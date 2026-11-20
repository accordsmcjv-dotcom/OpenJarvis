package com.openjarvis.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;

import java.util.ArrayList;
import java.util.Locale;

public class ShivamWakeWordService extends Service {
    public static final String ACTION_START = "com.openjarvis.app.WAKE_START";
    private static final String CHANNEL = "shivam_wake_word";
    private static final int NOTIFICATION_ID = 7402;
    private static final long RETRY_DELAY_MS = 1800L;
    // Android speech sessions can stall without delivering onError/onResults.
    private static final long LISTEN_TIMEOUT_MS = 12000L;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean active = false;
    private boolean launching = false;
    // Prefer Android's on-device recognizer when the device exposes one.
    // Some devices do not ship an offline Marathi model, so retain a fallback.
    private boolean useOnDeviceRecognizer = false;
    private SpeechRecognizer recognizer;

    private final Runnable restartListening = () -> {
        if (active && !launching) listen();
    };
    private final Runnable listenTimeout = () -> {
        if (!active || launching) return;
        destroyRecognizer();
        scheduleRestart();
    };

    @Override
    public void onCreate() {
        super.onCreate();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL, "SHIVAM Wake Word", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Visible microphone notification while SHIVAM listens.");
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || ACTION_START.equals(intent.getAction())) {
            if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                    != PackageManager.PERMISSION_GRANTED) {
                stopSelf();
                return START_NOT_STICKY;
            }
            if (!active) {
                try {
                    startForegroundNow();
                    active = true;
                    useOnDeviceRecognizer = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                            && SpeechRecognizer.isOnDeviceRecognitionAvailable(this);
                    listen();
                } catch (SecurityException | IllegalStateException error) {
                    active = false;
                    stopSelf();
                    return START_NOT_STICKY;
                }
            }
        }
        return START_STICKY;
    }

    private void startForegroundNow() {
        Intent open = new Intent(this, MainActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, NOTIFICATION_ID, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new Notification.Builder(this, CHANNEL)
                .setContentTitle("SHIVAM आवाज ऐकत आहे")
                .setContentText("“Shivam” म्हणा. बंद करण्यासाठी अॅपमधील सेवा बंद करा.")
                .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .build();

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private void listen() {
        if (!active || launching) return;
        if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            stopSelf();
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            scheduleRestart();
            return;
        }

        destroyRecognizer();
        try {
            recognizer = useOnDeviceRecognizer
                    ? SpeechRecognizer.createOnDeviceSpeechRecognizer(this)
                    : SpeechRecognizer.createSpeechRecognizer(this);
            recognizer.setRecognitionListener(new RecognitionListener() {
                @Override public void onReadyForSpeech(android.os.Bundle params) {}
                @Override public void onBeginningOfSpeech() {}
                @Override public void onRmsChanged(float rmsdB) {}
                @Override public void onBufferReceived(byte[] buffer) {}
                @Override public void onEndOfSpeech() {}
                @Override public void onPartialResults(android.os.Bundle partialResults) {
                    if (containsWakeWord(partialResults)) wake();
                }
                @Override public void onEvent(int eventType, android.os.Bundle params) {}

                @Override
                public void onError(int error) {
                    handler.removeCallbacks(listenTimeout);
                    // Fall back once if the local service lacks Marathi or its model.
                    if (useOnDeviceRecognizer) useOnDeviceRecognizer = false;
                    scheduleRestart();
                }

                @Override
                public void onResults(android.os.Bundle results) {
                    handler.removeCallbacks(listenTimeout);
                    if (containsWakeWord(results)) {
                        wake();
                        return;
                    }
                    scheduleRestart();
                }
            });

            Intent request = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            request.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            request.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "mr-IN");
            request.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "mr-IN");
            request.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
            request.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 4);
            recognizer.startListening(request);
            handler.removeCallbacks(listenTimeout);
            handler.postDelayed(listenTimeout, LISTEN_TIMEOUT_MS);
        } catch (Exception error) {
            if (useOnDeviceRecognizer) useOnDeviceRecognizer = false;
            scheduleRestart();
        }
    }

    private boolean containsWakeWord(android.os.Bundle results) {
        if (results == null) return false;
        ArrayList<String> matches = results.getStringArrayList(
                SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches == null) return false;
        for (String match : matches) {
            String value = match == null ? "" : match.toLowerCase(Locale.ROOT)
                    .replaceAll("[^\\p{L}\\p{N}]+", " ").trim();
            // Match a complete spoken token, not an accidental substring in another word.
            for (String token : value.split("\\s+")) {
                if (token.equals("shivam") || token.equals("शिवम")
                        || token.equals("शिवम्") || token.equals("शिवाम")
                        || token.equals("शिवान")) return true;
            }
        }
        return false;
    }

    private void scheduleRestart() {
        if (!active || launching) return;
        handler.removeCallbacks(listenTimeout);
        handler.removeCallbacks(restartListening);
        handler.postDelayed(restartListening, RETRY_DELAY_MS);
    }

    private void wake() {
        if (launching) return;
        launching = true;
        active = false;
        handler.removeCallbacksAndMessages(null);
        destroyRecognizer();

        Intent intent = new Intent(this, MainActivity.class);
        intent.setAction("com.openjarvis.app.SHIVAM_WAKE");
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                | Intent.FLAG_ACTIVITY_SINGLE_TOP
                | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        try {
            startActivity(intent);
        } catch (Exception ignored) {
            // The ongoing notification remains available as a manual way back into SHIVAM.
        }
        stopForeground(true);
        stopSelf();
    }

    private void destroyRecognizer() {
        SpeechRecognizer current = recognizer;
        recognizer = null;
        if (current != null) {
            try { current.cancel(); } catch (Exception ignored) {}
            try { current.destroy(); } catch (Exception ignored) {}
        }
    }

    @Override
    public void onDestroy() {
        active = false;
        handler.removeCallbacksAndMessages(null);
        destroyRecognizer();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}