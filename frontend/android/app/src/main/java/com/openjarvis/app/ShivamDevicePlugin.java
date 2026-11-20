package com.openjarvis.app;

import android.app.ActivityManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import android.os.StatFs;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.wifi.WifiManager;

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

            StatFs storage = new StatFs(getContext().getFilesDir().getAbsolutePath());
            result.put("storageFreeGb", storage.getAvailableBytes() / 1073741824.0);
            result.put("storageTotalGb", storage.getTotalBytes() / 1073741824.0);

            ActivityManager manager = (ActivityManager) getContext().getSystemService(Context.ACTIVITY_SERVICE);
            if (manager != null) {
                ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
                manager.getMemoryInfo(memory);
                result.put("memoryAvailableGb", memory.availMem / 1073741824.0);
                result.put("memoryTotalGb", memory.totalMem / 1073741824.0);
                result.put("lowMemory", memory.lowMemory);
            }

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
