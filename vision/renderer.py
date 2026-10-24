"""Rendering visivo e overlay grafico per Hearthstone Battlegrounds Advisor."""
from typing import List, Optional, Tuple

import cv2
import numpy as np

from advisor import Tip
from state import GameState

# Tavolozza colori BGR per le categorie di consiglio
PALETTE = {
    "triple": (0, 215, 255),    # Oro brillante per le triple
    "core": (60, 230, 60),      # Verde smeraldo per minion core
    "add-on": (240, 180, 40),   # Ciano/Azzurro elettrico per add-on
    "tribe": (0, 150, 255),     # Arancione per sinergia di tribù
    "tier": (180, 220, 255),    # Giallo chiaro / oro chiaro
    "upgrade": (80, 235, 120),  # Verde chiaro per level up taverna
    "roll": (220, 130, 240),    # Viola / magenta chiaro per roll
    "freeze": (255, 220, 100),  # Ciano glaciale per freeze
    "default": (70, 220, 70),   # Verde standard
    "dark_bg": (20, 22, 28),    # Sfondo scuro per badge e banner
    "text_white": (255, 255, 255),
    "text_dark": (15, 15, 15),
}


def _draw_translucent_rect(
    img: np.ndarray,
    rect: Tuple[int, int, int, int],
    color: Tuple[int, int, int],
    alpha: float = 0.65,
) -> None:
    """Disegna un rettangolo pieno con trasparenza alpha."""
    x, y, w, h = rect
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(img.shape[1], x + w), min(img.shape[0], y + h)
    if x2 <= x1 or y2 <= y1:
        return
    overlay = img[y1:y2, x1:x2].copy()
    cv2.rectangle(overlay, (0, 0), (x2 - x1, y2 - y1), color, -1)
    cv2.addWeighted(overlay, alpha, img[y1:y2, x1:x2], 1.0 - alpha, 0, img[y1:y2, x1:x2])


