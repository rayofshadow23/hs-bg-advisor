import time
import cv2
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

# Group by tier
tier_refs = {}
for m in minions:
    cid = m["cardId"]
    t = m.get("tier", 1)
    art_path = art_dir / f"{cid}.jpg"
    if art_path.exists():
        ref = cv2.imread(str(art_path))
        if t not in tier_refs:
            tier_refs[t] = []
        tier_refs[t].append((m, [cv2.resize(ref, (s, s)) for s in (125, 145)]))

def match_crop_tiered(crop_img, max_tier=6):
    h, w = crop_img.shape[:2]
    cy, cx = h // 2, w // 2
    cc = crop_img[cy-25:cy+25, cx-25:cx+25]
    best_score = -1.0
    best_m = None
    # only search tiers up to max_tier
    for t in range(1, max_tier + 1):
        for m, scaled_list in tier_refs.get(t, []):
            for sref in scaled_list:
                res = cv2.matchTemplate(sref, cc, cv2.TM_CCOEFF_NORMED)
                _, max_v, _, _ = cv2.minMaxLoc(res)
                if max_v > best_score:
                    best_score = max_v
                    best_m = m
    return best_m, best_score

r = load_regions()
f = cv2.resize(cv2.imread(str(base_dir / "tests/fixtures/turn1_recruit.png")), tuple(r["base_size"]))
shop = mv.locate_shop(f, r)

t0 = time.time()
print("\n--- Testing Turn 1 Shop (Max Tier 1) ---")
for i, rect in enumerate(shop):
    m, score = match_crop_tiered(crop(f, rect), max_tier=1)
    print(f"Slot {i}: {m['name']} (Conf: {score:.3f})")
print(f"Total time for 3 slots: {(time.time() - t0)*1000:.1f}ms")
