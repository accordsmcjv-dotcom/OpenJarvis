package com.openjarvis.app;

import android.app.ActivityManager;
import android.app.NotificationManager;
import android.provider.Settings;
import android.content.ComponentName;
import android.app.KeyguardManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.Environment;
import android.os.Build;
import android.os.PowerManager;
import android.os.StatFs;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.wifi.WifiManager;
import android.net.Uri;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;

@CapacitorPlugin(name = "ShivamDevice")
public class ShivamDevicePlugin extends Plugin {
    private BroadcastReceiver chargingReceiver;
    private boolean chargingMonitorRegistered = false;
    private BroadcastReceiver notificationReceiver;

    @PluginMethod
    public void startChargingMonitor(PluginCall call) {
        try {
            if (!chargingMonitorRegistered) {
                chargingReceiver = new BroadcastReceiver() {
                    @Override
                    public void onReceive(Context context, Intent intent) {
                        String action = intent.getAction();
                        boolean connected = Intent.ACTION_POWER_CONNECTED.equals(action);
                        JSObject event = new JSObject();
                        event.put("charging", connected);
                        notifyListeners("chargingChanged", event);
                    }
                };
                IntentFilter filter = new IntentFilter();
                filter.addAction(Intent.ACTION_POWER_CONNECTED);
                filter.addAction(Intent.ACTION_POWER_DISCONNECTED);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    getContext().registerReceiver(chargingReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
                } else {
                    getContext().registerReceiver(chargingReceiver, filter);
                }
                chargingMonitorRegistered = true;
            }
            call.resolve();
        } catch (Exception error) {
            call.reject("चार्जरची स्थिती पाहता आली नाही.", error);
        }
    }

    @PluginMethod
    public void stopChargingMonitor(PluginCall call) {
        try {
            if (chargingMonitorRegistered && chargingReceiver != null) {
                getContext().unregisterReceiver(chargingReceiver);
                chargingReceiver = null;
                chargingMonitorRegistered = false;
            }
            call.resolve();
        } catch (Exception error) {
            call.reject("चार्जर मॉनिटर बंद करता आला नाही.", error);
        }
    }
    @Override
    public void load() {
        super.load();
        notificationReceiver = new BroadcastReceiver() {
            @Override public void onReceive(Context context, Intent intent) {
                JSObject event = new JSObject();
                event.put("packageName", intent.getStringExtra("packageName"));
                event.put("title", intent.getStringExtra("title"));
                event.put("text", intent.getStringExtra("text"));
                notifyListeners("notificationReceived", event);
            }
        };
        IntentFilter filter = new IntentFilter("com.openjarvis.app.NOTIFICATION_CAPTURED");
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getContext().registerReceiver(notificationReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            getContext().registerReceiver(notificationReceiver, filter);
        }
    }

    @PluginMethod
    public void startWatchman(PluginCall call) {
        try {
            Intent service = new Intent(getContext(), ShivamWatchmanService.class);
            service.setAction(ShivamWatchmanService.ACTION_START);
            androidx.core.content.ContextCompat.startForegroundService(getContext(), service);
            JSObject result = new JSObject();
            result.put("started", true);
            call.resolve(result);
        } catch (Exception error) {
            call.reject("Smart Watchman सुरू करता आला नाही. Notification परवानगी तपासा.", error);
        }
    }

    @PluginMethod
    public void setNotificationReadingEnabled(PluginCall call) {
        boolean enabled = call.getBoolean("enabled", false);
        getContext().getSharedPreferences("shivam_notification_privacy", Context.MODE_PRIVATE)
            .edit().putBoolean("voice_reading_enabled", enabled).apply();
        JSObject result = new JSObject();
        result.put("enabled", enabled);
        call.resolve(result);
    }

    @PluginMethod
    public void getWatchmanStatus(PluginCall call) {
        boolean enabled = getContext().getSharedPreferences("shivam_watchman", Context.MODE_PRIVATE)
            .getBoolean("user_enabled", false);
        JSObject result = new JSObject();
        result.put("enabled", enabled);
        call.resolve(result);
    }

    @PluginMethod
    public void stopWatchman(PluginCall call) {
        try {
            Intent service = new Intent(getContext(), ShivamWatchmanService.class);
            service.setAction(ShivamWatchmanService.ACTION_STOP);
            getContext().startService(service);
            JSObject result = new JSObject();
            result.put("stopping", true);
            call.resolve(result);
        } catch (Exception error) {
            call.reject("Smart Watchman बंद करता आला नाही.", error);
        }
    }