def _draw_badge(
    img: np.ndarray,
    text: str,
    cx: int,
    y: int,
    bg_color: Tuple[int, int, int],
    text_color: Tuple[int, int, int] = PALETTE["text_white"],
    scale: float = 0.55,
    thickness: int = 1,
) -> None:
    """Disegna un'etichetta (badge/pillola) centrata su cx all'altezza y."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad_x, pad_y = 10, 6
    x1 = cx - (tw // 2) - pad_x
    x2 = cx + (tw // 2) + pad_x
    y1 = y - th - pad_y
    y2 = y + pad_y + baseline

    # Sfondo badge (pillola con angoli squadrati puliti)
    cv2.rectangle(img, (x1, y1), (x2, y2), bg_color, -1)
    cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), 1, cv2.LINE_AA)
    # Testo centrato
    cv2.putText(img, text, (cx - tw // 2, y + baseline // 2), font, scale, text_color, thickness, cv2.LINE_AA)


def _draw_hud(img: np.ndarray, state: GameState, top_tip: Optional[Tip]) -> None:
    """Disegna la barra di stato superiore (HUD) con turno, oro, taverna, vita e consiglio principale."""
    w = img.shape[1]
    hud_h = 48
    _draw_translucent_rect(img, (0, 0, w, hud_h), PALETTE["dark_bg"], alpha=0.85)
    cv2.line(img, (0, hud_h), (w, hud_h), (80, 90, 110), 1, cv2.LINE_AA)

    font = cv2.FONT_HERSHEY_SIMPLEX
    # Informazioni a sinistra: Turno, Fase
    turn_str = f"TURNO {state.turn}" if state.turn else "TURNO -"
    phase_str = state.phase.upper()
    phase_col = (80, 230, 80) if state.phase == "recruit" else (70, 70, 240)
    cv2.putText(img, turn_str, (18, 30), font, 0.7, (240, 240, 240), 2, cv2.LINE_AA)
    cv2.putText(img, f"[{phase_str}]", (160, 30), font, 0.65, phase_col, 2, cv2.LINE_AA)

    # Informazioni al centro: Oro, Taverna, Vita
    gold_str = f"ORO: {state.gold if state.gold is not None else '?'}/{state.max_gold if state.max_gold is not None else '?'}"
    tavern_str = f"TAVERNA: T{state.tavern_tier if state.tavern_tier else '?'}"
    health_str = f"HP: {state.hero_health if state.hero_health is not None else '?'}"
    if state.hero_armor:
        health_str += f" (+{state.hero_armor})"

    stats_str = f"{gold_str}   |   {tavern_str}   |   {health_str}"
    cv2.putText(img, stats_str, (340, 30), font, 0.65, (230, 230, 180), 2, cv2.LINE_AA)

    # Consiglio principale sintetico a destra
    if top_tip:
        rec_color = PALETTE.get(top_tip.role, PALETTE["default"])
        # Tronca il testo per la barra superiore se troppo lungo
        display_text = top_tip.text
        if len(display_text) > 75:
            display_text = display_text[:72] + "..."
        cv2.putText(img, f"> {display_text}", (950, 30), font, 0.65, rec_color, 2, cv2.LINE_AA)


def draw_overlay(
    frame: np.ndarray,
    state: GameState,
    tips: List[Tip],
    regions: dict,
) -> np.ndarray:
    """Disegna tutti gli elementi grafici dell'advisor sopra una copia del frame."""
    out = frame.copy()

    # 1. Trova il consiglio principale
    top_tip = tips[0] if tips else None

    # 2. Barra superiore HUD
    _draw_hud(out, state, top_tip)

    # 3. Mappa dei consigli sullo shop per indice carta
    shop_tips_by_idx = {}
    for t in tips:
        if t.action == "BUY" and t.card_index is not None and t.card_index not in shop_tips_by_idx:
            shop_tips_by_idx[t.card_index] = t

    # 4. Evidenziazione carte dello Shop
    shop_rects = getattr(state, "shop_rects", []) or []
    for idx, rect in enumerate(shop_rects):
        rx, ry, rw, rh = rect
        cx = rx + rw // 2
        card_w = 138
        card_x1 = max(0, cx - card_w // 2)
        card_x2 = min(out.shape[1], cx + card_w // 2)
        card_y1 = 226
        card_y2 = 434

        tip = shop_tips_by_idx.get(idx)
        if tip:
            color = PALETTE.get(tip.role, PALETTE["default"])

            # Glow semitrasparente attorno alla carta consigliata
            glow_pad = 8
            _draw_translucent_rect(
                out,
                (card_x1 - glow_pad, card_y1 - glow_pad, card_w + glow_pad * 2, (card_y2 - card_y1) + glow_pad * 2),
                color,
                alpha=0.25,
            )

            # Riquadro principale evidenziato
            cv2.rectangle(out, (card_x1, card_y1), (card_x2, card_y2), color, 3, cv2.LINE_AA)
            cv2.rectangle(out, (card_x1 - 2, card_y1 - 2), (card_x2 + 2, card_y2 + 2), (255, 255, 255), 1, cv2.LINE_AA)

            # Badge ruolo / raccomandazione sopra la carta
            badge_title = {
                "triple": "3x TRIPLA",
                "core": "★ CORE",
                "add-on": "+ ADD-ON",
                "tribe": "SINERGIA",
                "tier": "ALTO TIER",
            }.get(tip.role, "RACCOMANDATO")

            _draw_badge(out, badge_title, cx, card_y1 - 6, color, PALETTE["text_white"], scale=0.6, thickness=2)

            # Dettaglio sotto la carta: Comp name o punteggio
            detail = tip.comp_name or (tip.card_name if tip.card_name else "")
            if detail:
                if len(detail) > 18:
                    detail = detail[:16] + ".."
                _draw_badge(out, detail, cx, card_y2 + 22, PALETTE["dark_bg"], color, scale=0.5, thickness=1)

    # 5. Evidenziazione Salita di Taverna (Upgrade)
    upgrade_tip = next((t for t in tips if t.action == "UPGRADE"), None)
    if upgrade_tip:
        up_rect = regions.get("upgrade_cost")
        if up_rect:
            ux, uy, uw, uh = up_rect
            # Rettangolo verde attorno al pulsante di taverna di Bob
            cv2.rectangle(out, (ux - 12, uy - 12), (ux + uw + 12, uy + uh + 12), PALETTE["upgrade"], 3, cv2.LINE_AA)
            _draw_badge(
                out,
                "⬆️ SALI TAVERNA",
                ux + uw // 2,
                uy + uh + 32,
                PALETTE["upgrade"],
                PALETTE["text_dark"],
                scale=0.6,
                thickness=2,
            )

    # 6. Evidenziazione Reroll (se consigliato)
    roll_tip = next((t for t in tips if t.action == "ROLL"), None)
    if roll_tip and "roll_button" in regions.get("phase_markers", {}):
        rx, ry, rw, rh = regions["phase_markers"]["roll_button"]
        cv2.rectangle(out, (rx, ry), (rx + rw, ry + rh), PALETTE["roll"], 2, cv2.LINE_AA)
        _draw_badge(out, "🎲 ROLL", rx + rw // 2, ry + rh + 20, PALETTE["roll"], PALETTE["text_white"], scale=0.55)

    # 7. Evidenziazione Freeze (se consigliato da Jeef)
    freeze_tip = next((t for t in tips if t.action == "FREEZE"), None)
    if freeze_tip and "roll_button" in regions.get("phase_markers", {}):
        rx, ry, rw, rh = regions["phase_markers"]["roll_button"]
        fx = 750
        cv2.rectangle(out, (fx, ry), (fx + rw, ry + rh), PALETTE["freeze"], 2, cv2.LINE_AA)
        _draw_badge(out, "❄️ FREEZE", fx + rw // 2, ry + rh + 20, PALETTE["freeze"], PALETTE["text_dark"], scale=0.55)

    return out
