"""Lettura dei numeri dallo schermo di Hearthstone.

Il font del gioco e' stilizzato (cifre bianche con contorno scuro su monete e gocce colorate),
quindi il riconoscimento e' basato sul template matching a correlazione normalizzata delle singole
cifre (0-9 e '/') estratte ad alta fedelta'. Questo metodo e' deterministico, non richiede binari
esterni come Tesseract, ed e' ottimizzato per l'esecuzione in tempo reale su dispositivi mobili (<20ms).
Il livello della taverna non usa cifre: si contano le stelle dorate del badge.
"""
from pathlib import Path

import cv2
import numpy as np

DIGITS = "0123456789"
# regione -> modalita' della maschera
READERS = {"upgrade_cost": "wg", "hero_health": "white", "hero_armor": "otsu"}

DIGITS_TEMPLATE_DIR = Path(__file__).with_name("templates") / "digits"
_DIGIT_TEMPLATES = None


def _load_digit_templates():
    """Carica i template delle cifre (0-9 e '/') normalizzati a 64x64 su canvas nero."""
    global _DIGIT_TEMPLATES
    if _DIGIT_TEMPLATES is not None:
        return _DIGIT_TEMPLATES
    _DIGIT_TEMPLATES = {}
    if not DIGITS_TEMPLATE_DIR.exists():
        return _DIGIT_TEMPLATES
    for p in DIGITS_TEMPLATE_DIR.glob("*.png"):
        raw_name = p.stem.split("_")[0]
        char = "/" if raw_name == "slash" else raw_name
        tpl = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if tpl is not None:
            _DIGIT_TEMPLATES.setdefault(char, []).append(tpl)
    return _DIGIT_TEMPLATES


def _normalize_glyph(img, target_size=(64, 64)):
    """Normalizza un glifo binario: rimuove rumore/spruzzi sottili e centra sul canvas preservando le proporzioni."""
    if img is None or img.size == 0:
        return None
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    row_sums = (bw > 0).sum(axis=1)
    col_sums = (bw > 0).sum(axis=0)
    if not np.any(row_sums) or not np.any(col_sums):
        return None

    # Rimuove artefatti e sbavature sottili ai bordi (es. riflessi di carte)
    max_w = row_sums.max()
    max_h = col_sums.max()
    valid_rows = np.where(row_sums >= 0.15 * max_w)[0]
    valid_cols = np.where(col_sums >= 0.15 * max_h)[0]
    if len(valid_rows) == 0 or len(valid_cols) == 0:
        return None

    trimmed = bw[valid_rows[0]:valid_rows[-1] + 1, valid_cols[0]:valid_cols[-1] + 1]
    th, tw = trimmed.shape

    # Ridimensiona mantenendo il rapporto d'aspetto
    scale = min((target_size[0] - 8) / th, (target_size[1] - 8) / tw)
    nw, nh = max(1, int(round(tw * scale))), max(1, int(round(th * scale)))
    scaled = cv2.resize(trimmed, (nw, nh), interpolation=cv2.INTER_AREA)

    canvas = np.zeros(target_size, dtype=np.uint8)
    y_off = (target_size[0] - nh) // 2
    x_off = (target_size[1] - nw) // 2
    canvas[y_off:y_off + nh, x_off:x_off + nw] = scaled
    return canvas


def match_glyph(glyph_mask, min_confidence=0.55):
    """Riconosce una singola cifra o '/' tramite cross-correlazione normalizzata col dizionario di template.

    Restituisce (carattere, punteggio).
    """
    norm = _normalize_glyph(glyph_mask)
    if norm is None:
        return "", 0.0

    templates = _load_digit_templates()
    best_ch, best_score = "", -1.0
    for ch, tpl_list in templates.items():
        for tpl in tpl_list:
            score = float(cv2.matchTemplate(norm, tpl, cv2.TM_CCOEFF_NORMED)[0][0])
            if score > best_score:
                best_score = score
                best_ch = ch

    if best_score < min_confidence:
        return "", best_score
    return best_ch, best_score


def _looks_like_zero(glyph_mask):
    """Compatibilita': riconosce se un ritaglio e' uno zero."""
    ch, score = match_glyph(glyph_mask, min_confidence=0.60)
    return ch == "0"


def _white_mask(crop, vmin=185, smax=70):
    return cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, vmin), (180, smax, 255))


