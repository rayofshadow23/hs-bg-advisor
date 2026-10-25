"""Lettura dei numeri dallo schermo di Hearthstone.

Il font del gioco e' stilizzato (cifre bianche con contorno scuro su monete e gocce colorate), quindi
l'OCR sulla stringa intera e' inaffidabile. Ogni regione ha una preparazione dedicata, scelta provando
le varianti sugli screenshot reali in tests/fixtures. Il livello della taverna non si legge con l'OCR:
si contano le stelle del badge.
"""
from pathlib import Path

import cv2
import numpy as np
import pytesseract

DIGITS = "0123456789"
# regione -> (modalita' della maschera, psm di Tesseract)
READERS = {"upgrade_cost": ("wg", 8), "hero_health": ("white", 7), "hero_armor": ("otsu", 8)}


def _ocr(img, psm, whitelist=DIGITS):
    return pytesseract.image_to_string(
        img, config=f"--psm {psm} -c tessedit_char_whitelist={whitelist}").strip()


def _white_mask(crop, vmin=185, smax=70):
    return cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, vmin), (180, smax, 255))


def _prepare(crop, mode):
    """Immagine nero-su-bianco, ingrandita 4x, pronta per Tesseract."""
    if mode == "otsu":
        gray = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None, fx=4, fy=4,
                          interpolation=cv2.INTER_CUBIC)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return bw if bw.mean() > 127 else 255 - bw
    mask = _white_mask(crop)
    if mode == "wg":  # bianco oppure verde: i costi scontati sono verdi
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask = mask | cv2.inRange(hsv, (35, 90, 100), (85, 255, 255))
    mask = cv2.resize(mask, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(255 - mask, 14, 14, 14, 14, cv2.BORDER_CONSTANT, value=255)


def read_number(crop, mode="wg", psm=7):
    """Intero letto dal ritaglio, oppure None se Tesseract non trova solo cifre."""
    if crop is None or crop.size == 0:
        return None
    text = _ocr(_prepare(crop, mode), psm)
    return int(text) if text.isdigit() else None


def read_region(frame, regions, name):
    """Legge una delle regioni in READERS (upgrade_cost, hero_health, hero_armor)."""
    x, y, w, h = regions[name]
    mode, psm = READERS[name]
    return read_number(frame[y:y + h, x:x + w], mode, psm)


ZERO_TEMPLATE = Path(__file__).with_name("templates") / "digit_0.png"
ZERO_THRESHOLD = 0.75


def _looks_like_zero(glyph_mask):
    """Tesseract restituisce vuoto per lo 0 di questo font, quindi lo si riconosce col template
    digit_0.png (media di tre 0 reali del contatore oro). Gli 0 ottengono 0.88-0.97, i glifi 3/5/6
    al massimo 0.63. Piu' screenshot di 0 e di altre cifre renderebbero la soglia piu' affidabile."""
    tpl = cv2.imread(str(ZERO_TEMPLATE), cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        return False
    g = cv2.resize(glyph_mask, (tpl.shape[1], tpl.shape[0]), interpolation=cv2.INTER_AREA)
    return float(cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)[0][0]) >= ZERO_THRESHOLD


def read_gold(crop):
    """'0/5' -> (0, 5): oro corrente e massimo, oppure None.

    Ogni glifo si legge da solo (Tesseract sulla stringa intera sbaglia). Un glifo che Tesseract
    lascia vuoto viene confrontato col template dello 0."""
    if crop is None or crop.size == 0:
        return None
    mask = cv2.resize(_white_mask(crop), None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    boxes = sorted((s[0], s[1], s[2], s[3]) for s in stats[1:] if s[3] >= 110 and s[4] > 1500)
    left, right, slash = "", "", False
    for x, y, w, h in boxes:
        glyph = mask[y:y + h, x:x + w]
        ch = _ocr(cv2.copyMakeBorder(255 - glyph, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255),
                  8, DIGITS + "/")  # psm 8 legge 3/5/6/9; psm 10 restituisce vuoto per il 9
        if ch == "" and _looks_like_zero(glyph):
            ch = "0"
        if ch == "/":
            slash = True
        elif ch.isdigit():
            if slash:
                right += ch
            else:
                left += ch
    if left and not slash and not right:
        # Con il massimo a 10 (dal turno 8) il contatore mostra solo l'oro corrente, senza "/10".
        # Visto in un solo screenshot: 0 senza denominatore subito dopo il turno 7 (massimo 9).
        cur, mx = int(left), 10
    elif slash and left and right:
        cur, mx = int(left), int(right)
    else:
        return None
    return (cur, mx) if 0 <= cur <= mx <= 10 else None


def count_stars(crop, min_area=30):
    """Livello della taverna: numero di stelle dorate nel badge accanto a Bob."""
    if crop is None or crop.size == 0:
        return 0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (15, 120, 170), (34, 255, 255))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    return int(sum(1 for s in stats[1:] if s[4] >= min_area))


# Cifre di attacco (moneta a sinistra) e vita (goccia a destra) sotto ogni carta.
# Offset rispetto al rettangolo dell'illustrazione (vision.minions): verificati su shop e board del turno 8.
STAT_DY = {"shop": 122, "board": 129}
STAT_SPLIT = 56            # i glifi a sinistra di rect.x + 56 sono l'attacco, gli altri la vita
STAT_GLYPH_H = (28, 44)    # altezza plausibile di una cifra a 2000x900
STAT_GLYPH_W = (6, 32)


def _stat_mask(crop):
    """Cifre bianche (statistiche base) o verdi (potenziate) col loro contorno scuro."""
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    return _white_mask(crop, vmin=200) | cv2.inRange(hsv, (45, 190, 170), (80, 255, 255))


def read_minion_stats(frame, rect, kind="board"):
    """(attacco, vita) di una carta, ciascuno None se illeggibile. kind: 'shop' | 'board'.

    Si segmentano i glifi con le componenti connesse, scartando macchie fuori misura (arte chiara,
    scintille), poi si legge ogni cifra da sola come per l'oro."""
    x, y, _, _ = rect
    cy = y + STAT_DY[kind]
    x0, y0 = max(0, x - 15), max(0, cy - 22)
    win = frame[y0:cy + 22, x0:x + 137]
    if win.size == 0:
        return None, None
    m1 = _stat_mask(win)
    m1[:, x + 46 - x0:x + 68 - x0] = 0  # fascia centrale: solo arte della carta, mai cifre
    mask = cv2.resize(m1, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    glyphs = []
    for gx, gy, gw, gh, area in stats[1:]:
        if not (STAT_GLYPH_H[0] * 4 <= gh <= STAT_GLYPH_H[1] * 4 and STAT_GLYPH_W[0] * 4 <= gw <= STAT_GLYPH_W[1] * 4):
            continue
        if area < 0.25 * gw * gh:  # sottile/frastagliato: non e' una cifra
            continue
        glyphs.append((gx, gy, gw, gh))
    sides = {"att": [], "hp": []}
    split = (x + STAT_SPLIT - x0) * 4
    for gx, gy, gw, gh in sorted(glyphs):
        digit = mask[gy:gy + gh, gx:gx + gw]
        ch = _ocr(cv2.copyMakeBorder(255 - digit, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255), 8)
        if ch == "" and _looks_like_zero(digit):
            ch = "0"
        if ch.isdigit() and len(ch) == 1:
            sides["att" if gx + gw / 2 < split else "hp"].append(ch)
        else:  # una cifra illeggibile rende inaffidabile tutto il numero di quel lato
            sides["att" if gx + gw / 2 < split else "hp"].append(None)
    def num(chars):
        return int("".join(chars)) if chars and None not in chars else None
    return num(sides["att"]), num(sides["hp"])
