package com.openjarvis.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;
import com.google.mlkit.vision.label.ImageLabel;
import com.google.mlkit.vision.label.ImageLabeler;
import com.google.mlkit.vision.label.ImageLabeling;
import com.google.mlkit.vision.label.defaults.ImageLabelerOptions;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;

import androidx.activity.result.ActivityResult;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions;

@CapacitorPlugin(name = "ScreenUnderstanding")
public class ScreenUnderstandingPlugin extends Plugin {
    private PluginCall pendingCall;
    private BroadcastReceiver resultReceiver;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable timeout;
    private TextRecognizer imageDevanagariRecognizer;
    private TextRecognizer imageLatinRecognizer;
    private ImageLabeler imageLabeler;
    private PdfRenderer pdfRenderer;
    private ParcelFileDescriptor pdfDescriptor;
    private TextRecognizer pdfDevanagariRecognizer;
    private TextRecognizer pdfLatinRecognizer;
    private final StringBuilder pdfText = new StringBuilder();
    private int pdfPageIndex = 0;
    private int pdfPageCount = 0;
    private int pdfTotalPageCount = 0;

    @PluginMethod
    public void captureAndReadScreen(PluginCall call) {
        if (pendingCall != null) {
            call.reject("स्क्रीन वाचण्याची विनंती आधीच सुरू आहे.");
            return;
        }
        MediaProjectionManager manager = (MediaProjectionManager)
                getContext().getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        if (manager == null) {
            call.reject("या Android आवृत्तीत Screen Capture उपलब्ध नाही.");
            return;
        }
        pendingCall = call;
        startActivityForResult(call, manager.createScreenCaptureIntent(), "screenPermissionResult");
    }

    @PluginMethod
    public void pickImageAndRead(PluginCall call) {
        if (pendingCall != null) {
            call.reject("दुसरी वाचन विनंती आधीच सुरू आहे.");
            return;
        }
        pendingCall = call;
        Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.setType("image/*");
        try {
            startActivityForResult(call, picker, "imagePermissionResult");
        } catch (Exception e) {
            pendingCall = null;
            call.reject("फोटो निवडता आला नाही: " + e.getMessage());
        }
    }

    @PluginMethod
    public void pickImageAndDescribe(PluginCall call) {
        if (pendingCall != null) {
            call.reject("दुसरी वाचन विनंती आधीच सुरू आहे.");
            return;
        }
        pendingCall = call;
        Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.setType("image/*");
        try {
            startActivityForResult(call, picker, "imageDescriptionResult");
        } catch (Exception e) {
            pendingCall = null;
            call.reject("फोटो निवडता आला नाही: " + e.getMessage());
        }
    }

    @PluginMethod
    public void pickPdfAndRead(PluginCall call) {
        if (pendingCall != null) {
            call.reject("दुसरी वाचन विनंती आधीच सुरू आहे.");
            return;
        }
        pendingCall = call;
        Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.setType("application/pdf");
        try {
            startActivityForResult(call, picker, "pdfDocumentResult");
        } catch (Exception e) {
            pendingCall = null;
            call.reject("PDF निवडता आला नाही: " + e.getMessage());
        }
    }

    @ActivityCallback
    private void pdfDocumentResult(PluginCall call, ActivityResult result) {
        if (pendingCall == null) return;
        if (result == null || result.getResultCode() != android.app.Activity.RESULT_OK
                || result.getData() == null || result.getData().getData() == null) {
            finishWithError("PDF निवडणे रद्द केले.");
            return;
        }
        try {
            Uri uri = result.getData().getData();
            pdfDescriptor = getContext().getContentResolver().openFileDescriptor(uri, "r");
            if (pdfDescriptor == null) throw new IllegalStateException("PDF फाइल उघडता आली नाही.");
            pdfRenderer = new PdfRenderer(pdfDescriptor);
            pdfTotalPageCount = pdfRenderer.getPageCount();
            pdfPageCount = Math.min(pdfTotalPageCount, 10);
            if (pdfPageCount == 0) throw new IllegalStateException("PDF मध्ये पृष्ठे नाहीत.");
            pdfPageIndex = 0;
            pdfText.setLength(0);
            pdfDevanagariRecognizer = TextRecognition.getClient(
                    new DevanagariTextRecognizerOptions.Builder().build());
            pdfLatinRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            timeout = () -> finishWithError("PDF वाचण्यासाठी वेळ लागला. लहान PDF पुन्हा निवडा.");
            handler.postDelayed(timeout, 90000);
            readNextPdfPage();
        } catch (Exception e) {
            finishWithError("PDF वाचता आला नाही: " + e.getMessage());
        }
    }

