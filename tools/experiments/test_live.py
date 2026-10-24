import cv2
import numpy as np
from pathlib import Path
import json

base_dir = Path("/home/ray/Downloads/hs-bg-advisor")
import sys
sys.path.insert(0, str(base_dir))

from vision import load_regions, crop
from vision import minions as mv
from vision import numbers as nv
from vision.phase import detect_phase

art_dir = Path("/home/ray/bg-assistant/card_art")
with open("/home/ray/bg-assistant/app/src/main/assets/minions.json") as f:
    minions = json.load(f)["minions"]

refs = {}
for m in minions:
    cid = m["cardId"]
    art_path = art_dir / f"{cid}.jpg"
    if art_path.exists():
        ref = cv2.imread(str(art_path))
        refs[cid] = (m, [cv2.resize(ref, (s, s)) for s in (125, 145, 165)])

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
img = cv2.imread("/tmp/live_now.png")
f = cv2.resize(img, tuple(r["base_size"]))

phase = detect_phase(f, r)
gold = nv.read_gold(crop(f, r["gold"]))
tier = nv.count_stars(crop(f, r["tavern_stars"]))
upgrade = nv.read_region(f, r, "upgrade_cost")
shop = mv.locate_shop(f, r)
board = mv.locate_board(f, r)

print(f"Phase: {phase} | Gold: {gold} | Tier: {tier} | Upgrade: {upgrade}")
print(f"Shop count: {len(shop)} | Board count: {len(board)}")

print("\n--- SHOP CARDS DETECTED ---")
for i, rect in enumerate(shop):
    m, score = match_crop(crop(f, rect))
    if score >= 0.50:
        print(f"  Slot {i+1}: {m['name']} (Tier {m['tier']}, {m.get('tribe','None')}) | Conf: {score:.3f}")
    else:
        print(f"  Slot {i+1}: ? (incantesimo/non riconosciuto, max conf: {score:.3f} per {m['name']})")

print("\n--- BOARD MINIONS DETECTED ---")
for i, rect in enumerate(board):
    m, score = match_crop(crop(f, rect))
    if score >= 0.50:
        print(f"  Slot {i+1}: {m['name']} (Tier {m['tier']}, {m.get('tribe','None')}) | Conf: {score:.3f}")
    else:
        print(f"  Slot {i+1}: ? (conf: {score:.3f} per {m['name']})")
