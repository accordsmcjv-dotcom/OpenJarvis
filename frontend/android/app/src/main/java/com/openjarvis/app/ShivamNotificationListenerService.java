package com.openjarvis.app;

import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.app.Notification;
import android.content.Intent;
import android.os.Bundle;
import android.app.KeyguardManager;
import android.text.TextUtils;

import java.util.Locale;
import java.util.regex.Pattern;

public class ShivamNotificationListenerService extends NotificationListenerService {
    private static final Pattern SECRET_NUMBER = Pattern.compile("\\b\\d{4,8}\\b");
    private static final Pattern SECRET_WORDS = Pattern.compile(
        "(?i)(otp|one[- ]?time|verification|verify|password|passcode|pin code|पिन कोड|पासवर्ड|transaction|debit|credit|credited|debited|balance|payment|upi|\u092c\u0948\u0902\u0915|\u0916\u093e\u0924\u093e|\u0913\u091f\u0940\u092a\u0940)");

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null || sbn.getPackageName() == null) return;
        KeyguardManager keyguard = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        if (keyguard != null && keyguard.isKeyguardLocked()) return;

        String packageName = sbn.getPackageName().toLowerCase(Locale.ROOT);
        // Never forward private conversations, financial apps, authenticators, or SHIVAM's own notifications.
        if (packageName.equals(getPackageName())
            || packageName.matches(".*(bank|banking|wallet|paytm|phonepe|gpay|google\\.android\\.apps\\.authenticator|authenticator|password|credential|whatsapp|telegram|signal|messenger|messages|sms|com\\.google\\.android\\.apps\\.messaging).*")) return;

        Notification notification = sbn.getNotification();
        if (notification == null || notification.extras == null) return;
        Bundle extras = notification.extras;
        CharSequence titleValue = extras.getCharSequence(Notification.EXTRA_TITLE);
        CharSequence textValue = extras.getCharSequence(Notification.EXTRA_BIG_TEXT);
        if (TextUtils.isEmpty(textValue)) textValue = extras.getCharSequence(Notification.EXTRA_TEXT);
        String content = (String.valueOf(titleValue) + " " + String.valueOf(textValue)).trim();
        if (content.isEmpty() || SECRET_WORDS.matcher(content).find()) return;
        if (SECRET_NUMBER.matcher(content).find() && Pattern.compile("(?i)(code|verify|verification|otp|login|sign.?in)").matcher(content).find()) return;

        Intent event = new Intent("com.openjarvis.app.NOTIFICATION_CAPTURED");
        event.setPackage(getPackageName());
        event.putExtra("packageName", sbn.getPackageName());
        event.putExtra("title", titleValue == null ? "" : titleValue.toString());
        event.putExtra("text", textValue == null ? "" : textValue.toString());
        sendBroadcast(event);
    }
}
