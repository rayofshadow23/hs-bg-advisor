package it.ray.hsoverlay

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.TextView

/**
 * Schermata di controllo principale:
 * - Concessione permessi (Overlay, Notifiche, Cattura Schermo, Risparmio Batteria).
 * - Selezione modalità (100% Standalone sul telefono vs PC Client via Wi-Fi/ADB).
 * - Avvio e arresto del servizio overlay.
 */
class MainActivity : Activity() {

    private lateinit var status: TextView
    private lateinit var urlField: EditText
    private lateinit var modeRadioGroup: RadioGroup
    private lateinit var pcSettingsLayout: LinearLayout

    private val REQUEST_MEDIA_PROJECTION = 1001

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
            text = "HS BG Advisor (Standalone & Overlay)\n\nAssistente strategico in tempo reale per Hearthstone Battlegrounds."
            textSize = 16f
        })

        // Selettore Modalità
        modeRadioGroup = RadioGroup(this).apply {
            orientation = RadioGroup.VERTICAL
            val radioStandalone = RadioButton(this@MainActivity).apply {
                id = 1
                text = "Modalità Standalone (100% sul telefono, nessun PC)"
                isChecked = prefs.getString("mode", OverlayService.MODE_STANDALONE) == OverlayService.MODE_STANDALONE
            }
            val radioPc = RadioButton(this@MainActivity).apply {
                id = 2
                text = "Modalità PC Client (Elaborazione su PC via Wi-Fi/cavo)"
                isChecked = prefs.getString("mode", OverlayService.MODE_STANDALONE) == OverlayService.MODE_PC
            }
            addView(radioStandalone)
            addView(radioPc)
        }
        add(modeRadioGroup)

        pcSettingsLayout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = if (modeRadioGroup.checkedRadioButtonId == 2) android.view.View.VISIBLE else android.view.View.GONE
        }
        urlField = EditText(this).apply {
            setText(prefs.getString("url", OverlayService.DEFAULT_URL))
            setSingleLine()
            hint = "http://127.0.0.1:8765/state o IP PC"
        }
        pcSettingsLayout.addView(TextView(this).apply { text = "Indirizzo del server PC:" })
        pcSettingsLayout.addView(urlField)
        add(pcSettingsLayout)

        modeRadioGroup.setOnCheckedChangeListener { _, checkedId ->
            pcSettingsLayout.visibility = if (checkedId == 2) android.view.View.VISIBLE else android.view.View.GONE
            prefs.edit().putString(
                "mode",
                if (checkedId == 2) OverlayService.MODE_PC else OverlayService.MODE_STANDALONE
            ).apply()
        }

        // 1. Permesso Overlay
        add(Button(this).apply {
            text = "1. Permesso 'Mostra sopra altre app'"
            setOnClickListener {
                startActivity(
                    Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
                )
            }
        })

        // 2. Permesso Batteria (per evitare kill di ColorOS/MIUI/Samsung)
        add(Button(this).apply {
            text = "2. Disattiva risparmio batteria (ColorOS/Oppo)"
            setOnClickListener {
                val pm = getSystemService(POWER_SERVICE) as PowerManager
                if (Build.VERSION.SDK_INT >= 23 && !pm.isIgnoringBatteryOptimizations(packageName)) {
                    startActivity(
                        Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName"))
                    )
                } else {
                    status.text = "Risparmio batteria già disattivato per questa app."
                }
            }
        })

        // 3. Avvia Overlay
        add(Button(this).apply {
            text = "3. Avvia Advisor"
            setOnClickListener {
                if (!Settings.canDrawOverlays(this@MainActivity)) {
                    status.text = "Prima concedi il permesso 'Mostra sopra altre app' (passo 1)."
                    return@setOnClickListener
                }
                if (Build.VERSION.SDK_INT >= 33) {
                    requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1)
                }

                val isStandalone = modeRadioGroup.checkedRadioButtonId == 1
                if (isStandalone) {
                    val mpManager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                    startActivityForResult(mpManager.createScreenCaptureIntent(), REQUEST_MEDIA_PROJECTION)
                } else {
                    val url = urlField.text.toString().trim().ifEmpty { OverlayService.DEFAULT_URL }
                    prefs.edit().putString("url", url).apply()
                    val intent = Intent(this@MainActivity, OverlayService::class.java).apply {
                        putExtra(OverlayService.EXTRA_MODE, OverlayService.MODE_PC)
                        putExtra(OverlayService.EXTRA_URL, url)
                    }
                    startForegroundService(intent)
                    status.text = "Overlay PC avviato. Apri Hearthstone."
                }
            }
        })

        // 4. Ferma Overlay
        add(Button(this).apply {
            text = "4. Ferma Advisor"
            setOnClickListener {
                startService(
                    Intent(this@MainActivity, OverlayService::class.java).setAction(OverlayService.ACTION_STOP)
                )
                status.text = "Advisor fermato."
            }
        })

        status = TextView(this).apply { textSize = 15f }
        add(status)
        setContentView(root)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_MEDIA_PROJECTION) {
            if (resultCode == RESULT_OK && data != null) {
                val intent = Intent(this, OverlayService::class.java).apply {
                    putExtra(OverlayService.EXTRA_MODE, OverlayService.MODE_STANDALONE)
                    putExtra(OverlayService.EXTRA_RESULT_CODE, resultCode)
                    putExtra(OverlayService.EXTRA_RESULT_DATA, data)
                }
                startForegroundService(intent)
                status.text = "Advisor Standalone attivo in background. Apri Hearthstone!"
            } else {
                status.text = "Cattura schermo annullata o non autorizzata."
            }
        }
    }

    override fun onResume() {
        super.onResume()
        status.text = if (Settings.canDrawOverlays(this)) "Permesso overlay: OK" else "Permesso overlay: MANCANTE (vedi Passo 1)"
    }
}
