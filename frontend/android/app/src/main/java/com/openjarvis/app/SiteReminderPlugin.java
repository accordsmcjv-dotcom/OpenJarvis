package com.openjarvis.app;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import org.json.JSONObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.JSObject;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "SiteReminder")
public class SiteReminderPlugin extends Plugin {
    @PluginMethod
    public void scheduleReminder(PluginCall call) {
        String id = call.getString("id");
        String title = call.getString("title");
        String site = call.getString("site", "");
        long triggerAt = call.getLong("triggerAt", 0L);
        if (id == null || id.trim().isEmpty() || title == null || title.trim().isEmpty() || triggerAt <= System.currentTimeMillis()) {
            call.reject("कामाची माहिती आणि भविष्यातील वेळ आवश्यक आहे.");
            return;
        }
        try {
            Intent intent = new Intent(getContext(), SiteReminderReceiver.class);
            intent.putExtra("id", id);
            intent.putExtra("title", title);
            intent.putExtra("site", site);
            PendingIntent pending = PendingIntent.getBroadcast(getContext(), id.hashCode(), intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            AlarmManager alarms = (AlarmManager) getContext().getSystemService(Context.ALARM_SERVICE);
            if (alarms == null) throw new IllegalStateException("Alarm service unavailable");
            alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pending);
            JSONObject saved = new JSONObject();
            saved.put("id", id); saved.put("title", title); saved.put("site", site); saved.put("triggerAt", triggerAt);
            getContext().getSharedPreferences("shivam_site_reminders", Context.MODE_PRIVATE)
                .edit().putString("reminder_" + id, saved.toString()).apply();
            JSObject result = new JSObject();
            result.put("scheduled", true);
            call.resolve(result);
        } catch (Exception error) {
            call.reject("आठवण सेट करता आली नाही.", error);
        }
    }

    @PluginMethod
    public void cancelReminder(PluginCall call) {
        String id = call.getString("id");
        if (id == null || id.trim().isEmpty()) { call.reject("Reminder ID आवश्यक आहे."); return; }
        Intent intent = new Intent(getContext(), SiteReminderReceiver.class);
        PendingIntent pending = PendingIntent.getBroadcast(getContext(), id.hashCode(), intent,
            PendingIntent.FLAG_NO_CREATE | PendingIntent.FLAG_IMMUTABLE);
        if (pending != null) {
            AlarmManager alarms = (AlarmManager) getContext().getSystemService(Context.ALARM_SERVICE);
            if (alarms != null) alarms.cancel(pending);
            pending.cancel();
        }
        // Remove the persisted reminder too, otherwise the boot receiver could
        // recreate an alarm that the user already cancelled or completed.
        getContext().getSharedPreferences("shivam_site_reminders", Context.MODE_PRIVATE)
            .edit().remove("reminder_" + id).apply();
        JSObject result = new JSObject();
        result.put("cancelled", true);
        call.resolve(result);
    }
}
