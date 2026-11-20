package com.openjarvis.app;

import android.Manifest;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.provider.ContactsContract;
import android.text.TextUtils;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

@CapacitorPlugin(
    name = "ContactsCall",
    permissions = {
        @Permission(alias = "contacts", strings = { Manifest.permission.READ_CONTACTS }),
        @Permission(alias = "call", strings = { Manifest.permission.CALL_PHONE })
    }
)
public class ContactsCallPlugin extends Plugin {
    @PluginMethod
    public void findContacts(PluginCall call) {
        String query = call.getString("query", "").trim();
        if (query.length() < 2 || query.length() > 80) {
            call.reject("संपर्क शोधण्यासाठी किमान दोन अक्षरे आवश्यक आहेत.");
            return;
        }
        if (getPermissionState("contacts") != com.getcapacitor.PermissionState.GRANTED) {
            requestPermissionForAlias("contacts", call, "contactsPermissionCallback");
            return;
        }
        searchContacts(call, query);
    }

    @PermissionCallback
    private void contactsPermissionCallback(PluginCall call) {
        if (getPermissionState("contacts") != com.getcapacitor.PermissionState.GRANTED) {
            call.reject("संपर्क वाचण्याची Android परवानगी दिलेली नाही.");
            return;
        }
        searchContacts(call, call.getString("query", "").trim());
    }

    private void searchContacts(PluginCall call, String query) {
        Cursor cursor = null;
        try {
            String selection = ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " LIKE ?";
            String[] selectionArgs = new String[] { "%" + query.replace("%", "\\%").replace("_", "\\_") + "%" };
            cursor = getContext().getContentResolver().query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                new String[] {
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER
                },
                selection,
                selectionArgs,
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " COLLATE NOCASE ASC"
            );
            JSArray matches = new JSArray();
            java.util.HashSet<String> seen = new java.util.HashSet<>();
            if (cursor != null) {
                int nameIndex = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME);
                int numberIndex = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER);
                while (cursor.moveToNext() && matches.length() < 10) {
                    String name = cursor.getString(nameIndex);
                    String number = cursor.getString(numberIndex);
                    if (TextUtils.isEmpty(name) || TextUtils.isEmpty(number)) continue;
                    String key = name.trim().toLowerCase(java.util.Locale.ROOT) + "|" + number.replaceAll("\\s+", "");
                    if (!seen.add(key)) continue;
                    JSObject item = new JSObject();
                    item.put("name", name.trim());
                    item.put("number", number.trim());
                    matches.put(item);
                }
            }
            JSObject result = new JSObject();
            result.put("contacts", matches);
            result.put("count", matches.length());
            call.resolve(result);
        } catch (Exception error) {
            call.reject("संपर्क शोधता आले नाहीत.", error);
        } finally {
            if (cursor != null) cursor.close();
        }
    }

    // This method must only be invoked after SHIVAM has obtained an explicit
    // affirmative response from the user for this specific contact/number.
    @PluginMethod
    public void placeCall(PluginCall call) {
        String number = call.getString("number", "").trim();
        if (number.isEmpty() || number.length() > 40 || !number.matches("[+0-9*#,;() .-]+")) {
            call.reject("फोन क्रमांक अवैध आहे.");
            return;
        }
        if (getPermissionState("call") != com.getcapacitor.PermissionState.GRANTED) {
            requestPermissionForAlias("call", call, "callPermissionCallback");
            return;
        }
        startCall(call, number);
    }

    @PermissionCallback
    private void callPermissionCallback(PluginCall call) {
        if (getPermissionState("call") != com.getcapacitor.PermissionState.GRANTED) {
            call.reject("फोन कॉल करण्याची Android परवानगी दिलेली नाही.");
            return;
        }
        startCall(call, call.getString("number", "").trim());
    }

    private void startCall(PluginCall call, String number) {
        try {
            Intent intent = new Intent(Intent.ACTION_CALL, Uri.fromParts("tel", number, null));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            JSObject result = new JSObject();
            result.put("success", true);
            result.put("message", "कॉल सुरू केला आहे.");
            call.resolve(result);
        } catch (SecurityException error) {
            call.reject("कॉलसाठी Android परवानगी आवश्यक आहे.", error);
        } catch (Exception error) {
            call.reject("कॉल सुरू करता आला नाही.", error);
        }
    }
}
