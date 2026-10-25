"""Individuazione e riconoscimento dei minion.

Le carte sono centrate e il loro numero cambia, quindi non c'e' una griglia fissa:
- shop: si cercano gli stendardi viola sopra le carte (presenti anche sugli incantesimi);
- board: si cercano le gocce rosse della vita (solo minion), poi la griglia centrata le ordina.
Poi si ritaglia l'arte relativa al centro di ogni carta e la si riconosce confrontando il suo centro
(50x50 px) con le illustrazioni originali tramite cross-correlazione normalizzata.

Misure sui 25 slot degli screenshot reali (tests/fixtures), db completo di 279 carte:
- punteggio delle carte vere 0.82-0.94; incantesimi e minion fuori db 0.35-0.55 -> soglia 0.65;
- scala dei template: media 0.88 a 165 px, 0.87 a 185, 0.66 a 205, 0.60 a 145 -> basta la 165;
- a meta' risoluzione escono le stesse carte, 5x piu' veloce; con tutte le carte restano ~0.3 s a carta,
  quindi si filtra per tier e si usa una cache (CardReader).
"""
import json
import os
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "cards.json"
MAX_DISTANCE = 18          # distanza di Hamming massima per l'hash (solo test sintetici)
MATCH_CONFIDENCE = 0.65    # correlazione minima per accettare una carta
TEMPLATE_SCALE = 165       # lato in px a cui si porta l'illustrazione (poi dimezzato per la ricerca)
MIN_TEXTURE = 25.0         # dev. standard minima del ritaglio: il fumo viola sta a 12-14, le carte vere a 35+
CENTER = 50                # lato del ritaglio centrale confrontato
CARD_ART_DIRS = [ROOT / "data" / "card_art"]
if os.environ.get("HS_BG_CARD_ART"):
    CARD_ART_DIRS.insert(0, Path(os.environ["HS_BG_CARD_ART"]))


def _centers_x(mask, x0, min_area):
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, stats, cents = cv2.connectedComponentsWithStats(mask)
    return sorted(int(x0 + cents[i][0]) for i in range(1, n) if stats[i][4] >= min_area)


def _art_rect(cx, regions, y_key):
    a = regions["minion_art"]
    return [cx - a["w"] // 2, a[y_key], a["w"], a["h"]]


def locate_shop(frame, regions):
    """Rettangoli dell'arte delle carte dello shop (minion e incantesimi), da sinistra a destra."""
    x, y, w, h = regions["shop_pennant_strip"]
    hsv = cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2HSV)
    xs = _centers_x(cv2.inRange(hsv, (135, 100, 70), (170, 255, 255)), x, 300)
    return [_art_rect(cx, regions, "shop_y") for cx in xs]


def is_minion_card(frame, rect, regions):
    """True se la carta dello shop e' un minion: ha la goccia rossa della vita in basso a destra.

    Gli incantesimi non ce l'hanno (0 pixel rossi, contro 296-1099 dei minion negli screenshot reali)."""
    a = regions["minion_art"]
    cx, y = rect[0] + rect[2] // 2, a["shop_drop_y"]
    hsv = cv2.cvtColor(frame[y - 30:y + 30, cx + 20:cx + 64], cv2.COLOR_BGR2HSV)
    red = ((hsv[..., 0] <= 6) | (hsv[..., 0] >= 172)) & (hsv[..., 1] >= 110) & (hsv[..., 2] >= 90)
    return int(red.sum()) >= 60


def _fit_board(cues, grid):
    """Quanti minion e dove: i minion sono centrati con passo costante, quindi tra le disposizioni
    possibili (1..7 carte) si sceglie quella che meglio spiega gli indizi trovati. Cosi' un indizio
    falso (arte rossa) non conta e uno mancante (goccia coperta da un numero verde) non fa perdere la carta."""
    best, best_score = [], 0.0
    for n in range(1, 8):
        slots = [grid["center_x"] + grid["spacing"] * (i - (n - 1) / 2) for i in range(n)]
        hit = [any(abs(c - s) <= grid["tol"] for c in cues) for s in slots]
        stray = sum(1 for c in cues if all(abs(c - s) > grid["tol"] for s in slots))
        score = sum(hit) - 0.5 * (n - sum(hit)) - 0.25 * stray
        if score > best_score:
            best, best_score = slots, score
    return best


def locate_board(frame, regions):
    """Rettangoli dell'arte dei minion sul board, da sinistra a destra.

    Indizio per ogni minion: la goccia rossa della vita (anche piccola: se la vita e' potenziata il
    numero e' verde e copre quasi tutta la goccia). Le posizioni vengono poi imposte dalla griglia."""
    x, y, w, h = regions["board_strip"]
    hsv = cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 110, 90), (6, 255, 255)) | cv2.inRange(hsv, (172, 110, 90), (180, 255, 255))
    cues = [cx - regions["minion_art"]["drop_dx"] for cx in _centers_x(mask, x, 120)]
    return [_art_rect(round(s), regions, "board_y") for s in _fit_board(cues, regions["board_grid"])]