    @PluginMethod
    public void openNavigation(PluginCall call) {
        String destination = call.getString("destination");
        String mode = call.getString("mode", "driving");
        if (destination == null || destination.trim().isEmpty()) {
            call.reject("कृपया जाण्याचे ठिकाण सांगा.");
            return;
        }
        String travelMode = "walking".equalsIgnoreCase(mode) ? "walking"
            : "bicycling".equalsIgnoreCase(mode) ? "bicycling" : "driving";
        Uri mapsUri = Uri.parse("https://www.google.com/maps/dir/?api=1&destination="
            + Uri.encode(destination.trim()) + "&travelmode=" + travelMode + "&dir_action=navigate");
        try {
            Intent mapsIntent = new Intent(Intent.ACTION_VIEW, mapsUri);
            mapsIntent.setPackage("com.google.android.apps.maps");
            mapsIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            try {
                getContext().startActivity(mapsIntent);
            } catch (Exception mapsUnavailable) {
                Intent browserIntent = new Intent(Intent.ACTION_VIEW, mapsUri);
                browserIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                getContext().startActivity(browserIntent);
            }
            JSObject result = new JSObject();
            result.put("opened", true);
            result.put("travelMode", travelMode);
            call.resolve(result);
        } catch (Exception error) {
            call.reject("नकाशा उघडता आला नाही. Google Maps किंवा ब्राउझर तपासा.", error);
        }
    }

    @PluginMethod
    public void getNotificationAccessStatus(PluginCall call) {
        ComponentName listener = new ComponentName(getContext(), ShivamNotificationListenerService.class);
        String enabled = Settings.Secure.getString(getContext().getContentResolver(), "enabled_notification_listeners");
        boolean granted = enabled != null && enabled.contains(listener.flattenToString());
        JSObject result = new JSObject();
        result.put("granted", granted);
        call.resolve(result);
    }

    @PluginMethod
    public void openNotificationAccessSettings(PluginCall call) {
        try {
            Intent intent = new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            call.resolve();
        } catch (Exception error) {
            call.reject("Notification Access सेटिंग उघडता आली नाही.", error);
        }
    }

    @PluginMethod
    public void getTelemetry(PluginCall call) {
        try {
            JSObject result = new JSObject();
            Intent battery = getContext().registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
            if (battery != null) {
                int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
                int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
                if (level >= 0 && scale > 0) result.put("batteryPercent", Math.round(level * 100f / scale));
                int plugged = battery.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0);
                result.put("chargerConnected", plugged != 0);
                int status = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
                result.put("charging", status == BatteryManager.BATTERY_STATUS_CHARGING
                    || status == BatteryManager.BATTERY_STATUS_FULL);
                int temperature = battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1);
                if (temperature > 0) result.put("batteryTemperatureC", temperature / 10.0);
            }

