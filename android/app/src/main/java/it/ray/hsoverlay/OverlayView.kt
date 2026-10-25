package it.ray.hsoverlay

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import android.view.View

/**
 * Disegna i consigli SOLO nei margini dello schermo e in una fascia stretta sopra lo shop:
 * non copre la visuale centrale e non interferisce con la lettura dello schermo.
 * Margini in coordinate normalizzate 2000x900:
 *   sinistra x 8..262 (HUD), destra x 1700..1992 (consigli), fascia marcatori y 208..230 sopra le carte.
 */
class OverlayView(context: Context) : View(context) {

    @Volatile
    var state: OverlayState? = null

    @Volatile
    var error: String? = null

    private val bg = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(200, 16, 18, 24) }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val text = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        typeface = Typeface.DEFAULT_BOLD
    }

    private fun roleColor(role: String, action: String): Int = when {
        role == "triple" -> Color.rgb(255, 215, 0)
        role == "core" -> Color.rgb(60, 230, 60)
        role == "add-on" -> Color.rgb(40, 180, 240)
        role == "tribe" -> Color.rgb(255, 150, 0)
        action == "UPGRADE" -> Color.rgb(120, 235, 80)
        action == "FREEZE" -> Color.rgb(100, 220, 255)
        action == "ROLL" -> Color.rgb(240, 130, 220)
        action == "HOLD" -> Color.rgb(255, 120, 120)
        else -> Color.rgb(200, 200, 200)
    }

    private fun roleLabel(t: Tip): String = when {
        t.role == "triple" -> "3x"
        t.role == "core" -> "CORE"
        t.role == "add-on" -> "ADD-ON"
        t.role == "tribe" -> "TRIBU"
        else -> "COMPRA"
    }

    override fun onDraw(canvas: Canvas) {
        val s = state
        val sx = width / (s?.baseW ?: 2000).toFloat()
        val sy = height / (s?.baseH ?: 900).toFloat()
        val u = sy // unita' per i testi

        canvas.save()
        canvas.scale(sx, sy)

        drawHud(canvas, s, u)
        if (s != null && s.phase == "recruit") {
            drawMarkers(canvas, s)
            drawTips(canvas, s)
        }
        canvas.restore()
    }

    private fun drawHud(canvas: Canvas, s: OverlayState?, u: Float) {
        val lines = ArrayList<Pair<String, Int>>()
        if (error != null) {
            lines += "Stato: $error" to Color.rgb(255, 110, 110)
        } else if (s == null) {
            lines += "In attesa del gioco..." to Color.LTGRAY
        } else {
            val phase = when (s.phase) {
                "recruit" -> "Acquisto"
                "combat" -> "Combattimento"
                else -> "Fase ?"
            }
            lines += "Turno ${s.turn ?: "?"}  -  $phase" to Color.WHITE
            lines += "Oro ${s.gold ?: "?"}/${s.maxGold ?: "?"}  -  Taverna ${s.tier ?: "?"}" to Color.rgb(255, 215, 0)
            if (s.upgradeCost != null) lines += "Upgrade: ${s.upgradeCost} oro" to Color.LTGRAY
            lines += "Vita ${s.health ?: "?"} + ${s.armor ?: 0}" to Color.rgb(255, 130, 130)
        }
        text.textSize = 22f
        val lh = 30f
        val rect = RectF(8f, 120f, 262f, 120f + 14f + lines.size * lh)
        canvas.drawRoundRect(rect, 10f, 10f, bg)
        lines.forEachIndexed { i, (t, c) ->
            text.color = c
            canvas.drawText(t, 16f, 120f + 14f + (i + 1) * lh - 8f, text)
        }
    }

    /** Un marcatore per carta dello shop (il consiglio con punteggio piu' alto), nella fascia y 208..230. */
    private fun drawMarkers(canvas: Canvas, s: OverlayState) {
        val best = HashMap<Int, Tip>()
        for (t in s.tips) {
            val i = t.cardIndex ?: continue
            if (t.action != "BUY") continue
            if (best[i] == null || t.score > best[i]!!.score) best[i] = t
        }
        text.textSize = 18f
        for ((i, t) in best) {
            val rect = s.shop.getOrNull(i)?.rect ?: continue
            val cx = rect[0] + 52f
            val label = roleLabel(t)
            val w = text.measureText(label) + 20f
            val r = RectF(cx - w / 2, 208f, cx + w / 2, 230f)
            fill.color = roleColor(t.role, t.action)
            canvas.drawRoundRect(r, 8f, 8f, fill)
            text.color = Color.rgb(15, 15, 15)
            canvas.drawText(label, r.left + 10f, r.bottom - 5f, text)
        }
    }

    /** Pannello consigli nel margine destro, il primo e' il piu' importante. */
    private fun drawTips(canvas: Canvas, s: OverlayState) {
        val tips = s.tips.take(5)
        if (tips.isEmpty()) return
        val panelW = 292
        text.textSize = 22f
        var y = 110f
        for ((n, t) in tips.withIndex()) {
            val c = roleColor(t.role, t.action)
            text.color = Color.WHITE
            val layout = StaticLayout.Builder
                .obtain(t.text, 0, t.text.length, text, panelW - 28)
                .setAlignment(Layout.Alignment.ALIGN_NORMAL)
                .setLineSpacing(0f, 1.0f)
                .setIncludePad(false)
                .build()
            val h = layout.height + 22f
            if (y + h > 880f) break
            val r = RectF(1700f, y, 1700f + panelW, y + h)
            canvas.drawRoundRect(r, 10f, 10f, bg)
            fill.color = c
            canvas.drawRoundRect(RectF(r.left, r.top, r.left + 8f, r.bottom), 4f, 4f, fill)
            canvas.save()
            canvas.translate(r.left + 18f, r.top + 11f)
            if (n == 0) text.typeface = Typeface.DEFAULT_BOLD else text.typeface = Typeface.DEFAULT
            layout.draw(canvas)
            canvas.restore()
            y += h + 8f
        }
        text.typeface = Typeface.DEFAULT_BOLD
    }
}
