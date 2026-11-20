package com.openjarvis.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.Rect;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import androidx.annotation.Nullable;

import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions;

import java.nio.ByteBuffer;

public class ShivamScreenCaptureService extends Service {
    static final String ACTION_RESULT = "com.openjarvis.app.SCREEN_TEXT_RESULT";
    static final String EXTRA_RESULT_CODE = "resultCode";
    static final String EXTRA_RESULT_DATA = "resultData";
    static final String EXTRA_TEXT = "screenText";
    static final String EXTRA_SUCCESS = "success";
    private static final String CHANNEL = "shivam_screen_capture";
    private static final int NOTIFICATION_ID = 7403;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private MediaProjection projection;
    private VirtualDisplay display;
    private ImageReader imageReader;
    private TextRecognizer devanagariRecognizer;
    private TextRecognizer latinRecognizer;
    private boolean processing = false;
    private boolean finished = false;

    @Override public void onCreate() {
        super.onCreate();
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL, "SHIVAM Screen Understanding", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Visible notification while SHIVAM reads the screen you selected.");
            ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(channel);
        }
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || !intent.hasExtra(EXTRA_RESULT_DATA)) {
            finish(false, "स्क्रीन परवानगीची माहिती मिळाली नाही.");
            return START_NOT_STICKY;
        }
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        Notification notification = builder
                .setContentTitle("SHIVAM स्क्रीन समजून घेत आहे")
                .setContentText("तुमच्या परवानगीने स्क्रीनवरील मजकूर वाचत आहे.")
                .setSmallIcon(android.R.drawable.ic_menu_view)
                .setOngoing(true).build();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
        try {
            MediaProjectionManager manager = (MediaProjectionManager) getSystemService(MEDIA_PROJECTION_SERVICE);
            projection = manager.getMediaProjection(
                    intent.getIntExtra(EXTRA_RESULT_CODE, 0),
                    (Intent) intent.getParcelableExtra(EXTRA_RESULT_DATA));
            if (projection == null) {
                finish(false, "Android ने स्क्रीन कॅप्चर सुरू केले नाही.");
                return START_NOT_STICKY;
            }
            projection.registerCallback(new MediaProjection.Callback() {
                @Override public void onStop() { finish(false, "स्क्रीन कॅप्चर थांबवले गेले."); }
            }, handler);

            android.util.DisplayMetrics metrics = getResources().getDisplayMetrics();
            int width = metrics.widthPixels;
            int height = metrics.heightPixels;
            int density = metrics.densityDpi;
            imageReader = ImageReader.newInstance(width, height, android.graphics.PixelFormat.RGBA_8888, 2);
            display = projection.createVirtualDisplay("SHIVAM-Screen-Read", width, height, density,
                    DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, imageReader.getSurface(), null, handler);
            devanagariRecognizer = TextRecognition.getClient(new DevanagariTextRecognizerOptions.Builder().build());
            latinRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            imageReader.setOnImageAvailableListener(reader -> {
                if (finished || processing) return;
                Image image = reader.acquireLatestImage();
                if (image == null) return;
                try {
                    Bitmap bitmap = imageToBitmap(image);
                    if (bitmap == null) {
                        finish(false, "स्क्रीन प्रतिमा तयार करता आली नाही.");
                        return;
                    }
                    processing = true;
                    InputImage input = InputImage.fromBitmap(bitmap, 0);
                    final String[] devanagariText = {""};
                    final String[] latinText = {""};
                    final int[] completed = {0};
                    final boolean[] anySuccess = {false};
                    Runnable combine = () -> {
                        completed[0]++;
                        if (completed[0] == 2) {
                            if (!finished) {
                                String combined = (devanagariText[0] + "\n" + latinText[0]).trim();
                                finish(anySuccess[0], combined.isEmpty() ? "स्क्रीनवर वाचता येण्याजोगा मजकूर आढळला नाही." : combined);
                            }
                            if (!bitmap.isRecycled()) bitmap.recycle();
                        }
                    };
                    devanagariRecognizer.process(input)
                            .addOnSuccessListener(result -> { devanagariText[0] = formatScreenLayout(result, bitmap.getWidth(), bitmap.getHeight()); anySuccess[0] = true; })
                            .addOnCompleteListener(task -> combine.run());
                    latinRecognizer.process(input)
                            .addOnSuccessListener(result -> { latinText[0] = formatScreenLayout(result, bitmap.getWidth(), bitmap.getHeight()); anySuccess[0] = true; })
                            .addOnCompleteListener(task -> combine.run());
                } catch (Exception e) {
                    finish(false, "स्क्रीन वाचताना त्रुटी: " + e.getMessage());
                } finally {
                    image.close();
                }
            }, handler);
            handler.postDelayed(() -> {
                if (!finished) finish(false, "स्क्रीन प्रतिमा मिळाली नाही. पुन्हा प्रयत्न करा.");
            }, 8000);
        } catch (SecurityException e) {
            finish(false, "Android ने स्क्रीन कॅप्चरची परवानगी नाकारली.");
        } catch (Exception e) {
            finish(false, "Screen Understanding सुरू करता आले नाही: " + e.getMessage());
        }
        return START_NOT_STICKY;
    }

    private String formatScreenLayout(Text result, int width, int height) {
        if (result == null || result.getText().trim().isEmpty()) return "";
        StringBuilder out = new StringBuilder();
        out.append("स्क्रीनवरील मजकूर व मांडणी:\\n");
        int count = 0;
        for (Text.TextBlock block : result.getTextBlocks()) {
            for (Text.Line line : block.getLines()) {
                if (count++ >= 80) break;
                String value = line.getText() == null ? "" : line.getText().trim();
                if (value.isEmpty()) continue;
                android.graphics.Rect bounds = line.getBoundingBox();
                String region = "मधला भाग";
                if (bounds != null) {
                    float centerY = (bounds.top + bounds.bottom) / 2f;
                    if (centerY < height * 0.25f) region = "वरचा भाग";
                    else if (centerY > height * 0.75f) region = "खालचा भाग";
                    float x = Math.max(0f, Math.min(100f, bounds.centerX() * 100f / Math.max(1, width)));
                    float y = Math.max(0f, Math.min(100f, centerY * 100f / Math.max(1, height)));
                    out.append("• [").append(region).append("; x=")
                            .append(Math.round(x)).append("%, y=").append(Math.round(y))
                            .append("%] ").append(value).append("\\n");
                } else {
                    out.append("• [").append(region).append("] ").append(value).append("\\n");
                }
            }
            if (count >= 80) break;
        }
        return out.toString().trim();
    }

    private Bitmap imageToBitmap(Image image) {
        Image.Plane[] planes = image.getPlanes();
        if (planes.length == 0) return null;
        int width = image.getWidth(), height = image.getHeight();
        int pixelStride = planes[0].getPixelStride();
        int rowStride = planes[0].getRowStride();
        int rowPadding = rowStride - pixelStride * width;
        int paddedWidth = width + rowPadding / pixelStride;
        Bitmap padded = Bitmap.createBitmap(paddedWidth, height, Bitmap.Config.ARGB_8888);
        ByteBuffer buffer = planes[0].getBuffer();
        buffer.rewind();
        padded.copyPixelsFromBuffer(buffer);
        if (paddedWidth == width) return padded;
        Bitmap cropped = Bitmap.createBitmap(padded, 0, 0, width, height);
        padded.recycle();
        return cropped;
    }

    private void finish(boolean success, String text) {
        if (finished) return;
        finished = true;
        Intent result = new Intent(ACTION_RESULT);
        result.setPackage(getPackageName());
        result.putExtra(EXTRA_SUCCESS, success);
        result.putExtra(EXTRA_TEXT, text == null ? "" : text);
        sendBroadcast(result);
        handler.postDelayed(this::stopSelf, 100);
    }

    @Override public void onDestroy() {
        finished = true;
        handler.removeCallbacksAndMessages(null);
        if (display != null) { display.release(); display = null; }
        if (imageReader != null) { imageReader.close(); imageReader = null; }
        if (devanagariRecognizer != null) { devanagariRecognizer.close(); devanagariRecognizer = null; }
        if (latinRecognizer != null) { latinRecognizer.close(); latinRecognizer = null; }
        if (projection != null) { projection.stop(); projection = null; }
        stopForeground(true);
        super.onDestroy();
    }

    @Nullable @Override public IBinder onBind(Intent intent) { return null; }
}
