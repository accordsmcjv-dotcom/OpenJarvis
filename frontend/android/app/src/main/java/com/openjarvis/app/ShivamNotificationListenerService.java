package com.openjarvis.app;

import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.app.Notification;
import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;

public class ShivamNotificationListenerService extends NotificationListenerService {
    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null || sbn.getPackageName() == null) return;
        Notification notification = sbn.getNotification();
        if (notification == null || notification.extras == null) return;
        Bundle extras = notification.extras;
        CharSequence titleValue = extras.getCharSequence(Notification.EXTRA_TITLE);
        CharSequence textValue = extras.getCharSequence(Notification.EXTRA_BIG_TEXT);
        if (TextUtils.isEmpty(textValue)) textValue = extras.getCharSequence(Notification.EXTRA_TEXT);
        Intent event = new Intent("com.openjarvis.app.NOTIFICATION_CAPTURED");
        event.setPackage(getPackageName());
        event.putExtra("packageName", sbn.getPackageName());
        event.putExtra("title", titleValue == null ? "" : titleValue.toString());
        event.putExtra("text", textValue == null ? "" : textValue.toString());
        sendBroadcast(event);
    }
}
