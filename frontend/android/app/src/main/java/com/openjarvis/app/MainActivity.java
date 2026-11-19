package com.openjarvis.app;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;\nimport android.content.Intent;\nimport android.os.Handler;\nimport android.os.Looper;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private static final int SHIVAM_PERMISSION_REQUEST = 7401;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(ShivamWakeWordPlugin.class);\n        super.onCreate(savedInstanceState);\n        dispatchWakeIntent(getIntent());
        requestShivamPermissions();
    }

    @Override protected void onNewIntent(Intent intent) { super.onNewIntent(intent); setIntent(intent); dispatchWakeIntent(intent); }\n\n    private void dispatchWakeIntent(Intent intent) {\n        if (intent == null || !\"com.openjarvis.app.SHIVAM_WAKE\".equals(intent.getAction())) return;\n        intent.setAction(Intent.ACTION_MAIN);\n        new Handler(Looper.getMainLooper()).postDelayed(() -> { if (getBridge()!=null && getBridge().getWebView()!=null) getBridge().getWebView().evaluateJavascript(\"window.dispatchEvent(new Event('shivamWakeWord'))\", null); }, 1100);\n    }\n\n    private void requestShivamPermissions() {
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
