package com.openjarvis.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;

import androidx.activity.result.ActivityResult;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions;

@CapacitorPlugin(name = "ScreenUnderstanding")
public class ScreenUnderstandingPlugin extends Plugin {
    private PluginCall pendingCall;
    private BroadcastReceiver resultReceiver;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable timeout;
    private TextRecognizer imageDevanagariRecognizer;
    private TextRecognizer imageLatinRecognizer;

    @PluginMethod
    public void captureAndReadScreen(PluginCall call) {
        if (pendingCall != null) {
            call.reject("स्क्रीन वाचण्याची विनंती आधीच सुरू आहे.");
            return;
        }
        MediaProjectionManager manager = (MediaProjectionManager)
                getContext().getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        if (manager == null) {
            call.reject("या Android आवृत्तीत Screen Capture उपलब्ध नाही.");
            return;
        }
        pendingCall = call;
        startActivityForResult(call, manager.createScreenCaptureIntent(), "screenPermissionResult");
    }

    @PluginMethod
    public void pickImageAndRead(PluginCall call) {
        if (pendingCall != null) {
            call.reject("दुसरी वाचन विनंती आधीच सुरू आहे.");
            return;
        }
        pendingCall = call;
        Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.setType("image/*");
        try {
            startActivityForResult(call, picker, "imagePermissionResult");
        } catch (Exception e) {
            pendingCall = null;
            call.reject("फोटो निवडता आला नाही: " + e.getMessage());
        }
    }

    @ActivityCallback
    private void imagePermissionResult(PluginCall call, ActivityResult result) {
        if (pendingCall == null) return;
        if (result == null || result.getResultCode() != android.app.Activity.RESULT_OK
                || result.getData() == null || result.getData().getData() == null) {
            finishWithError("फोटो निवडणे रद्द केले.");
            return;
        }
        Uri uri = result.getData().getData();
        try {
            InputImage image = InputImage.fromFilePath(getContext(), uri);
            imageDevanagariRecognizer = TextRecognition.getClient(
                    new DevanagariTextRecognizerOptions.Builder().build());
            imageLatinRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            final String[] devanagariText = {""};
            final String[] latinText = {""};
            final boolean[] success = {false};
            final int[] completed = {0};
            Runnable combine = () -> {
                completed[0]++;
                if (completed[0] != 2) return;
                if (timeout != null) handler.removeCallbacks(timeout);
                String text = (devanagariText[0] + "\n" + latinText[0]).trim();
                closeImageRecognizers();
                PluginCall pending = pendingCall;
                pendingCall = null;
                if (pending == null) return;
                if (!success[0] || text.isEmpty()) {
                    pending.reject("फोटोमध्ये वाचता येण्याजोगा मजकूर आढळला नाही.");
                    return;
                }
                JSObject response = new JSObject();
                response.put("text", text);
                response.put("message", "फोटोवरील मजकूर वाचला.");
                pending.resolve(response);
            };
            imageDevanagariRecognizer.process(image)
                    .addOnSuccessListener(value -> { devanagariText[0] = value.getText(); success[0] = true; })
                    .addOnCompleteListener(task -> combine.run());
            imageLatinRecognizer.process(image)
                    .addOnSuccessListener(value -> { latinText[0] = value.getText(); success[0] = true; })
                    .addOnCompleteListener(task -> combine.run());
            timeout = () -> finishWithError("फोटोमधील मजकूर वाचण्यासाठी वेळ लागला. पुन्हा प्रयत्न करा.");
            handler.postDelayed(timeout, 20000);
        } catch (Exception e) {
            closeImageRecognizers();
            finishWithError("फोटो वाचता आला नाही: " + e.getMessage());
        }
    }

    @ActivityCallback
    private void screenPermissionResult(PluginCall call, ActivityResult result) {
        if (pendingCall == null) return;
        if (result == null || result.getResultCode() != android.app.Activity.RESULT_OK
                || result.getData() == null) {
            finishWithError("तुम्ही स्क्रीन पाहण्याची परवानगी दिली नाही.");
            return;
        }

        registerResultReceiver();
        Intent service = new Intent(getContext(), ShivamScreenCaptureService.class);
        service.putExtra(ShivamScreenCaptureService.EXTRA_RESULT_CODE, result.getResultCode());
        service.putExtra(ShivamScreenCaptureService.EXTRA_RESULT_DATA, result.getData());
        try {
            if (Build.VERSION.SDK_INT >= 26) getContext().startForegroundService(service);
            else getContext().startService(service);
            timeout = () -> finishWithError("स्क्रीनमधील मजकूर वाचण्यासाठी वेळ लागला. पुन्हा प्रयत्न करा.");
            handler.postDelayed(timeout, 20000);
        } catch (Exception e) {
            finishWithError("Screen Capture सुरू करता आले नाही: " + e.getMessage());
        }
    }

    private void registerResultReceiver() {
        resultReceiver = new BroadcastReceiver() {
            @Override public void onReceive(Context context, Intent intent) {
                if (timeout != null) handler.removeCallbacks(timeout);
                String text = intent.getStringExtra(ShivamScreenCaptureService.EXTRA_TEXT);
                boolean ok = intent.getBooleanExtra(ShivamScreenCaptureService.EXTRA_SUCCESS, false);
                unregisterResultReceiver();
                PluginCall call = pendingCall;
                pendingCall = null;
                if (call == null) return;
                if (!ok) {
                    call.reject(text == null ? "स्क्रीन वाचता आली नाही." : text);
                    return;
                }
                JSObject response = new JSObject();
                response.put("text", text == null ? "" : text);
                response.put("message", "स्क्रीनवरील मजकूर वाचला.");
                call.resolve(response);
            }
        };
        IntentFilter filter = new IntentFilter(ShivamScreenCaptureService.ACTION_RESULT);
        if (Build.VERSION.SDK_INT >= 33) getContext().registerReceiver(resultReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        else getContext().registerReceiver(resultReceiver, filter);
    }

    private void closeImageRecognizers() {
        if (imageDevanagariRecognizer != null) { imageDevanagariRecognizer.close(); imageDevanagariRecognizer = null; }
        if (imageLatinRecognizer != null) { imageLatinRecognizer.close(); imageLatinRecognizer = null; }
    }

    private void finishWithError(String message) {
        closeImageRecognizers();
        if (timeout != null) handler.removeCallbacks(timeout);
        try {
            getContext().stopService(new Intent(getContext(), ShivamScreenCaptureService.class));
        } catch (Exception ignored) {}
        unregisterResultReceiver();
        PluginCall call = pendingCall;
        pendingCall = null;
        if (call != null) call.reject(message);
    }

    private void unregisterResultReceiver() {
        if (resultReceiver != null) {
            try { getContext().unregisterReceiver(resultReceiver); } catch (Exception ignored) {}
            resultReceiver = null;
        }
    }

    @Override
    protected void handleOnDestroy() {
        if (timeout != null) handler.removeCallbacks(timeout);
        unregisterResultReceiver();
        closeImageRecognizers();
        if (pendingCall != null) {
            pendingCall.reject("SHIVAM बंद झाले.");
            pendingCall = null;
        }
        super.handleOnDestroy();
    }
}