            ConnectivityManager connectivity = (ConnectivityManager) getContext().getSystemService(Context.CONNECTIVITY_SERVICE);
            boolean networkConnected = false;
            boolean internetValidated = false;
            boolean wifiConnected = false;
            String networkTransport = "NONE";
            if (connectivity != null) {
                Network activeNetwork = connectivity.getActiveNetwork();
                if (activeNetwork != null) {
                    NetworkCapabilities capabilities = connectivity.getNetworkCapabilities(activeNetwork);
                    if (capabilities != null) {
                        networkConnected = capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
                        internetValidated = capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
                        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                            networkTransport = "WIFI";
                            wifiConnected = true;
                        } else if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
                            networkTransport = "CELLULAR";
                        } else if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
                            networkTransport = "ETHERNET";
                        } else if (networkConnected) {
                            networkTransport = "OTHER";
                        }
                    }
                }
            }
            WifiManager wifiManager = (WifiManager) getContext().getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            boolean wifiEnabled = wifiManager != null && wifiManager.isWifiEnabled();
            result.put("networkConnected", networkConnected);
            result.put("internetValidated", internetValidated);
            result.put("wifiEnabled", wifiEnabled);
            result.put("wifiConnected", wifiConnected);
            result.put("networkTransport", networkTransport);

            AudioManager audioManager = (AudioManager) getContext().getSystemService(Context.AUDIO_SERVICE);
            boolean bluetoothAudioConnected = false;
            boolean wiredHeadphonesConnected = false;
            if (audioManager != null) {
                AudioDeviceInfo[] outputs = audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS);
                for (AudioDeviceInfo output : outputs) {
                    int type = output.getType();
                    if (type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP
                            || type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
                            || (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                                && type == AudioDeviceInfo.TYPE_BLE_HEADSET)) {
                        bluetoothAudioConnected = true;
                    }
                    if (type == AudioDeviceInfo.TYPE_WIRED_HEADSET
                            || type == AudioDeviceInfo.TYPE_WIRED_HEADPHONES
                            || (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                                && type == AudioDeviceInfo.TYPE_USB_HEADSET)) {
                        wiredHeadphonesConnected = true;
                    }
                }
            }
            result.put("bluetoothAudioConnected", bluetoothAudioConnected);
            result.put("wiredHeadphonesConnected", wiredHeadphonesConnected);
            result.put("headphonesConnected", bluetoothAudioConnected || wiredHeadphonesConnected);

            // Report the phone's shared internal storage volume, not this app's private sandbox.
            File sharedStorage = Environment.getExternalStorageDirectory();
            StatFs storage = new StatFs(sharedStorage.getAbsolutePath());
            double storageFreeGb = storage.getAvailableBytes() / 1073741824.0;
            double storageTotalGb = storage.getTotalBytes() / 1073741824.0;
            result.put("storageFreeGb", storageFreeGb);
            result.put("storageTotalGb", storageTotalGb);
            result.put("storageScope", "DEVICE_SHARED_INTERNAL");

            ActivityManager manager = (ActivityManager) getContext().getSystemService(Context.ACTIVITY_SERVICE);
            if (manager != null) {
                ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
                manager.getMemoryInfo(memory);
                result.put("memoryAvailableGb", memory.availMem / 1073741824.0);
                result.put("memoryTotalGb", memory.totalMem / 1073741824.0);
                result.put("lowMemory", memory.lowMemory);
            }

            AudioManager phoneAudio = (AudioManager) getContext().getSystemService(Context.AUDIO_SERVICE);
            String ringerMode = "UNKNOWN";
            if (phoneAudio != null) {
                int mode = phoneAudio.getRingerMode();
                ringerMode = mode == AudioManager.RINGER_MODE_SILENT ? "SILENT"
                    : mode == AudioManager.RINGER_MODE_VIBRATE ? "VIBRATE" : "NORMAL";
            }
            NotificationManager notificationManager = (NotificationManager) getContext().getSystemService(Context.NOTIFICATION_SERVICE);
            boolean dndAccessGranted = Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                && notificationManager != null && notificationManager.isNotificationPolicyAccessGranted();
            String dndStatus = "UNKNOWN";
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && notificationManager != null && dndAccessGranted) {
                int filter = notificationManager.getCurrentInterruptionFilter();
                dndStatus = filter == NotificationManager.INTERRUPTION_FILTER_NONE ? "TOTAL_SILENCE"
                    : filter == NotificationManager.INTERRUPTION_FILTER_ALARMS ? "ALARMS_ONLY"
                    : filter == NotificationManager.INTERRUPTION_FILTER_PRIORITY ? "PRIORITY_ONLY"
                    : filter == NotificationManager.INTERRUPTION_FILTER_ALL ? "OFF" : "UNKNOWN";
            }
            PowerManager screenPower = (PowerManager) getContext().getSystemService(Context.POWER_SERVICE);
            boolean screenInteractive = screenPower != null && screenPower.isInteractive();
            KeyguardManager keyguard = (KeyguardManager) getContext().getSystemService(Context.KEYGUARD_SERVICE);
            boolean deviceLocked = keyguard != null && keyguard.isKeyguardLocked();
            result.put("ringerMode", ringerMode);
            result.put("dndAccessGranted", dndAccessGranted);
            result.put("dndStatus", dndStatus);
            result.put("screenInteractive", screenInteractive);
            result.put("deviceLocked", deviceLocked);

            result.put("deviceModel", Build.MANUFACTURER + " " + Build.MODEL);
            result.put("androidVersion", Build.VERSION.RELEASE);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                PowerManager power = (PowerManager) getContext().getSystemService(Context.POWER_SERVICE);
                if (power != null) {
                    int thermal = power.getCurrentThermalStatus();
                    String[] labels = {"NOMINAL", "LIGHT", "MODERATE", "SEVERE", "CRITICAL", "EMERGENCY", "SHUTDOWN"};
                    if (thermal >= 0 && thermal < labels.length) result.put("thermalStatus", labels[thermal]);
                }
            }
            call.resolve(result);
        } catch (Exception error) {
            call.reject("डिव्हाइसची माहिती मिळवता आली नाही.", error);
        }
    }
}
