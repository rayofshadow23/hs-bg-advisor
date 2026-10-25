package it.ray.hsoverlay

import org.json.JSONArray
import org.json.JSONObject

/** Stato pubblicato dal PC (overlay_server.py). Le coordinate sono nello spazio base_size (2000x900). */
data class Card(
    val name: String,
    val tier: Int,
    val attack: Int?,
    val health: Int?,
    val spell: Boolean,
    val rect: IntArray?,
)

data class Tip(
    val text: String,
    val action: String,
    val cardIndex: Int?,
    val role: String,
    val score: Double,
)

data class OverlayState(
    val seq: Int,
    val baseW: Int,
    val baseH: Int,
    val phase: String,
    val turn: Int?,
    val gold: Int?,
    val maxGold: Int?,
    val tier: Int?,
    val upgradeCost: Int?,
    val health: Int?,
    val armor: Int?,
    val shop: List<Card>,
    val tips: List<Tip>,
)

private fun JSONObject.intOrNull(key: String): Int? =
    if (!has(key) || isNull(key)) null else optInt(key)

private fun JSONArray.objects(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }

fun parseState(body: String): OverlayState {
    val o = JSONObject(body)
    val size = o.optJSONArray("base_size")
    val shop = (o.optJSONArray("shop") ?: JSONArray()).objects().map { c ->
        val r = c.optJSONArray("rect")
        Card(
            name = c.optString("name", "?"),
            tier = c.optInt("tier", 0),
            attack = c.intOrNull("attack"),
            health = c.intOrNull("health"),
            spell = c.optBoolean("spell", false),
            rect = if (r != null && r.length() == 4) IntArray(4) { r.getInt(it) } else null,
        )
    }
    val tips = (o.optJSONArray("tips") ?: JSONArray()).objects().map { t ->
        Tip(
            text = t.optString("text", ""),
            action = t.optString("action", "INFO"),
            cardIndex = t.intOrNull("card_index"),
            role = t.optString("role", ""),
            score = t.optDouble("score", 0.0),
        )
    }
    return OverlayState(
        seq = o.optInt("seq", 0),
        baseW = size?.optInt(0, 2000) ?: 2000,
        baseH = size?.optInt(1, 900) ?: 900,
        phase = o.optString("phase", "unknown"),
        turn = o.intOrNull("turn"),
        gold = o.intOrNull("gold"),
        maxGold = o.intOrNull("max_gold"),
        tier = o.intOrNull("tavern_tier"),
        upgradeCost = o.intOrNull("upgrade_cost"),
        health = o.intOrNull("hero_health"),
        armor = o.intOrNull("hero_armor"),
        shop = shop,
        tips = tips,
    )
}
