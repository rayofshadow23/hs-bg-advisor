"""Riconoscimento della fase di gioco tramite template matching."""
from pathlib import Path

import cv2

from . import crop

TEMPLATE_DIR = Path(__file__).with_name("templates")
THRESHOLD = 0.7


def _match(region, template_path):
    if not template_path.exists():
        return 0.0
    tpl = cv2.imread(str(template_path))
    if tpl is None or region.shape[0] < tpl.shape[0] or region.shape[1] < tpl.shape[1]:
        return 0.0
    return float(cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED).max())


def detect_phase(frame, regions):
    """recruit se si vede il pulsante reroll di Bob, combat se la targhetta a destra dice "Combat"
    (in acquisto mostra il timer), altrimenti unknown (menu, transizioni, schermate intermedie).

    Template in vision/templates/, ritagliati da screenshot reali: roll_button.png, combat_marker.png.
    Punteggi misurati: marcatore giusto 1.0, marcatore sbagliato <= 0.2 (soglia 0.7).
    """
    markers = regions["phase_markers"]
    roll = _match(crop(frame, markers["roll_button"]), TEMPLATE_DIR / "roll_button.png")
    if roll >= THRESHOLD:
        return "recruit"
    combat = _match(crop(frame, markers["combat_label"]), TEMPLATE_DIR / "combat_marker.png")
    if combat >= THRESHOLD:
        return "combat"
    return "unknown"
