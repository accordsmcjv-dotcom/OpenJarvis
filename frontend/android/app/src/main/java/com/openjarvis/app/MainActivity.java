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
        registerPlugin(ScreenUnderstandingPlugin.class);
        registerPlugin(ContactsCallPlugin.class);
        registerPlugin(ShivamLocationPlugin.class);
        registerPlugin(ShivamDevicePlugin.class);
        super.onCreate(savedInstanceState);
        Intent launchIntent = getIntent();
        boolean launchedByWakeWord = launchIntent != null
                && "com.openjarvis.app.SHIVAM_WAKE".equals(launchIntent.getAction());
        dispatchWakeIntent(launchIntent);
        requestShivamPermissions();
        if (!launchedByWakeWord
                && isWakeWordEnabled()
                && checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startShivamWakeWordService();
        }
    }

    @Override protected void onNewIntent(Intent intent) { super.onNewIntent(intent); setIntent(intent); dispatchWakeIntent(intent); }

    private void dispatchWakeIntent(Intent intent) {
        if (intent == null || !"com.openjarvis.app.SHIVAM_WAKE".equals(intent.getAction())) return;
        // Wake the display when the wake word is detected, without bypassing the lock screen.
        if (Build.VERSION.SDK_INT >= 27) {
            setTurnScreenOn(true);
        } else {
            getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON);
        }
        intent.setAction(Intent.ACTION_MAIN);
        new Handler(Looper.getMainLooper()).postDelayed(() -> { if (getBridge()!=null && getBridge().getWebView()!=null) getBridge().getWebView().evaluateJavascript("localStorage.setItem('shivam-wake-pending','1'); window.dispatchEvent(new Event('shivamWakeWord'))", null); }, 1100);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == SHIVAM_PERMISSION_REQUEST
                && isWakeWordEnabled()
                && checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startShivamWakeWordService();
        }
    }

    private boolean isWakeWordEnabled() {
        return getSharedPreferences("shivam_wake_word", MODE_PRIVATE)
                .getBoolean("enabled", false);
    }

    private void startShivamWakeWordService() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        Intent service = new Intent(this, ShivamWakeWordService.class);
        service.setAction(ShivamWakeWordService.ACTION_START);
        try {
            androidx.core.content.ContextCompat.startForegroundService(this, service);
        } catch (SecurityException | IllegalStateException error) {
            // Permission may have been revoked or Android may reject a
            // foreground-service start; keep the app usable without wake word.
            android.util.Log.w("SHIVAM", "Wake-word service could not start", error);
        }
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
