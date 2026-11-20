package com.openjarvis.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ServiceInfo;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.os.Build;
import android.os.IBinder;
import android.os.StatFs;
import android.os.Environment;

import java.util.Locale;

public class ShivamWatchmanService extends Service {
    public static final String ACTION_START = "com.openjarvis.app.WATCHMAN_START";
    public static final String ACTION_STOP = "com.openjarvis.app.WATCHMAN_STOP";
    private static final String CHANNEL_ID = "shivam_watchman";
    private static final int NOTIFICATION_ID = 8401;
    private BroadcastReceiver systemReceiver;
    private ConnectivityManager connectivityManager;
    private ConnectivityManager.NetworkCallback networkCallback;
    private boolean internetAvailable;

    @Override public void onCreate() {
        super.onCreate();
        createChannel();
        startOngoingNotification("फोनची स्थिती सुरक्षितपणे पाहत आहे");
        registerSystemSignals();
        registerNetworkSignals();
        inspectDevice();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        return START_STICKY;
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    @Override public void onDestroy() {
        if (systemReceiver != null) {
            try { unregisterReceiver(systemReceiver); } catch (Exception ignored) { }
            systemReceiver = null;
        }
        if (connectivityManager != null && networkCallback != null) {
            try { connectivityManager.unregisterNetworkCallback(networkCallback); } catch (Exception ignored) { }
            networkCallback = null;
        }
        super.onDestroy();
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "SHIVAM Smart Watchman", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("फोनची स्थिती आणि महत्त्वाचे अलर्ट");
            channel.setShowBadge(false);
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    private void startOngoingNotification(String message) {
        Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
        PendingIntent pending = launch == null ? null : PendingIntent.getActivity(
            this, 8401, launch, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, CHANNEL_ID) : new Notification.Builder(this);
        builder.setSmallIcon(getApplicationInfo().icon)
            .setContentTitle("SHIVAM Smart Watchman")
            .setContentText(message)
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setOnlyAlertOnce(true);
        if (pending != null) builder.setContentIntent(pending);
        Notification notification = builder.build();
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private void registerSystemSignals() {
        systemReceiver = new BroadcastReceiver() {
            @Override public void onReceive(Context context, Intent intent) {
                if (intent == null) return;
                String action = intent.getAction();
                if (Intent.ACTION_BATTERY_CHANGED.equals(action)
                    || Intent.ACTION_POWER_CONNECTED.equals(action)
                    || Intent.ACTION_POWER_DISCONNECTED.equals(action)
                    || Intent.ACTION_DEVICE_STORAGE_LOW.equals(action)
                    || Intent.ACTION_DEVICE_STORAGE_OK.equals(action)) {
                    inspectDevice();
                }
            }
        };
        IntentFilter filter = new IntentFilter();
        filter.addAction(Intent.ACTION_BATTERY_CHANGED);
        filter.addAction(Intent.ACTION_POWER_CONNECTED);
        filter.addAction(Intent.ACTION_POWER_DISCONNECTED);
        filter.addAction(Intent.ACTION_DEVICE_STORAGE_LOW);
        filter.addAction(Intent.ACTION_DEVICE_STORAGE_OK);
        try {
            if (Build.VERSION.SDK_INT >= 33) registerReceiver(systemReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
            else registerReceiver(systemReceiver, filter);
        } catch (Exception ignored) { }
    }

    private void registerNetworkSignals() {
        connectivityManager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (connectivityManager == null) return;
        networkCallback = new ConnectivityManager.NetworkCallback() {
            @Override public void onAvailable(Network network) {
                internetAvailable = hasValidatedInternet();
                updateStatusNotification();
            }
            @Override public void onLost(Network network) {
                internetAvailable = hasValidatedInternet();
                updateStatusNotification();
                if (!internetAvailable) postAlert("इंटरनेट कनेक्शन उपलब्ध नाही");
            }
            @Override public void onCapabilitiesChanged(Network network, NetworkCapabilities caps) {
                internetAvailable = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
                updateStatusNotification();
            }
        };
        try { connectivityManager.registerDefaultNetworkCallback(networkCallback); }
        catch (Exception ignored) { }
        internetAvailable = hasValidatedInternet();
    }

    private boolean hasValidatedInternet() {
        if (connectivityManager == null) return false;
        Network active = connectivityManager.getActiveNetwork();
        NetworkCapabilities caps = active == null ? null : connectivityManager.getNetworkCapabilities(active);
        return caps != null && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
    }

    private void inspectDevice() {
        Intent battery = registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        if (battery != null) {
            int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
            int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
            int percent = level >= 0 && scale > 0 ? Math.round(level * 100f / scale) : -1;
            int temp = battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1);
            boolean charging = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1) == BatteryManager.BATTERY_STATUS_CHARGING
                || battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1) == BatteryManager.BATTERY_STATUS_FULL;
            if (percent >= 0 && percent <= 20 && !charging) postAlertOnce("battery_low", "बॅटरी " + percent + "% आहे. चार्जर जोडा.");
            else if (percent > 25 || charging) clearAlert("battery_low");
            if (temp >= 450 && !charging) postAlertOnce("battery_hot", "बॅटरीचे तापमान " + String.format(Locale.ROOT, "%.1f", temp / 10.0) + "°C आहे.");
            else if (temp > 0 && temp <= 420) clearAlert("battery_hot");
        }
        try {
            StatFs stats = new StatFs(Environment.getDataDirectory().getPath());
            long free = stats.getAvailableBytes();
            long total = stats.getTotalBytes();
            if (total > 0 && free <= Math.max(5L * 1024 * 1024 * 1024, total / 10))
                postAlertOnce("storage_low", "फोनमधील उपलब्ध स्टोरेज कमी आहे.");
            else if (total > 0 && free > Math.max(6L * 1024 * 1024 * 1024, total * 12 / 100))
                clearAlert("storage_low");
        } catch (Exception ignored) { }
        updateStatusNotification();
    }

    private void updateStatusNotification() {
        String text = internetAvailable ? "फोनची स्थिती पाहत आहे · इंटरनेट जोडलेले" : "फोनची स्थिती पाहत आहे · इंटरनेट नाही";
        startOngoingNotification(text);
    }

    private void postAlertOnce(String key, String message) {
        android.content.SharedPreferences prefs = getSharedPreferences("shivam_watchman", MODE_PRIVATE);
        if (prefs.getBoolean(key, false)) return;
        prefs.edit().putBoolean(key, true).apply();
        postAlert(message);
    }

    private void clearAlert(String key) {
        getSharedPreferences("shivam_watchman", MODE_PRIVATE).edit().putBoolean(key, false).apply();
    }

    private void postAlert(String message) {
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, CHANNEL_ID) : new Notification.Builder(this);
        builder.setSmallIcon(getApplicationInfo().icon)
            .setContentTitle("SHIVAM Smart Watchman")
            .setContentText(message)
            .setAutoCancel(true)
            .setOnlyAlertOnce(true);
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager != null) manager.notify((int) (System.currentTimeMillis() % Integer.MAX_VALUE), builder.build());
    }
}
