package com.openjarvis.app;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private static final int SHIVAM_PERMISSION_REQUEST = 7401;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(ShivamWakeWordPlugin.class);
        super.onCreate(savedInstanceState);
        dispatchWakeIntent(getIntent());
        requestShivamPermissions();
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startShivamWakeWordService();
        }
    }

    @Override protected void onNewIntent(Intent intent) { super.onNewIntent(intent); setIntent(intent); dispatchWakeIntent(intent); }

    private void dispatchWakeIntent(Intent intent) {
        if (intent == null || !"com.openjarvis.app.SHIVAM_WAKE".equals(intent.getAction())) return;
        intent.setAction(Intent.ACTION_MAIN);
        new Handler(Looper.getMainLooper()).postDelayed(() -> { if (getBridge()!=null && getBridge().getWebView()!=null) getBridge().getWebView().evaluateJavascript("localStorage.setItem('shivam-wake-pending','1'); window.dispatchEvent(new Event('shivamWakeWord'))", null); }, 1100);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == SHIVAM_PERMISSION_REQUEST
                && checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startShivamWakeWordService();
        }
    }

    private void startShivamWakeWordService() {
        Intent service = new Intent(this, ShivamWakeWordService.class);
        service.setAction(ShivamWakeWordService.ACTION_START);
        androidx.core.content.ContextCompat.startForegroundService(this, service);
    }

    private void requestShivamPermissions() {
        java.util.ArrayList<String> missing = new java.util.ArrayList<>();

        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            missing.add(Manifest.permission.RECORD_AUDIO);
        }

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            missing.add(Manifest.permission.POST_NOTIFICATIONS);
        }

        if (!missing.isEmpty()) {
            requestPermissions(
                missing.toArray(new String[0]),
                SHIVAM_PERMISSION_REQUEST
            );
        }
    }
}
