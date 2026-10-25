package it.ray.hsoverlay

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

/** Schermata di controllo: permesso overlay, indirizzo del PC, avvia/ferma. Layout costruito da codice. */
class MainActivity : Activity() {

    private lateinit var status: TextView
    private lateinit var urlField: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("cfg", Context.MODE_PRIVATE)
        val pad = (16 * resources.displayMetrics.density).toInt()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
        }
        fun add(v: android.view.View) = root.addView(
            v, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        )

        add(TextView(this).apply {
            text = "HS BG Overlay\n\nMostra sopra Hearthstone i consigli calcolati dal PC.\n" +
                "Sul PC: adb reverse tcp:8765 tcp:8765 e python main.py --serve"
            textSize = 16f
        })
        urlField = EditText(this).apply {
            setText(prefs.getString("url", OverlayService.DEFAULT_URL))
            setSingleLine()
        }
        add(urlField)
        add(Button(this).apply {
            text = "1. Consenti 'Mostra sopra altre app'"
            setOnClickListener {
                startActivity(
                    Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
                )
            }
        })
        add(Button(this).apply {
            text = "2. Avvia overlay"
            setOnClickListener {
                if (!Settings.canDrawOverlays(this@MainActivity)) {
                    status.text = "Prima concedi il permesso (passo 1)."
                    return@setOnClickListener
                }
                if (Build.VERSION.SDK_INT >= 33) {
                    requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1)
                }
                val url = urlField.text.toString().trim().ifEmpty { OverlayService.DEFAULT_URL }
                prefs.edit().putString("url", url).apply()
                startForegroundService(
                    Intent(this@MainActivity, OverlayService::class.java).putExtra(OverlayService.EXTRA_URL, url)
                )
                status.text = "Overlay avviato. Apri Hearthstone."
            }
        })
        add(Button(this).apply {
            text = "3. Ferma overlay"
            setOnClickListener {
                startService(
                    Intent(this@MainActivity, OverlayService::class.java).setAction(OverlayService.ACTION_STOP)
                )
                status.text = "Overlay fermato."
            }
        })
        status = TextView(this).apply { textSize = 15f }
        add(status)
        setContentView(root)
    }

    override fun onResume() {
        super.onResume()
        status.text = if (Settings.canDrawOverlays(this)) "Permesso overlay: OK" else "Permesso overlay: MANCANTE"
    }
}