def read_number(crop, mode="wg", psm=None):
    """Intero letto dal ritaglio tramite template matching, oppure None se non trova cifre valide."""
    if crop is None or crop.size == 0:
        return None
    if mode == "otsu":
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        mask = bw if bw.mean() < 127 else 255 - bw
    else:
        mask = _white_mask(crop)
        if mode == "wg":  # bianco oppure verde: i costi scontati sono verdi
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            mask = mask | cv2.inRange(hsv, (35, 90, 100), (85, 255, 255))
        mask = cv2.resize(mask, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    boxes = [s_i for s_i in stats[1:] if s_i[1] > 10 and s_i[3] >= 80 and s_i[4] >= 1000]
    boxes.sort(key=lambda b: b[0])

    digits = []
    for gx, gy, gw, gh, _ in boxes:
        glyph = mask[gy:gy + gh, gx:gx + gw]
        ch, _ = match_glyph(glyph)
        if ch.isdigit():
            digits.append(ch)

    return int("".join(digits)) if digits else None


def read_region(frame, regions, name):
    """Legge una delle regioni in READERS (upgrade_cost, hero_health, hero_armor)."""
    x, y, w, h = regions[name]
    mode = READERS.get(name, "wg")
    if isinstance(mode, tuple):
        mode = mode[0]
    return read_number(frame[y:y + h, x:x + w], mode)


def read_gold(crop):
    """'0/5' -> (0, 5): oro corrente e massimo, oppure None.

    Ogni glifo si legge con template matching. Con il massimo a 10 (dal turno 8)
    il contatore mostra solo l'oro corrente, senza '/10'.
    """
    if crop is None or crop.size == 0:
        return None
    mask = cv2.resize(_white_mask(crop), None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    boxes = sorted((s[0], s[1], s[2], s[3]) for s in stats[1:] if s[3] >= 100 and s[4] > 1200)
    left, right, slash = "", "", False
    for x, y, w, h in boxes:
        glyph = mask[y:y + h, x:x + w]
        ch, _ = match_glyph(glyph)
        if ch == "/":
            slash = True
        elif ch.isdigit():
            if slash:
                right += ch
            else:
                left += ch
    if left and not slash and not right:
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
# Offset rispetto al rettangolo dell'illustrazione (vision.minions): verificati su shop e board.
STAT_DY = {"shop": 122, "board": 129}
STAT_CENTER = 52           # centro della carta rispetto a rect.x: a sinistra l'attacco, a destra la vita
STAT_DEAD = 8              # nessuna cifra ha il centro entro +-8 px dal centro della carta (li' c'e' solo arte)
STAT_REACH = 86            # oltre meta' del passo tra le carte (172.5 / 2) il glifo e' del vicino
STAT_GLYPH_H = (22, 46)    # altezza plausibile di una cifra a 2000x900 (con 3 cifre il font e' piu' piccolo)
STAT_GLYPH_W = (5, 60)     # oltre ~30 e' quasi certamente piu' di una cifra fusa: si divide
STAT_DIGIT_ASPECT = 0.72   # larghezza/altezza tipica di una cifra


def _stat_mask(crop):
    """Cifre bianche (statistiche base) o verdi (potenziate, anche piu' chiare sulle carte dorate)."""
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    return _white_mask(crop, vmin=200) | cv2.inRange(hsv, (40, 140, 160), (80, 255, 255))


def _split_wide(gx, gy, gw, gh, mask):
    """Le cifre ravvicinate (numeri a 3 cifre) si fondono in un'unica componente: la si divide in parti
    uguali, tagliando dove la colonna di pixel bianchi e' piu' scarsa vicino al taglio ideale."""
    n = max(1, round(gw / (STAT_DIGIT_ASPECT * gh)))
    if n == 1:
        return [(gx, gy, gw, gh)]
    cols = (mask[gy:gy + gh, gx:gx + gw] > 0).sum(axis=0)
    cuts = [0]
    for k in range(1, n):
        ideal = int(round(k * gw / n))
        lo, hi = max(cuts[-1] + 1, ideal - gw // (n * 4)), min(gw - 1, ideal + gw // (n * 4))
        cuts.append(lo + int(np.argmin(cols[lo:hi + 1])) if hi >= lo else ideal)
    cuts.append(gw)
    return [(gx + a, gy, b - a, gh) for a, b in zip(cuts, cuts[1:]) if b - a > 4]


def read_minion_stats(frame, rect, kind="board"):
    """(attacco, vita) di una carta, ciascuno None se illeggibile. kind: 'shop' | 'board'.

    Si segmentano i glifi con le componenti connesse, scartando macchie fuori misura (arte chiara,
    scintille), si dividono quelli fusi, poi si riconosce ogni cifra tramite template matching.
    Attacco e vita si distinguono dalla posizione rispetto al centro della carta."""
    x, y, _, _ = rect
    cy = y + STAT_DY[kind]
    x0, y0 = max(0, x - 40), max(0, cy - 22)
    win = frame[y0:cy + 22, x0:x + 147]
    if win.size == 0:
        return None, None
    mask = cv2.resize(_stat_mask(win), None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    glyphs = []
    for gx, gy, gw, gh, area in stats[1:]:
        if not (STAT_GLYPH_H[0] * 4 <= gh <= STAT_GLYPH_H[1] * 4 and STAT_GLYPH_W[0] * 4 <= gw <= STAT_GLYPH_W[1] * 4):
            continue
        if area < 0.25 * gw * gh:  # sottile/frastagliato: non e' una cifra
            continue
        if gx <= 1 or gx + gw >= mask.shape[1] - 1:  # tagliato dal bordo della finestra: cifra del vicino
            continue
        glyphs.extend(_split_wide(gx, gy, gw, gh, mask))
    sides = {"att": [], "hp": []}
    for gx, gy, gw, gh in sorted(glyphs):
        rel = (gx + gw / 2) / 4 + x0 - (x + STAT_CENTER)
        if abs(rel) > STAT_REACH or abs(rel) < STAT_DEAD:
            continue
        digit = mask[gy:gy + gh, gx:gx + gw]
        ch, _ = match_glyph(digit)
        side = "att" if rel < 0 else "hp"
        sides[side].append(ch if len(ch) == 1 and ch.isdigit() else None)  # una cifra illeggibile -> numero None

    def num(chars):
        return int("".join(chars)) if chars and None not in chars else None
    return num(sides["att"]), num(sides["hp"])


STAT_GROUP_PITCH = 1.05    # tra i centri di due cifre dello stesso numero (in altezze di cifra): oltre e' un altro numero


def _glyphs_in(win):
    """Glifi-cifra di una finestra (x, larghezza, altezza, maschera 4x) ordinati da sinistra; cifre fuse divise."""
    mask = cv2.resize(_stat_mask(win), None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    out = []
    for gx, gy, gw, gh, area in stats[1:]:
        if not (STAT_GLYPH_H[0] * 4 <= gh <= STAT_GLYPH_H[1] * 4 and STAT_GLYPH_W[0] * 4 <= gw <= STAT_GLYPH_W[1] * 4):
            continue
        if area < 0.25 * gw * gh or gx <= 1 or gx + gw >= mask.shape[1] - 1:
            continue
        out.extend(_split_wide(gx, gy, gw, gh, mask))
    return sorted(out), mask


def _read_glyph(mask, g):
    gx, gy, gw, gh = g
    digit = mask[gy:gy + gh, gx:gx + gw]
    ch, _ = match_glyph(digit)
    if len(ch) == 1 and ch.isdigit():
        return ch
    # macchia quadrata e illeggibile (arte chiara fra le due cifre): non e' una cifra, si ignora
    return "" if 0.9 <= gw / gh <= 1.4 else None


def read_strip_stats(frame, rects, kind="board"):
    """[(attacco, vita), ...] per tutte le carte di una riga, indipendente dalla posizione esatta dei centri.

    Le cifre di tutta la riga si raggruppano in numeri (una cifra dello stesso numero dista circa un'altezza
    di cifra dalla precedente, un altro numero molto di piu'). Con N carte ci sono 2N numeri, in ordine
    attacco, vita, attacco, vita...: si abbinano in sequenza. Con il board a 6-7 carte il passo tra le carte
    cambia e i centri della griglia sono sfasati: questo evita di dipendere da loro. Se i numeri non sono 2N
    (carta senza statistiche, cifra persa) si torna alla lettura carta per carta."""
    if not rects:
        return []
    cy = rects[0][1] + STAT_DY[kind]
    x0 = max(0, min(r[0] for r in rects) - 90)
    win = frame[max(0, cy - 22):cy + 22, x0:max(r[0] for r in rects) + 200]
    if win.size == 0:
        return [(None, None)] * len(rects)
    glyphs, mask = _glyphs_in(win)
    groups = []
    for g in glyphs:
        if groups:
            prev = groups[-1][-1]
            pitch = (g[0] + g[2] / 2) - (prev[0] + prev[2] / 2)
            if pitch <= STAT_GROUP_PITCH * (g[3] + prev[3]) / 2:
                groups[-1].append(g)
                continue
        groups.append([g])
    if len(groups) != 2 * len(rects):
        return [read_minion_stats(frame, r, kind) for r in rects]
    nums = []
    for grp in groups:
        chars = [c for c in (_read_glyph(mask, g) for g in grp) if c != ""]
        nums.append(int("".join(chars)) if chars and None not in chars else None)
    return list(zip(nums[0::2], nums[1::2]))
