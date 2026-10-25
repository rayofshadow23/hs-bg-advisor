import json
import sys
from pathlib import Path
import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from standalone_engine import StandaloneEngine, process_rgba, reset_engine

FIXTURES = Path(__file__).parent / "fixtures"


def test_standalone_engine_bgr():
    img_path = FIXTURES / "turn1_recruit.png"
    img = cv2.imread(str(img_path))
    assert img is not None

    engine = StandaloneEngine()
    payload_str = engine.process_frame_bgr(img, force_update=True)
    assert isinstance(payload_str, str)

    data = json.loads(payload_str)
    assert data["phase"] == "recruit"
    assert data["gold"] == 0
    assert data["max_gold"] == 3
    assert data["turn"] == 1
    assert data["tavern_tier"] == 1
    assert len(data["shop"]) == 3  # 2 minions + 1 spell
    assert len(data["tips"]) > 0


def test_standalone_engine_rgba_bytes():
    img_path = FIXTURES / "turn3_recruit.png"
    bgr = cv2.imread(str(img_path))
    assert bgr is not None
    h, w = bgr.shape[:2]
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
    rgba_bytes = rgba.tobytes()

    engine = StandaloneEngine()
    payload_str = engine.process_frame_rgba_bytes(rgba_bytes, w, h, force_update=True)
    data = json.loads(payload_str)

    assert data["phase"] == "recruit"
    assert data["gold"] == 0
    assert data["max_gold"] == 5
    assert data["turn"] == 3
    assert data["tavern_tier"] == 2
    assert len(data["shop"]) == 3
    assert len(data["tips"]) > 0


def test_standalone_engine_rgba_with_stride():
    img_path = FIXTURES / "turn1_recruit.png"
    bgr = cv2.imread(str(img_path))
    h, w = bgr.shape[:2]
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)

    # Simula un padding di 32 byte alla fine di ogni riga
    pad_bytes = 32
    padded_stride = w * 4 + pad_bytes
    padded_arr = np.zeros((h, padded_stride), dtype=np.uint8)
    padded_arr[:, :w * 4] = rgba.reshape((h, w * 4))
    padded_bytes = padded_arr.tobytes()

    engine = StandaloneEngine()
    payload_str = engine.process_frame_rgba_bytes(padded_bytes, w, h, row_stride=padded_stride, force_update=True)
    data = json.loads(payload_str)

    assert data["phase"] == "recruit"
    assert data["gold"] == 0
    assert data["max_gold"] == 3


def test_global_bridge_functions():
    reset_engine()
    img_path = FIXTURES / "turn1_recruit.png"
    bgr = cv2.imread(str(img_path))
    h, w = bgr.shape[:2]
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)

    # Invio due frame consecutivi per simulare flusso stabile dal vivo
    process_rgba(rgba.tobytes(), w, h)
    payload_str = process_rgba(rgba.tobytes(), w, h)
    data = json.loads(payload_str)
    assert data["phase"] == "recruit"
    assert "tips" in data
    assert data["gold"] == 0
    assert data["max_gold"] == 3
