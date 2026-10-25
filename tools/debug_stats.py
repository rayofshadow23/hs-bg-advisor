"""Diagnostica della lettura di attacco/vita: mostra dove il codice crede che siano le carte.

Uso: python tools/debug_stats.py shot.png [--out debug_stats.png]
Stampa per ogni carta del board e dello shop (x del centro, attacco, vita) e scrive un'immagine con il
centro di ogni carta (linea verticale), la finestra di lettura e i numeri letti. Se le linee non cadono
al centro delle carte, il problema e' la posizione (locate_board / board_grid), non l'OCR delle cifre.
"""
import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vision import load_regions  # noqa: E402
from vision import minions as mv  # noqa: E402
from vision import numbers as nv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default="debug_stats.png")
    args = ap.parse_args()
    r = load_regions()
    raw = cv2.imread(args.image)
    if raw is None:
        sys.exit(f"file illeggibile: {args.image}")
    f = cv2.resize(raw, tuple(r["base_size"]), interpolation=cv2.INTER_AREA)
    out = f.copy()
    for kind, rects in (("shop", mv.locate_shop(f, r)), ("board", mv.locate_board(f, r))):
        print(f"{kind}: {len(rects)} carte")
        for i, rect in enumerate(rects):
            x, y, w, h = rect
            att, hp = nv.read_minion_stats(f, rect, kind)
            cx, cy = x + nv.STAT_CENTER, y + nv.STAT_DY[kind]
            print(f"  {kind}{i}: centro x={cx}  attacco={att}  vita={hp}")
            cv2.line(out, (cx, cy - 60), (cx, cy + 40), (0, 0, 255), 2)
            cv2.rectangle(out, (max(0, x - 40), cy - 22), (x + 147, cy + 22), (255, 200, 0), 1)
            cv2.putText(out, f"{att}/{hp}", (cx - 40, cy + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
    cv2.imwrite(args.out, out)
    print(f"Immagine scritta in {args.out}")


if __name__ == "__main__":
    main()