    private void readNextPdfPage() {
        if (pendingCall == null || pdfRenderer == null) return;
        if (pdfPageIndex >= pdfPageCount) {
            if (timeout != null) handler.removeCallbacks(timeout);
            String result = pdfText.toString().trim();
            closePdfResources();
            PluginCall call = pendingCall;
            pendingCall = null;
            if (result.isEmpty()) {
                call.reject("PDF मधून वाचता येण्याजोगा मजकूर मिळाला नाही.");
                return;
            }
            JSObject response = new JSObject();
            response.put("text", result);
            response.put("message", "PDF मधील मजकूर वाचला.");
            response.put("pagesRead", pdfPageCount);
            response.put("totalPages", pdfTotalPageCount);
            call.resolve(response);
            return;
        }
        PdfRenderer.Page page = null;
        try {
            page = pdfRenderer.openPage(pdfPageIndex);
            int width = Math.max(1, Math.min(page.getWidth(), 1600));
            int height = Math.max(1, Math.min(page.getHeight(), 2200));
            Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
            bitmap.eraseColor(Color.WHITE);
            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
            page.close();
            final int currentPage = pdfPageIndex + 1;
            final Bitmap pageBitmap = bitmap;
            final String[] devanagari = {""};
            final String[] latin = {""};
            final int[] completed = {0};
            Runnable finishPage = () -> {
                completed[0]++;
                if (completed[0] != 2) return;
                if (pdfText.length() > 0) pdfText.append("\n\n");
                pdfText.append("पृष्ठ ").append(currentPage).append("\n");
                if (!devanagari[0].isEmpty()) pdfText.append(devanagari[0]).append("\n");
                if (!latin[0].isEmpty() && !latin[0].equals(devanagari[0])) pdfText.append(latin[0]);
                pageBitmap.recycle();
                pdfPageIndex++;
                readNextPdfPage();
            };
            InputImage input = InputImage.fromBitmap(pageBitmap, 0);
            pdfDevanagariRecognizer.process(input)
                    .addOnSuccessListener(value -> devanagari[0] = value.getText())
                    .addOnCompleteListener(task -> finishPage.run());
            pdfLatinRecognizer.process(input)
                    .addOnSuccessListener(value -> latin[0] = value.getText())
                    .addOnCompleteListener(task -> finishPage.run());
        } catch (Exception e) {
            if (page != null) page.close();
            finishWithError("PDF पृष्ठ वाचताना त्रुटी: " + e.getMessage());
        }
    }

    private void closePdfResources() {
        if (pdfDevanagariRecognizer != null) { pdfDevanagariRecognizer.close(); pdfDevanagariRecognizer = null; }
        if (pdfLatinRecognizer != null) { pdfLatinRecognizer.close(); pdfLatinRecognizer = null; }
        if (pdfRenderer != null) { try { pdfRenderer.close(); } catch (Exception ignored) {} pdfRenderer = null; }
        if (pdfDescriptor != null) { try { pdfDescriptor.close(); } catch (Exception ignored) {} pdfDescriptor = null; }
    }

