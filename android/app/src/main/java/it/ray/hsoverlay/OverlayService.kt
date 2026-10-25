package it.ray.hsoverlay

import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.DisplayMetrics
import android.view.Gravity
import android.view.WindowManager
import kotlin.math.max
import kotlin.math.min

/**
 * Servizio in primo piano: gestisce sia la modalità Standalone su dispositivo
 * (MediaProjection + Chaquopy) che la modalità PC Client (HTTP Polling).
 */
class OverlayService : Service() {

    private var windowManager: WindowManager? = null
    private var view: OverlayView? = null
    private var poller: StatePoller? = null
    private var capture: MediaProjectionCapture? = null
    private var advisorBridge: AdvisorBridge? = null
    private val ui = Handler(Looper.getMainLooper())

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) return START_NOT_STICKY

        when (intent.action) {
            ACTION_STOP -> {
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_RESET -> {
                advisorBridge?.reset()
                return START_STICKY
            }
        }

        val mode = intent.getStringExtra(EXTRA_MODE) ?: MODE_STANDALONE
        startInForeground(mode)
        removeOverlay()
        addOverlay()

        if (mode == MODE_STANDALONE) {
            startStandaloneCapture(intent)
        } else {
            startPcPoller(intent)
        }

        return START_STICKY
    }

    private fun startStandaloneCapture(intent: Intent) {
        poller?.stopPolling()
        poller = null
        capture?.stop()
        capture = null

        val resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED)
        val resultData = if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(EXTRA_RESULT_DATA)
        }

        if (resultCode != Activity.RESULT_OK || resultData == null) {
            ui.post {
                view?.error = "Permesso di cattura schermo non concesso."
                view?.invalidate()
            }
            return
        }

        val mpManager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val mediaProjection = mpManager.getMediaProjection(resultCode, resultData)

        if (advisorBridge == null) {
            advisorBridge = AdvisorBridge(this)
        }

        val metrics = resources.displayMetrics
        val screenW = max(metrics.widthPixels, metrics.heightPixels)
        val screenH = min(metrics.widthPixels, metrics.heightPixels)
        val density = metrics.densityDpi

        capture = MediaProjectionCapture(
            mediaProjection = mediaProjection,
            width = screenW,
            height = screenH,
            densityDpi = density,
            advisorBridge = advisorBridge!!,
        ) { state, err ->
            ui.post {
                view?.state = state ?: view?.state
                view?.error = err
                view?.invalidate()
            }
        }.also { it.start() }
    }

    private fun startPcPoller(intent: Intent) {
        capture?.stop()
        capture = null
        poller?.stopPolling()
        val url = intent.getStringExtra(EXTRA_URL) ?: DEFAULT_URL
        poller = StatePoller(url) { state, err ->
            ui.post {
                view?.state = state ?: view?.state
                view?.error = err
                view?.invalidate()
            }
        }.also { it.start() }
    }

    private fun startInForeground(mode: String) {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "Overlay HS BG Advisor", NotificationManager.IMPORTANCE_LOW)
        )
        val stop = PendingIntent.getService(
            this, 0,
            Intent(this, OverlayService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val reset = PendingIntent.getService(
            this, 1,
            Intent(this, OverlayService::class.java).setAction(ACTION_RESET),
            PendingIntent.FLAG_IMMUTABLE,
        )

        val title = if (mode == MODE_STANDALONE) "HS BG Advisor Standalone Attivo" else "HS BG Overlay (PC Mode) Attivo"
        val n = Notification.Builder(this, CHANNEL)
            .setContentTitle(title)
            .setContentText("Tocca per resettare o fermare l'advisor")
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .addAction(Notification.Action.Builder(android.R.drawable.ic_menu_rotate, "Nuova Partita", reset).build())
            .addAction(Notification.Action.Builder(android.R.drawable.ic_delete, "Ferma", stop).build())
            .setOngoing(true)
            .build()

        if (Build.VERSION.SDK_INT >= 34) {
            val serviceType = if (mode == MODE_STANDALONE) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
            } else {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
            }
            startForeground(1, n, serviceType)
        } else {
            startForeground(1, n)
        }
    }

    private fun addOverlay() {
        val wm = getSystemService(WINDOW_SERVICE) as WindowManager
        val v = OverlayView(this)
        val lp = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        )
        lp.gravity = Gravity.TOP or Gravity.START
        if (Build.VERSION.SDK_INT >= 28) {
            lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
        }
        wm.addView(v, lp)
        windowManager = wm
        view = v
    }

    private fun removeOverlay() {
        view?.let { runCatching { windowManager?.removeView(it) } }
        view = null
    }

    override fun onDestroy() {
        capture?.stop()
        poller?.stopPolling()
        removeOverlay()
        super.onDestroy()
    }

    companion object {
        const val CHANNEL = "overlay"
        const val ACTION_STOP = "it.ray.hsoverlay.STOP"
        const val ACTION_RESET = "it.ray.hsoverlay.RESET"
        const val EXTRA_MODE = "mode"
        const val EXTRA_URL = "url"
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"

        const val MODE_STANDALONE = "standalone"
        const val MODE_PC = "pc"
        const val DEFAULT_URL = "http://127.0.0.1:8765/state"
    }
}
