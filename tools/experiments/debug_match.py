import sys
from pathlib import Path
import cv2
import json
from PIL import Image

base_dir = Path("/home/ray/Downloads/hs-bg-advisor")
sys.path.insert(0, str(base_dir))

from vision import load_regions, crop
from vision import minions as mv

r = load_regions()
img = cv2.imread(str(base_dir / "tests/fixtures/turn1_recruit.png"))
f = cv2.resize(img, tuple(r["base_size"]))
shop_rects = mv.locate_shop(f, r)

with open("/home/ray/bg-assistant/app/src/main/assets/minions.json") as jf:
    mdata = json.load(jf)
minions = mdata.get("minions", mdata)
art_dir = Path("/home/ray/bg-assistant/card_art")

# Cache 48x48
cache = {}
for m in minions:
    cid = m.get("cardId")
    p = art_dir / f"{cid}.jpg"
    if p.exists():
        im = Image.open(p).convert("RGB")
        aw, ah = im.size
        # crop portrait center: 20%-80% width, 15%-75% height
        ac = im.crop((int(aw * 0.20), int(ah * 0.15), int(aw * 0.80), int(ah * 0.75))).resize((48, 48))
        cache[cid] = (m, list(ac.getdata()))

for i, rect in enumerate(shop_rects):
    c = crop(f, rect)
    # The crop is 104x100
    im = Image.fromarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB))
    cw, ch = im.size
    # crop center to avoid the oval frame
    cc = im.crop((int(cw * 0.15), int(ch * 0.15), int(cw * 0.85), int(ch * 0.85))).resize((48, 48))
    c_pix = list(cc.getdata())

    scores = []
    for cid, (m, ref_pix) in cache.items():
        diff = sum(abs(r1-r2) + abs(g1-g2) + abs(b1-b2) for (r1,g1,b1), (r2,g2,b2) in zip(c_pix, ref_pix))
        scores.append((diff, m))
    scores.sort(key=lambda x: x[0])
    print(f"Slot {i}:")
    for diff, m in scores[:3]:
        print(f"   {m['name']} (tier {m['tier']}, id={m['cardId']}): diff={diff}")
