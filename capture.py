"""Cattura dello schermo del telefono via adb e normalizzazione della risoluzione."""
import subprocess

import cv2
import numpy as np


def grab_frame(base_size=(2400, 1080), serial=None):
    """Ritorna un frame BGR ridimensionato a base_size (larghezza, altezza)."""
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += ["exec-out", "screencap", "-p"]
    raw = subprocess.run(cmd, capture_output=True, check=True, timeout=10).stdout
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("screencap non valido: telefono collegato e sbloccato?")
    h, w = img.shape[:2]
    if h > w:  # telefono in portrait: ruota (Hearthstone gira in landscape)
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return cv2.resize(img, tuple(base_size), interpolation=cv2.INTER_AREA)


def is_stable(prev, curr, threshold=2.0):
    """True se due frame consecutivi sono quasi uguali (animazioni finite)."""
    if prev is None:
        return False
    diff = cv2.absdiff(cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY), cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY))
    return float(diff.mean()) < threshold
