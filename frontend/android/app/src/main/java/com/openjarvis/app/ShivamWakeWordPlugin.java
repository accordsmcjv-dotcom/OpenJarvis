package com.openjarvis.app;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;

import androidx.core.content.ContextCompat;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.ArrayList;

@CapacitorPlugin(name = "ShivamWakeWord")
public class ShivamWakeWordPlugin extends Plugin {
    private SpeechRecognizer commandRecognizer;
    private final Handler commandHandler = new Handler(Looper.getMainLooper());
    private PluginCall activeCommandCall;
    private final Runnable commandTimeout = () -> {
        PluginCall pending = activeCommandCall;
        releaseCommandRecognizer();
        if (pending != null) pending.reject("आवाज ओळखण्यासाठी वेळ संपला. पुन्हा प्रयत्न करा.");
    };

    @PluginMethod
    public void startListening(PluginCall call) {
        if (getContext().checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            call.reject("Microphone permission is required");
            return;
        }
        Intent intent = new Intent(getContext(), ShivamWakeWordService.class);
        intent.setAction(ShivamWakeWordService.ACTION_START);
        try {
            ContextCompat.startForegroundService(getContext(), intent);
            call.resolve();
        } catch (Exception e) {
            call.reject("Could not start voice service: " + e.getMessage());
        }
    }

    @PluginMethod
    public void stopListening(PluginCall call) {
        getContext().stopService(new Intent(getContext(), ShivamWakeWordService.class));
        call.resolve();
    }

    // Use Android's native SpeechRecognizer for Marathi command capture.
    // Android System WebView does not consistently expose Web Speech API.
    @PluginMethod
    public void recognizeSpeech(PluginCall call) {
        if (getContext().checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            call.reject("Microphone permission is required");
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(getContext())) {
            call.reject("Android speech recognition service is unavailable");
            return;
        }

        getActivity().runOnUiThread(() -> {
            PluginCall previousCall = activeCommandCall;
            destroyCommandRecognizer();
            if (previousCall != null) {
                previousCall.reject("नवीन आवाज विनंती सुरू झाली.");
            }
            activeCommandCall = call;
            commandHandler.postDelayed(commandTimeout, 15000L);
            startCommandRecognition(call,
                    Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                            && SpeechRecognizer.isOnDeviceRecognitionAvailable(getContext()));
        });
    }

    private void startCommandRecognition(PluginCall call, boolean preferOnDevice) {
        try {
            commandRecognizer = preferOnDevice
                    ? SpeechRecognizer.createOnDeviceSpeechRecognizer(getContext())
                    : SpeechRecognizer.createSpeechRecognizer(getContext());
            commandRecognizer.setRecognitionListener(new RecognitionListener() {
                @Override public void onReadyForSpeech(Bundle params) {}
                @Override public void onBeginningOfSpeech() {}
                @Override public void onRmsChanged(float rmsdB) {}
                @Override public void onBufferReceived(byte[] buffer) {}
                @Override public void onEndOfSpeech() {}
                @Override public void onPartialResults(Bundle partialResults) {}
                @Override public void onEvent(int eventType, Bundle params) {}

                @Override
                public void onResults(Bundle results) {
                    ArrayList<String> matches = results.getStringArrayList(
                            SpeechRecognizer.RESULTS_RECOGNITION);
                    String transcript = matches == null || matches.isEmpty()
                            ? "" : matches.get(0).trim();
                    releaseCommandRecognizer();
                    if (transcript.isEmpty()) {
                        call.reject("आवाज समजला नाही. पुन्हा प्रयत्न करा.");
                        return;
                    }
                    JSObject response = new JSObject();
                    response.put("text", transcript);
                    call.resolve(response);
                }

                @Override
                public void onError(int error) {
                    if (preferOnDevice && activeCommandCall == call) {
                        releaseCommandRecognizer();
                        startCommandRecognition(call, false);
                        return;
                    }
                    releaseCommandRecognizer();
                    call.reject("मराठी आवाज ओळखता आला नाही. त्रुटी क्रमांक: " + error);
                }
            });

            Intent request = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            request.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            request.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "mr-IN");
            request.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "mr-IN");
            request.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false);
            request.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
            commandRecognizer.startListening(request);
        } catch (Exception e) {
            releaseCommandRecognizer();
            if (preferOnDevice && activeCommandCall == call) {
                startCommandRecognition(call, false);
            } else {
                call.reject("मराठी आवाज ओळख सुरू करता आली नाही: " + e.getMessage());
            }
        }
    }

    @PluginMethod
    public void stopSpeechRecognition(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            if (commandRecognizer == null) {
                call.resolve();
                return;
            }
            try {
                commandRecognizer.stopListening();
                call.resolve();
            } catch (Exception e) {
                call.reject("आवाज ओळख थांबवता आली नाही: " + e.getMessage());
            }
        });
    }

    private void destroyCommandRecognizer() {
        closeCommandRecognizer(true);
    }

    private void releaseCommandRecognizer() {
        closeCommandRecognizer(false);
    }

    private void closeCommandRecognizer(boolean cancel) {
        commandHandler.removeCallbacks(commandTimeout);
        activeCommandCall = null;
        SpeechRecognizer current = commandRecognizer;
        commandRecognizer = null;
        if (current != null) {
            if (cancel) {
                try { current.cancel(); } catch (Exception ignored) {}
            }
            try { current.destroy(); } catch (Exception ignored) {}
        }
    }

    @Override
    protected void handleOnDestroy() {
        PluginCall pending = activeCommandCall;
        destroyCommandRecognizer();
        if (pending != null) {
            pending.reject("SHIVAM आवाज सेवा बंद झाली.");
        }
        super.handleOnDestroy();
    }
}