    @ActivityCallback
    private void imageDescriptionResult(PluginCall call, ActivityResult result) {
        if (pendingCall == null) return;
        if (result == null || result.getResultCode() != android.app.Activity.RESULT_OK
                || result.getData() == null || result.getData().getData() == null) {
            finishWithError("फोटो निवडणे रद्द केले.");
            return;
        }
        try {
            InputImage image = InputImage.fromFilePath(getContext(), result.getData().getData());
            imageLabeler = ImageLabeling.getClient(ImageLabelerOptions.DEFAULT_OPTIONS);
            timeout = () -> finishWithError("फोटोचे विश्लेषण करण्यासाठी वेळ लागला. पुन्हा प्रयत्न करा.");
            handler.postDelayed(timeout, 20000);
            imageLabeler.process(image)
                    .addOnSuccessListener(labels -> {
                        if (timeout != null) handler.removeCallbacks(timeout);
                        StringBuilder description = new StringBuilder();
                        for (ImageLabel label : labels) {
                            if (label.getConfidence() >= 0.45f) {
                                if (description.length() > 0) description.append("\n");
                                description.append(label.getText()).append(" (")
                                        .append(Math.round(label.getConfidence() * 100)).append("%)");
                            }
                        }
                        closeImageLabeler();
                        PluginCall pending = pendingCall;
                        pendingCall = null;
                        if (pending == null) return;
                        if (description.length() == 0) {
                            pending.reject("फोटोतील वस्तू किंवा दृश्य ओळखता आले नाही.");
                            return;
                        }
                        JSObject response = new JSObject();
                        response.put("text", description.toString());
                        response.put("message", "फोटोतील दृश्याचे विश्लेषण पूर्ण.");
                        pending.resolve(response);
                    })
                    .addOnFailureListener(error -> finishWithError("फोटोचे विश्लेषण करता आले नाही: " + error.getMessage()));
        } catch (Exception e) {
            closeImageLabeler();
            finishWithError("फोटो उघडता आला नाही: " + e.getMessage());
        }
    }

    @ActivityCallback
    private void imagePermissionResult(PluginCall call, ActivityResult result) {
        if (pendingCall == null) return;
        if (result == null || result.getResultCode() != android.app.Activity.RESULT_OK
                || result.getData() == null || result.getData().getData() == null) {
            finishWithError("फोटो निवडणे रद्द केले.");
            return;
        }
        Uri uri = result.getData().getData();
        try {
            InputImage image = InputImage.fromFilePath(getContext(), uri);
            imageDevanagariRecognizer = TextRecognition.getClient(
                    new DevanagariTextRecognizerOptions.Builder().build());
            imageLatinRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            final String[] devanagariText = {""};
            final String[] latinText = {""};
            final boolean[] success = {false};
            final int[] completed = {0};
            Runnable combine = () -> {
                completed[0]++;
                if (completed[0] != 2) return;
                if (timeout != null) handler.removeCallbacks(timeout);
                String text = (devanagariText[0] + "\n" + latinText[0]).trim();
                closeImageRecognizers();
                PluginCall pending = pendingCall;
                pendingCall = null;
                if (pending == null) return;
                if (!success[0] || text.isEmpty()) {
                    pending.reject("फोटोमध्ये वाचता येण्याजोगा मजकूर आढळला नाही.");
                    return;
                }
                JSObject response = new JSObject();
                response.put("text", text);
                response.put("message", "फोटोवरील मजकूर वाचला.");
                pending.resolve(response);
            };
            imageDevanagariRecognizer.process(image)
                    .addOnSuccessListener(value -> { devanagariText[0] = value.getText(); success[0] = true; })
                    .addOnCompleteListener(task -> combine.run());
            imageLatinRecognizer.process(image)
                    .addOnSuccessListener(value -> { latinText[0] = value.getText(); success[0] = true; })
                    .addOnCompleteListener(task -> combine.run());
            timeout = () -> finishWithError("फोटोमधील मजकूर वाचण्यासाठी वेळ लागला. पुन्हा प्रयत्न करा.");
            handler.postDelayed(timeout, 20000);
        } catch (Exception e) {
            closeImageRecognizers();
            finishWithError("फोटो वाचता आला नाही: " + e.getMessage());
        }
    }

