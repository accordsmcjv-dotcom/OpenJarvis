package com.openjarvis.app;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import org.json.JSONObject;
import java.util.Map;

public class SiteReminderBootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())
                && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(intent.getAction())) return;
        AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarms == null) return;
        Map<String, ?> saved = context.getSharedPreferences("shivam_site_reminders", Context.MODE_PRIVATE).getAll();
        for (Object value : saved.values()) {
            if (!(value instanceof String)) continue;
            try {
                JSONObject item = new JSONObject((String) value);
                long triggerAt = item.optLong("triggerAt", 0L);
                String id = item.optString("id", "");
                if (id.isEmpty() || triggerAt <= System.currentTimeMillis()) continue;
                Intent alarm = new Intent(context, SiteReminderReceiver.class);
                alarm.putExtra("id", id);
                alarm.putExtra("title", item.optString("title", ""));
                alarm.putExtra("site", item.optString("site", ""));
                PendingIntent pending = PendingIntent.getBroadcast(context, id.hashCode(), alarm,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
                alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending);
            } catch (Exception ignored) { }
        }
    }
}
