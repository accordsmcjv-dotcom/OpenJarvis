package com.openjarvis.app;
import android.content.Intent;
import androidx.core.content.ContextCompat;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
@CapacitorPlugin(name="ShivamWakeWord")
public class ShivamWakeWordPlugin extends Plugin {
 @PluginMethod public void startListening(PluginCall call) {
  if(getContext().checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=android.content.pm.PackageManager.PERMISSION_GRANTED){call.reject("Microphone permission is required");return;}
  Intent i=new Intent(getContext(),ShivamWakeWordService.class); i.setAction(ShivamWakeWordService.ACTION_START);
  try{ContextCompat.startForegroundService(getContext(),i);call.resolve();}catch(Exception e){call.reject("Could not start voice service: "+e.getMessage());}
 }
 @PluginMethod public void stopListening(PluginCall call){getContext().stopService(new Intent(getContext(),ShivamWakeWordService.class));call.resolve();}
}