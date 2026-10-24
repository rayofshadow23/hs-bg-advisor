"""Mostra uno screenshot con le regioni di regions.yaml sovrapposte, per verificare la calibrazione.

Uso: python tools/calibrate.py screenshot.png [--out calibration.png]
Modifica vision/regions.yaml finche' i rettangoli coprono gli elementi giusti. Le carte di shop e board
vengono individuate come fa main.py, quindi se mancano nell'overlay mancherebbero anche nel bot.
"""
import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vision import load_regions  # noqa: E402
from vision.minions import locate_board, locate_shop  # noqa: E402

RECT_KEYS = ("gold", "upgrade_cost", "hero_health", "hero_armor", "tavern_stars",
             "phase_banner", "hand_area", "shop_pennant_strip", "board_strip")


def draw(img, rect, label, color=(0, 255, 0)):
    x, y, w, h = rect
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
    cv2.putText(img, label, (x, max(20, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default="calibration.png")
    args = ap.parse_args()

    regions = load_regions()
    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"Impossibile leggere {args.image}")
    img = cv2.resize(img, tuple(regions["base_size"]), interpolation=cv2.INTER_AREA)
    frame = img.copy()  # le individuazioni lavorano sul frame pulito, senza i rettangoli disegnati
    for name in RECT_KEYS:
        draw(img, regions[name], name)
    for name, rect in regions["phase_markers"].items():
        draw(img, rect, name, (255, 0, 0))
    for i, r in enumerate(locate_shop(frame, regions)):
        draw(img, r, f"shop{i}", (0, 200, 255))
    for i, r in enumerate(locate_board(frame, regions)):
        draw(img, r, f"board{i}", (255, 0, 255))
    cv2.imwrite(args.out, img)
    print(f"Scritto {args.out}")


if __name__ == "__main__":
    main()
