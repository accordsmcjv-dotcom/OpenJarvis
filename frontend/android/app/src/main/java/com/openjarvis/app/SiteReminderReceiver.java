package com.openjarvis.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import androidx.core.app.NotificationCompat;

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
    }
}
