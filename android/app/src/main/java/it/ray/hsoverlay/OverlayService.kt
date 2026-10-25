package it.ray.hsoverlay

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.view.Gravity
import android.view.WindowManager

/** Servizio in primo piano: mostra l'overlay a tutto schermo (non toccabile) e lo aggiorna dal PC. */
class OverlayService : Service() {

    private var windowManager: WindowManager? = null
    private var view: OverlayView? = null
    private var poller: StatePoller? = null
    private val ui = Handler(Looper.getMainLooper())

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        startInForeground()
        val url = intent?.getStringExtra(EXTRA_URL) ?: DEFAULT_URL
        removeOverlay()
        addOverlay()
        poller?.stopPolling()
        poller = StatePoller(url) { state, err ->
            ui.post {
                view?.state = state ?: view?.state
                view?.error = err
                view?.invalidate()
            }
        }.also { it.start() }
        return START_NOT_STICKY
    }

    private fun startInForeground() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "Overlay HS BG", NotificationManager.IMPORTANCE_LOW)
        )
        val stop = android.app.PendingIntent.getService(
            this, 0,
            Intent(this, OverlayService::class.java).setAction(ACTION_STOP),
            android.app.PendingIntent.FLAG_IMMUTABLE,
        )
        val n = Notification.Builder(this, CHANNEL)
            .setContentTitle("HS BG Overlay attivo")
            .setContentText("Tocca 'Ferma' per chiudere l'overlay")
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .addAction(Notification.Action.Builder(android.R.drawable.ic_delete, "Ferma", stop).build())
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
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
        poller?.stopPolling()
        removeOverlay()
        super.onDestroy()
    }

    companion object {
        const val CHANNEL = "overlay"
        const val ACTION_STOP = "it.ray.hsoverlay.STOP"
        const val EXTRA_URL = "url"
        const val DEFAULT_URL = "http://127.0.0.1:8765/state"
    }
}
