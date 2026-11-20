package com.openjarvis.app;

import android.Manifest;
import android.content.Context;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Looper;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

@CapacitorPlugin(
    name = "ShivamLocation",
    permissions = {
        @Permission(alias = "location", strings = {
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.ACCESS_FINE_LOCATION
        })
    }
)
public class ShivamLocationPlugin extends Plugin {
    @PluginMethod
    public void getCurrentLocation(PluginCall call) {
        if (getPermissionState("location") != com.getcapacitor.PermissionState.GRANTED) {
            requestPermissionForAlias("location", call, "locationPermissionCallback");
            return;
        }
        readCurrentLocation(call);
    }

    @PermissionCallback
    private void locationPermissionCallback(PluginCall call) {
        if (getPermissionState("location") != com.getcapacitor.PermissionState.GRANTED) {
            call.reject("स्थान मिळवण्यासाठी Location परवानगी आवश्यक आहे.");
            return;
        }
        readCurrentLocation(call);
    }

    private void readCurrentLocation(PluginCall call) {
        try {
            LocationManager manager = (LocationManager) getContext().getSystemService(Context.LOCATION_SERVICE);
            if (manager == null) {
                call.reject("फोनचे Location सेवा उपलब्ध नाही.");
                return;
            }
            boolean fineGranted = getContext().checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                == android.content.pm.PackageManager.PERMISSION_GRANTED;
            String provider = fineGranted && manager.isProviderEnabled(LocationManager.GPS_PROVIDER)
                ? LocationManager.GPS_PROVIDER : LocationManager.NETWORK_PROVIDER;
            if (!manager.isProviderEnabled(provider)) {
                call.reject("फोनची Location सुविधा सुरू करा किंवा अचूक स्थानाची परवानगी द्या.");
                return;
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                manager.getCurrentLocation(provider, null, getActivity().getMainExecutor(), location -> {
                    if (location == null) {
                        call.reject("सध्याचे स्थान मिळाले नाही. पुन्हा प्रयत्न करा.");
                        return;
                    }
                    resolveLocation(call, location);
                });
            } else {
                manager.requestSingleUpdate(provider, new LocationListener() {
                    @Override public void onLocationChanged(Location location) { resolveLocation(call, location); }
                    @Override public void onStatusChanged(String name, int status, Bundle extras) {}
                    @Override public void onProviderEnabled(String name) {}
                    @Override public void onProviderDisabled(String name) {
                        call.reject("Location सेवा बंद आहे.");
                    }
                }, Looper.getMainLooper());
            }
        } catch (SecurityException error) {
            call.reject("Location परवानगी उपलब्ध नाही.", error);
        } catch (Exception error) {
            call.reject("सध्याचे स्थान मिळवता आले नाही.", error);
        }
    }

    private void resolveLocation(PluginCall call, Location location) {
        JSObject result = new JSObject();
        result.put("latitude", location.getLatitude());
        result.put("longitude", location.getLongitude());
        result.put("accuracy", location.hasAccuracy() ? location.getAccuracy() : -1);
        call.resolve(result);
    }
}
