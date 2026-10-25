package it.ray.hsoverlay

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Ponte bidirezionale tra Kotlin e il runtime Python embedded (Chaquopy).
 * Invia i buffer immagine dello schermo e riceve lo stato di gioco e i consigli strategici in JSON.
 */
class AdvisorBridge(context: Context) {

    private val isInitialized = AtomicBoolean(false)
    private var engineModule: PyObject? = null

    init {
        ensureInitialized(context)
    }

    @Synchronized
    private fun ensureInitialized(context: Context) {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(context.applicationContext))
        }
        if (engineModule == null) {
            val py = Python.getInstance()
            engineModule = py.getModule("standalone_engine")
            isInitialized.set(true)
        }
    }

    /**
     * Elabora un buffer di pixel RGBA catturato da MediaProjection/ImageReader.
     * Ritorna l'OverlayState aggiornato o null in caso di errore.
     */
    fun processRgba(rgbaBytes: ByteArray, width: Int, height: Int, rowStride: Int = 0): OverlayState? {
        val module = engineModule ?: return null
        return try {
            val jsonResult = module.callAttr("process_rgba", rgbaBytes, width, height, rowStride).toString()
            parseState(jsonResult)
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    /**
     * Resetta lo stato del TurnTracker e dello Smoother all'inizio di una nuova partita.
     */
    fun reset() {
        try {
            engineModule?.callAttr("reset_engine")
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
}
