package it.ray.hsoverlay

import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.util.Log

/**
 * Gestisce la cattura continua dello schermo tramite MediaProjection API + ImageReader.
 * Esegue l'analisi in background a ~2-3 FPS per bilanciare reattività e risparmio energetico.
 */
class MediaProjectionCapture(
    private val mediaProjection: MediaProjection,
    private val width: Int,
    private val height: Int,
    private val densityDpi: Int,
    private val advisorBridge: AdvisorBridge,
    private val onStateUpdate: (OverlayState?, String?) -> Unit,
) {

    private val tag = "MediaCapture"
    private var imageReader: ImageReader? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var handlerThread: HandlerThread? = null
    private var handler: Handler? = null

    @Volatile
    private var isRunning = false
    private var lastProcessTimeMs = 0L
    private val frameIntervalMs = 350L // ~2.8 FPS

    fun start() {
        if (isRunning) return
        isRunning = true

        handlerThread = HandlerThread("ScreenCaptureThread").apply { start() }
        handler = Handler(handlerThread!!.looper)

        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2).apply {
            setOnImageAvailableListener({ reader ->
                val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
                processImage(image)
            }, handler)
        }

        // Android 14+: la callback va registrata PRIMA di createVirtualDisplay, altrimenti lancia IllegalStateException
        mediaProjection.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() {
                isRunning = false
            }
        }, handler)

        virtualDisplay = mediaProjection.createVirtualDisplay(
            "HS-BG-Advisor-Display",
            width,
            height,
            densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader!!.surface,
            null,
            handler,
        )
        Log.i(tag, "Cattura schermo avviata: ${width}x${height} @ ${densityDpi}dpi")
    }

    private fun processImage(image: Image) {
        val now = SystemClock.uptimeMillis()
        if (now - lastProcessTimeMs < frameIntervalMs) {
            image.close()
            return
        }
        lastProcessTimeMs = now

        try {
            val plane = image.planes[0]
            val buffer = plane.buffer
            val pixelStride = plane.pixelStride
            val rowStride = plane.rowStride
            val imgWidth = image.width
            val imgHeight = image.height

            val bytes = ByteArray(buffer.remaining())
            buffer.get(bytes)
            image.close()

            val state = advisorBridge.processRgba(bytes, imgWidth, imgHeight, rowStride)
            if (state != null) {
                onStateUpdate(state, null)
            }
        } catch (e: Exception) {
            Log.e(tag, "Errore durante l'elaborazione del frame", e)
            onStateUpdate(null, e.message ?: e.javaClass.simpleName)
            image.close()
        }
    }

    fun stop() {
        isRunning = false
        try {
            virtualDisplay?.release()
            virtualDisplay = null
            imageReader?.close()
            imageReader = null
            mediaProjection.stop()
            handlerThread?.quitSafely()
            handlerThread = null
            handler = null
            Log.i(tag, "Cattura schermo terminata con successo")
        } catch (e: Exception) {
            Log.e(tag, "Errore durante la chiusura della cattura schermo", e)
        }
    }
}
