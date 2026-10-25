package it.ray.hsoverlay

import java.net.HttpURLConnection
import java.net.URL

/** Interroga il PC ogni ~400 ms. onState(stato, null) se ok, onState(null, errore) se il PC non risponde. */
class StatePoller(
    private val url: String,
    private val onState: (OverlayState?, String?) -> Unit,
) : Thread("state-poller") {

    @Volatile
    private var running = true

    fun stopPolling() {
        running = false
        interrupt()
    }

    override fun run() {
        while (running) {
            try {
                val conn = URL(url).openConnection() as HttpURLConnection
                conn.connectTimeout = 800
                conn.readTimeout = 1200
                try {
                    val body = conn.inputStream.bufferedReader().use { it.readText() }
                    onState(parseState(body), null)
                } finally {
                    conn.disconnect()
                }
            } catch (e: InterruptedException) {
                return
            } catch (e: Exception) {
                onState(null, e.message ?: e.javaClass.simpleName)
            }
            try {
                sleep(400)
            } catch (e: InterruptedException) {
                return
            }
        }
    }
}
