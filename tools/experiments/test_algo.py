import cv2
import numpy as np
from pathlib import Path
import json

base_dir = Path("/home/ray/Downloads/hs-bg-advisor")
import sys
sys.path.insert(0, str(base_dir))

from vision import load_regions, crop
from vision import minions as mv

art_dir = Path("/home/ray/bg-assistant/card_art")
with open("/home/ray/bg-assistant/app/src/main/assets/minions.json") as f:
    minions = json.load(f)["minions"]

# Preload & prescale reference images
refs = {}
for m in minions:
    cid = m["cardId"]
    art_path = art_dir / f"{cid}.jpg"
    if art_path.exists():
        ref = cv2.imread(str(art_path))
        refs[cid] = (m, [cv2.resize(ref, (s, s)) for s in (120, 140, 160)])

def match_crop(crop_img):
    h, w = crop_img.shape[:2]
    cy, cx = h // 2, w // 2
    cc = crop_img[cy-25:cy+25, cx-25:cx+25]
    best_score = -1.0
    best_m = None
    for cid, (m, scaled_list) in refs.items():
        for sref in scaled_list:
            res = cv2.matchTemplate(sref, cc, cv2.TM_CCOEFF_NORMED)
            _, max_v, _, _ = cv2.minMaxLoc(res)
            if max_v > best_score:
                best_score = max_v
                best_m = m
    return best_m, best_score

r = load_regions()
for name in ["turn1_recruit.png", "turn3_recruit.png", "turn4_recruit.png"]:
    f = cv2.resize(cv2.imread(str(base_dir / f"tests/fixtures/{name}")), tuple(r["base_size"]))
    shop = mv.locate_shop(f, r)
    board = mv.locate_board(f, r)
    print(f"\n=== {name} ===")
    print(f"Shop ({len(shop)}):")
    for i, rect in enumerate(shop):
        m, s = match_crop(crop(f, rect))
        print(f"  Slot {i}: {m['name']} (T{m['tier']}) - Conf: {s:.3f}")
    print(f"Board ({len(board)}):")
    for i, rect in enumerate(board):
        m, s = match_crop(crop(f, rect))
        print(f"  Slot {i}: {m['name']} (T{m['tier']}) - Conf: {s:.3f}")
