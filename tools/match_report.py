"""Mostra quali carte vengono riconosciute in uno o piu' screenshot di acquisto.

Uso: python tools/match_report.py shot.png [altri.png ...] [--sheet tavola.png]
Stampa per ogni slot nome, tier e punteggio; con --sheet scrive una tavola con il ritaglio del gioco
accanto all'illustrazione scelta, per controllare a occhio i match (rosso = sotto soglia).
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vision import crop, load_regions  # noqa: E402
from vision import minions as mv  # noqa: E402
from vision import numbers as nv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--sheet", help="file PNG della tavola di controllo")
    ap.add_argument("--no-tier-filter", action="store_true", help="cerca su tutte le carte, senza filtro di tier")
    args = ap.parse_args()

    regions = load_regions()
    db = mv.load_db()
    arts = {c["id"]: cv2.imread(str(next(d for d in mv.CARD_ART_DIRS if d.is_dir()) / f"{c['id']}.jpg")) for c in db
            if "_tpl" in c}
    if not arts:
        sys.exit("Nessuna illustrazione trovata: copia le immagini in data/card_art o imposta HS_BG_CARD_ART")
    reader = mv.CardReader(db)
    cells = []
    for path in args.images:
        img = cv2.imread(path)
        if img is None:
            print(f"{path}: file illeggibile")
            continue
        f = cv2.resize(img, tuple(regions["base_size"]), interpolation=cv2.INTER_AREA)
        tier = nv.count_stars(crop(f, regions["tavern_stars"])) or None
        if args.no_tier_filter:
            tier = None
        print(f"\n== {Path(path).name} (taverna {tier})")
        for kind, rects, max_tier in (("shop", mv.locate_shop(f, regions), tier),
                                      ("board", mv.locate_board(f, regions), tier + 1 if tier else None)):
            for i, rect in enumerate(rects):
                label = f"{kind}{i}"
                if kind == "shop" and not mv.is_minion_card(f, rect, regions):
                    print(f"  {label:7s} (incantesimo)")
                    continue
                c = crop(f, rect)
                t = time.time()
                card, score = reader.read(c, max_tier=max_tier)
                ms = (time.time() - t) * 1000
                if card:
                    print(f"  {label:7s} {card['name']} (T{card['tier']} {card.get('tribe') or '-'})  {score:.2f}  {ms:.0f} ms")
                else:
                    best = "piatto/animazione" if score is None else f"miglior punteggio {score:.2f}"
                    print(f"  {label:7s} ?  ({best})  {ms:.0f} ms")
                if args.sheet:
                    cell = np.full((185, 316, 3), 40, np.uint8)
                    left = cv2.resize(c, None, fx=1.5, fy=1.5)
                    cell[:left.shape[0], :left.shape[1]] = left
                    if card:
                        cell[:150, 160:310] = cv2.resize(arts[card["id"]], (150, 150))
                    cv2.putText(cell, f"{Path(path).stem[:12]} {label}", (2, 168), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
                    cv2.putText(cell, (f"{card['name'][:22]} {score:.2f}" if card else "?"), (2, 182),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 0) if card else (0, 0, 255), 1)
                    cells.append(cell)
    if args.sheet and cells:
        while len(cells) % 5:
            cells.append(np.zeros_like(cells[0]))
        cv2.imwrite(args.sheet, np.vstack([np.hstack(cells[i:i + 5]) for i in range(0, len(cells), 5)]))
        print(f"\nTavola scritta in {args.sheet}")


if __name__ == "__main__":
    main()
