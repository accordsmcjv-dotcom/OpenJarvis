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
        @Permission(alias = "call", strings = { Manifest.permission.CALL_PHONE }),
        @Permission(alias = "sms", strings = { Manifest.permission.SEND_SMS })
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
    // Sends SMS only after SHIVAM has confirmed the exact recipient and text.
    @PluginMethod
    public void sendSms(PluginCall call) {
        String number = call.getString("number", "").trim();
        String message = call.getString("message", "").trim();
        String digits = number.replaceAll("[^0-9]", "");
        if (digits.length() < 7 || digits.length() > 15 || message.isEmpty() || message.length() > 4000) {
            call.reject("फोन नंबर किंवा मेसेज योग्य नाही.");
            return;
        }
        if (getPermissionState("sms") != com.getcapacitor.PermissionState.GRANTED) {
            requestPermissionForAlias("sms", call, "smsPermissionCallback");
            return;
        }
        sendSmsNow(call, number, message);
    }

    @PermissionCallback
    private void smsPermissionCallback(PluginCall call) {
        if (getPermissionState("sms") != com.getcapacitor.PermissionState.GRANTED) {
            call.reject("SMS पाठवण्याची Android परवानगी दिलेली नाही.");
            return;
        }
        sendSmsNow(call, call.getString("number", "").trim(), call.getString("message", "").trim());
    }

    private void sendSmsNow(PluginCall call, String number, String message) {
        try {
            android.telephony.SmsManager smsManager = android.telephony.SmsManager.getDefault();
            java.util.ArrayList<String> parts = smsManager.divideMessage(message);
            if (parts.size() > 1) {
                smsManager.sendMultipartTextMessage(number, null, parts, null, null);
            } else {
                smsManager.sendTextMessage(number, null, message, null, null);
            }
            JSObject result = new JSObject();
            result.put("success", true);
            result.put("message", "SMS पाठवण्याची विनंती मोबाईल नेटवर्ककडे दिली आहे.");
            call.resolve(result);
        } catch (Exception error) {
            call.reject("SMS पाठवता आला नाही. SIM, नेटवर्क आणि SMS परवानगी तपासा.", error);
        }
    }

    // Finds the first YouTube video for a spoken request, then opens its watch
    // page in the official app so playback can start directly.
    @PluginMethod
    public void searchYouTube(PluginCall call) {
        final String query = call.getString("query", "").trim();
        if (query.length() < 2 || query.length() > 200) {
            call.reject("गाण्याचे किंवा व्हिडिओचे नाव स्पष्ट सांगा.");
            return;
        }
        if (!isYouTubeInstalled()) {
            call.reject("YouTube अॅप सापडले नाही. कृपया YouTube स्थापित किंवा अपडेट करा.");
            return;
        }
        new Thread(() -> {
            String videoId = null;
            try {
                java.net.URL url = new java.net.URL(
                    "https://www.youtube.com/results?search_query=" +
                    java.net.URLEncoder.encode(query, "UTF-8")
                );
                java.net.HttpURLConnection connection =
                    (java.net.HttpURLConnection) url.openConnection();
                connection.setRequestMethod("GET");
                connection.setConnectTimeout(8000);
                connection.setReadTimeout(10000);
                connection.setInstanceFollowRedirects(true);
                connection.setRequestProperty("User-Agent",
                    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36");
                connection.setRequestProperty("Accept-Language", "mr-IN,mr;q=0.9,en;q=0.8");
                try (java.io.InputStream input = connection.getInputStream();
                     java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {
                    byte[] buffer = new byte[8192];
                    int read;
                    int total = 0;
                    while ((read = input.read(buffer)) != -1 && total < 2 * 1024 * 1024) {
                        output.write(buffer, 0, read);
                        total += read;
                    }
                    String html = output.toString("UTF-8");
                    java.util.regex.Matcher matcher = java.util.regex.Pattern
                        .compile("\\\"videoId\\\"\\s*:\\s*\\\"([A-Za-z0-9_-]{11})\\\"")
                        .matcher(html);
                    if (matcher.find()) videoId = matcher.group(1);
                } finally {
                    connection.disconnect();
                }
            } catch (Exception ignored) {
                // If YouTube blocks search extraction, open search results as a safe fallback.
            }

            final String selectedVideoId = videoId;
            getActivity().runOnUiThread(() -> {
                try {
                    Uri uri = selectedVideoId != null
                        ? Uri.parse("https://www.youtube.com/watch?v=" + selectedVideoId)
                        : Uri.parse("https://www.youtube.com/results?search_query=" + Uri.encode(query));
                    Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                    intent.setPackage("com.google.android.youtube");
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    getContext().startActivity(intent);
                    JSObject result = new JSObject();
                    result.put("success", true);
                    result.put("autoplay", selectedVideoId != null);
                    result.put("message", selectedVideoId != null
                        ? "पहिला व्हिडिओ YouTube मध्ये उघडला आहे."
                        : "व्हिडिओ आपोआप निवडता आला नाही; YouTube शोध उघडला आहे.");
                    call.resolve(result);
                } catch (Exception error) {
                    call.reject("YouTube व्हिडिओ उघडता आला नाही.", error);
                }
            });
        }).start();
    }

    private boolean isYouTubeInstalled() {
        Intent launch = getContext().getPackageManager()
            .getLaunchIntentForPackage("com.google.android.youtube");
        return launch != null;
    }

    // Opens a user-visible composer only after SHIVAM has confirmed the
    // recipient and exact message. The user completes the final Send action.
    @PluginMethod
    public void openMessageComposer(PluginCall call) {
        String channel = call.getString("channel", "").trim().toLowerCase(java.util.Locale.ROOT);
        String number = call.getString("number", "").trim();
        String message = call.getString("message", "").trim();
        String digits = number.replaceAll("[^0-9]", "");
        if (channel.equals("whatsapp") && digits.length() == 10) digits = "91" + digits;
        if (!(channel.equals("sms") || channel.equals("whatsapp"))) {
            call.reject("मेसेजचा प्रकार SMS किंवा WhatsApp असावा.");
            return;
        }
        if (digits.length() < 7 || digits.length() > 15 || message.isEmpty() || message.length() > 4000) {
            call.reject("फोन नंबर किंवा मेसेज योग्य नाही.");
            return;
        }
        try {
            Intent intent;
            if (channel.equals("sms")) {
                intent = new Intent(Intent.ACTION_SENDTO, Uri.fromParts("smsto", number, null));
                intent.putExtra("sms_body", message);
            } else {
                Uri uri = Uri.parse("https://wa.me/" + digits + "?text=" + Uri.encode(message));
                intent = new Intent(Intent.ACTION_VIEW, uri);
                // Personal WhatsApp only. Never fall back to WhatsApp Business
                // or a generic handler, so the user's chosen app stays explicit.
                intent.setPackage("com.whatsapp");
                if (intent.resolveActivity(getContext().getPackageManager()) == null) {
                    call.reject("वैयक्तिक WhatsApp स्थापित नाही. कृपया WhatsApp अॅप तपासा.");
                    return;
                }
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            JSObject result = new JSObject();
            result.put("success", true);
            result.put("message", "मेसेज तयार केला आहे. पाठवण्यासाठी अॅपमधील Send बटण दाबा.");
            call.resolve(result);
        } catch (Exception error) {
            call.reject(channel.equals("whatsapp")
                ? "WhatsApp उघडता आले नाही. WhatsApp स्थापित आहे का ते तपासा."
                : "SMS अॅप उघडता आले नाही.", error);
        }
    }

}