    @ActivityCallback
    private void screenPermissionResult(PluginCall call, ActivityResult result) {
        if (pendingCall == null) return;
        if (result == null || result.getResultCode() != android.app.Activity.RESULT_OK
                || result.getData() == null) {
            finishWithError("तुम्ही स्क्रीन पाहण्याची परवानगी दिली नाही.");
            return;
        }

        registerResultReceiver();
        Intent service = new Intent(getContext(), ShivamScreenCaptureService.class);
        service.putExtra(ShivamScreenCaptureService.EXTRA_RESULT_CODE, result.getResultCode());
        service.putExtra(ShivamScreenCaptureService.EXTRA_RESULT_DATA, result.getData());
        try {
            if (Build.VERSION.SDK_INT >= 26) getContext().startForegroundService(service);
            else getContext().startService(service);
            timeout = () -> finishWithError("स्क्रीनमधील मजकूर वाचण्यासाठी वेळ लागला. पुन्हा प्रयत्न करा.");
            handler.postDelayed(timeout, 20000);
        } catch (Exception e) {
            finishWithError("Screen Capture सुरू करता आले नाही: " + e.getMessage());
        }
    }

    private void registerResultReceiver() {
        resultReceiver = new BroadcastReceiver() {
            @Override public void onReceive(Context context, Intent intent) {
                if (timeout != null) handler.removeCallbacks(timeout);
                String text = intent.getStringExtra(ShivamScreenCaptureService.EXTRA_TEXT);
                boolean ok = intent.getBooleanExtra(ShivamScreenCaptureService.EXTRA_SUCCESS, false);
                unregisterResultReceiver();
                PluginCall call = pendingCall;
                pendingCall = null;
                if (call == null) return;
                if (!ok) {
                    call.reject(text == null ? "स्क्रीन वाचता आली नाही." : text);
                    return;
                }
                JSObject response = new JSObject();
                response.put("text", text == null ? "" : text);
                response.put("message", "स्क्रीनवरील मजकूर वाचला.");
                call.resolve(response);
            }
        };
        IntentFilter filter = new IntentFilter(ShivamScreenCaptureService.ACTION_RESULT);
        if (Build.VERSION.SDK_INT >= 33) getContext().registerReceiver(resultReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        else getContext().registerReceiver(resultReceiver, filter);
    }

    private void closeImageLabeler() {
        if (imageLabeler != null) { imageLabeler.close(); imageLabeler = null; }
    }

    private void closeImageRecognizers() {
        if (imageDevanagariRecognizer != null) { imageDevanagariRecognizer.close(); imageDevanagariRecognizer = null; }
        if (imageLatinRecognizer != null) { imageLatinRecognizer.close(); imageLatinRecognizer = null; }
    }

    private void finishWithError(String message) {
        closeImageRecognizers();
        closeImageLabeler();
        closePdfResources();
        if (timeout != null) handler.removeCallbacks(timeout);
        try {
            getContext().stopService(new Intent(getContext(), ShivamScreenCaptureService.class));
        } catch (Exception ignored) {}
        unregisterResultReceiver();
        PluginCall call = pendingCall;
        pendingCall = null;
        if (call != null) call.reject(message);
    }

    private void unregisterResultReceiver() {
        if (resultReceiver != null) {
            try { getContext().unregisterReceiver(resultReceiver); } catch (Exception ignored) {}
            resultReceiver = null;
        }
    }

    @Override
    protected void handleOnDestroy() {
        if (timeout != null) handler.removeCallbacks(timeout);
        unregisterResultReceiver();
        closeImageRecognizers();
        closeImageLabeler();
        closePdfResources();
        if (pendingCall != null) {
            pendingCall.reject("SHIVAM बंद झाले.");
            pendingCall = null;
        }
        super.handleOnDestroy();
    }
}
