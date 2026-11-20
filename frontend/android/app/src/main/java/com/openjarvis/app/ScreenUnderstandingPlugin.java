package com.openjarvis.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
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

@CapacitorPlugin(name = "ScreenUnderstanding")
public class ScreenUnderstandingPlugin extends Plugin {
    private PluginCall pendingCall;
    private BroadcastReceiver resultReceiver;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable timeout;

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

    private void finishWithError(String message) {
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
        if (pendingCall != null) {
            pendingCall.reject("SHIVAM बंद झाले.");
            pendingCall = null;
        }
        super.handleOnDestroy();
    }
}
