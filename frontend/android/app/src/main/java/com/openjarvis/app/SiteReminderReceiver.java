package com.openjarvis.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import androidx.core.app.NotificationCompat;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

public class SiteReminderReceiver extends BroadcastReceiver {
    private static final String CHANNEL_ID = "shivam_site_reminders";
    @Override public void onReceive(Context context, Intent intent) {
        String id = intent.getStringExtra("id");
        String title = intent.getStringExtra("title");
        String site = intent.getStringExtra("site");
        if (title == null || title.trim().isEmpty()) return;
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(CHANNEL_ID, "SHIVAM Site Reminders", NotificationManager.IMPORTANCE_HIGH);
            channel.setDescription("बांधकाम साइटवरील कामांच्या आठवणी");
            manager.createNotificationChannel(channel);
        }
        Intent open = new Intent(context, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent content = PendingIntent.getActivity(context, 0, open,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        String body = site == null || site.trim().isEmpty() ? title : site + " — " + title;
        NotificationCompat.Builder notification = new NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(context.getApplicationInfo().icon)
            .setContentTitle("SHIVAM — साइटची आठवण")
            .setContentText(body)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(content)
            .setDefaults(NotificationCompat.DEFAULT_ALL);
        manager.notify(id == null ? (int) System.currentTimeMillis() : id.hashCode(), notification.build());

        // Speak the reminder in Marathi using Android's installed speech engine.
        speakReminder(context.getApplicationContext(), body);
    }

    private void speakReminder(Context context, String body) {
        final BroadcastReceiver.PendingResult pending = goAsync();
        final AtomicBoolean finished = new AtomicBoolean(false);
        PowerManager power = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        final PowerManager.WakeLock wakeLock = power == null ? null
            : power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "SHIVAM:SiteReminder");
        if (wakeLock != null) wakeLock.acquire(35000L);
        final TextToSpeech[] engine = new TextToSpeech[1];
        Runnable finish = () -> {
            if (!finished.compareAndSet(false, true)) return;
            if (engine[0] != null) engine[0].shutdown();
            if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
            pending.finish();
        };
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(finish, 30000L);
        engine[0] = new TextToSpeech(context, status -> {
            if (status != TextToSpeech.SUCCESS) { finish.run(); return; }
            try {
                int language = engine[0].setLanguage(Locale.forLanguageTag("mr-IN"));
                if (language == TextToSpeech.LANG_MISSING_DATA || language == TextToSpeech.LANG_NOT_SUPPORTED) {
                    finish.run();
                    return;
                }
                engine[0].setSpeechRate(0.95f);
                engine[0].setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override public void onStart(String utteranceId) { }
                    @Override public void onDone(String utteranceId) { finish.run(); }
                    @Override public void onError(String utteranceId) { finish.run(); }
                });
                Bundle params = new Bundle();
                engine[0].speak("साइटची आठवण. " + body, TextToSpeech.QUEUE_FLUSH, params, "shivam-site-" + System.currentTimeMillis());
            } catch (Exception error) { finish.run(); }
        });
    }
}