def _half(img):
    return cv2.resize(img, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)


def load_db(path=DB_PATH):
    """cards.json: lista di {id, name, tier, tribe, hash}. Se trova le illustrazioni (data/card_art/<id>.jpg
    oppure la cartella in $HS_BG_CARD_ART) aggiunge a ogni carta il template gia' scalato in '_tpl'."""
    if not Path(path).exists():
        return []
    with open(path) as f:
        cards = json.load(f)
    art_dir = next((d for d in CARD_ART_DIRS if d.is_dir()), None)
    for c in cards:
        if "hash" in c:
            try:
                import imagehash  # import tardivo: sul telefono (Chaquopy) serve solo il riconoscimento per template
                c["_hash"] = imagehash.hex_to_hash(c["hash"])
            except Exception:
                pass
        if art_dir and c.get("id"):
            ref = cv2.imread(str(art_dir / f"{c['id']}.jpg"))
            if ref is not None:
                c["_tpl"] = _half(cv2.resize(ref, (TEMPLATE_SCALE, TEMPLATE_SCALE)))
    return cards


def hash_crop(crop_bgr):
    import imagehash
    from PIL import Image
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    return imagehash.phash(Image.fromarray(rgb), hash_size=16)


def _center(crop_bgr):
    h, w = crop_bgr.shape[:2]
    cy, cx = h // 2, w // 2
    return crop_bgr[max(0, cy - CENTER // 2):cy + CENTER // 2, max(0, cx - CENTER // 2):cx + CENTER // 2]


def identify(crop_bgr, db, min_confidence=MATCH_CONFIDENCE, max_tier=None):
    """Ritorna (carta, punteggio); carta = None se nessun match abbastanza sicuro.

    Se il ritaglio e' troppo piatto per essere un'illustrazione (fumo, animazioni) ritorna (None, None):
    la cross-correlazione su una macchia di colore da' punteggi alti a caso (0.71 misurato).
    max_tier limita la ricerca alle carte fino a quel tier."""
    if not db or crop_bgr is None or crop_bgr.size == 0:
        return None, None

    if any("_tpl" in c for c in db):
        cc = _center(crop_bgr)
        if cc.shape[0] < 20 or cc.shape[1] < 20 or float(cc.std(axis=(0, 1)).mean()) < MIN_TEXTURE:
            return None, None
        probe = _half(cc)
        best_card, best_score = None, -1.0
        for c in db:
            tpl = c.get("_tpl")
            if tpl is None or (max_tier is not None and c.get("tier", 0) > max_tier):
                continue
            v = cv2.minMaxLoc(cv2.matchTemplate(tpl, probe, cv2.TM_CCOEFF_NORMED))[1]
            if v > best_score:
                best_card, best_score = c, v
        if best_card is not None and best_score >= min_confidence:
            return best_card, best_score
        return None, best_score

    # Senza illustrazioni: hash percettivo (usato dai test sintetici)
    h = hash_crop(crop_bgr)
    best, best_d = None, None
    for c in db:
        if "_hash" not in c:
            continue
        d = h - c["_hash"]
        if best_d is None or d < best_d:
            best, best_d = c, d
    if best_d is not None and best_d <= MAX_DISTANCE:
        return best, best_d
    return None, best_d


class CardReader:
    """identify() con cache: tra un frame e l'altro quasi tutti gli slot non cambiano, e una ricerca
    sull'intero db costa ~0.3 s. Il ritaglio centrale ridotto a 16x16 e' la chiave della cache."""

    SIG_DIFF = 8.0   # differenza media massima (0-255) per considerare uguale uno slot gia' visto

    def __init__(self, db, max_entries=64):
        self.db, self.max_entries, self._cache = db, max_entries, []

    def read(self, crop_bgr, max_tier=None):
        if crop_bgr is None or crop_bgr.size == 0 or not self.db:
            return None, None
        sig = cv2.resize(_center(crop_bgr), (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
        for key_sig, tier, result in self._cache:
            if tier == max_tier and float(np.abs(key_sig - sig).mean()) < self.SIG_DIFF:
                return result
        result = identify(crop_bgr, self.db, max_tier=max_tier)
        if result[1] is not None:  # un ritaglio piatto (transitorio) non si memorizza
            self._cache.append((sig, max_tier, result))
            del self._cache[:-self.max_entries]
        return result
