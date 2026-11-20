package com.openjarvis.app;

import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.app.Notification;
import android.content.Intent;
import android.os.Bundle;
import android.app.KeyguardManager;
import android.text.TextUtils;

public class ShivamNotificationListenerService extends NotificationListenerService {
    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null || sbn.getPackageName() == null) return;
        // Do not forward notification contents while the device is locked.
        KeyguardManager keyguard = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        if (keyguard != null && keyguard.isKeyguardLocked()) return;
        String packageName = sbn.getPackageName().toLowerCase(java.util.Locale.ROOT);
        if (packageName.matches(".*(bank|banking|wallet|paytm|phonepe|gpay|google\\.android\\.apps\\.authenticator|authenticator|password|credential).*")) return;
        Notification notification = sbn.getNotification();
        if (notification == null || notification.extras == null) return;
        Bundle extras = notification.extras;
        CharSequence titleValue = extras.getCharSequence(Notification.EXTRA_TITLE);
        CharSequence textValue = extras.getCharSequence(Notification.EXTRA_BIG_TEXT);
        if (TextUtils.isEmpty(textValue)) textValue = extras.getCharSequence(Notification.EXTRA_TEXT);
        String content = (String.valueOf(titleValue) + " " + String.valueOf(textValue)).toLowerCase(java.util.Locale.ROOT);
        if (content.matches("(?s).*\\\\b\\\\d{4,8}\\\\b.*") && (content.contains("otp") || content.contains("one-time") || content.contains("verification") || content.contains("code"))) return;
        if (content.matches("(?s).*\\\\b\\\\d{4,8}\\\\b.*") && (content.contains("otp") || content.contains("one-time") || content.contains("verification") || content.contains("code"))) return;
        Intent event = new Intent("com.openjarvis.app.NOTIFICATION_CAPTURED");
        event.setPackage(getPackageName());
        event.putExtra("packageName", sbn.getPackageName());
        event.putExtra("title", titleValue == null ? "" : titleValue.toString());
        event.putExtra("text", textValue == null ? "" : textValue.toString());
        sendBroadcast(event);
    }
}
