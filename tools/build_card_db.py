"""Costruisce cards.json con gli hash delle carte Battlegrounds.

Da eseguire sulla tua macchina (serve la rete). Scarica il JSON delle carte da HearthstoneJSON,
tiene i minion di Battlegrounds (quelli con techLevel) e calcola l'hash
dell'immagine di ogni carta.

Salva anche le illustrazioni 256x256 in data/card_art/<id>.jpg: servono al riconoscimento (vision/minions.py).

Uso: python tools/build_card_db.py [--out cards.json] [--art-dir data/card_art]
"""
import argparse
import io
import json
import sys
from pathlib import Path

import imagehash
import requests
from PIL import Image

CARDS_URL = "https://api.hearthstonejson.com/v1/latest/enUS/cards.json"
ART_URL = "https://art.hearthstonejson.com/v1/256x/{id}.jpg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "cards.json"))
    ap.add_argument("--art-dir", default=str(Path(__file__).resolve().parent.parent / "data" / "card_art"))
    ap.add_argument("--limit", type=int, default=0, help="solo per prove")
    args = ap.parse_args()

    cards = requests.get(CARDS_URL, timeout=60).json()
    bg = [c for c in cards if c.get("type") == "MINION" and c.get("techLevel")]
    if args.limit:
        bg = bg[: args.limit]
    out = []
    art_dir = Path(args.art_dir)
    art_dir.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(bg, 1):
        try:
            r = requests.get(ART_URL.format(id=c["id"]), timeout=30)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            (art_dir / f"{c['id']}.jpg").write_bytes(r.content)
        except Exception as e:  # noqa: BLE001
            print(f"salto {c['id']}: {e}", file=sys.stderr)
            continue
        out.append({
            "id": c["id"],
            "name": c["name"],
            "tier": c["techLevel"],
            "tribe": (c.get("race") or "").title(),
            "hash": str(imagehash.phash(img, hash_size=16)),
        })
        print(f"[{i}/{len(bg)}] {c['name']}")
    with open(args.out, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Scritto {args.out} ({len(out)} carte)")


if __name__ == "__main__":
    main()
