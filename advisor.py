"""Euristiche v1 per i consigli in fase di acquisto. Solo suggerimenti: nessun input al telefono."""
import json
from collections import Counter
from pathlib import Path

COMPS_PATH = Path(__file__).resolve().parent / "data" / "comps.json"
# Peso della comp in base al tier HSReplay (1 = migliore); le carte add-on pesano la meta' dei core.
TIER_WEIGHT = {1: 3, 2: 2, 3: 1}
ADDON_FACTOR = 0.5
MIN_SCORE = 2  # sotto questa soglia la carta non viene segnalata


def load_comps(path=COMPS_PATH):
    """Carica le comp generate da tools/parse_hsreplay_comps.py. Lista vuota se il file manca."""
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)["comps"]


COMPS = load_comps()


def _norm(name):
    return name.strip().lower()


def key_card_tips(state, comps=None):
    """Segnala le carte dello shop che servono a una comp HSReplay.

    Punteggio = peso del tier della comp (x0.5 se la carta e' solo add-on)
                + carte core gia' sul board (1 ciascuna) + add-on gia' sul board (0.5 ciascuna).
    Si segnala solo sopra MIN_SCORE: una comp forte, oppure una gia' avviata."""
    comps = COMPS if comps is None else comps
    board = {_norm(m.name) for m in state.board if m.name != "?"}
    tips = []
    for m in state.shop:
        if m.name == "?":
            continue
        name = _norm(m.name)
        best = None
        for c in comps:
            core = {_norm(x["name"]) for x in c["core"]}
            addons = {_norm(x["name"]) for x in c["addons"]} - core
            if name in core:
                role, base = "core", TIER_WEIGHT.get(c["tier"], 0)
            elif name in addons:
                role, base = "add-on", TIER_WEIGHT.get(c["tier"], 0) * ADDON_FACTOR
            else:
                continue
            have_core, have_add = len(core & board), len(addons & board)
            score = base + have_core + ADDON_FACTOR * have_add
            if best is None or score > best[0]:
                best = (score, c, role, have_core + have_add)
        if best and best[0] >= MIN_SCORE:
            score, c, role, have = best
            tips.append((score, f"{m.name}: {role} di {c['name']} (Tier {c['tier']}, ne hai {have} sul board)."))
    return [t for _, t in sorted(tips, key=lambda x: -x[0])]


# Costo base per salire al tier successivo (scende di 1 ogni turno senza salire; qui usiamo il massimo)
UPGRADE_BASE_COST = {1: 5, 2: 7, 3: 8, 4: 11, 5: 11}
# Turno indicativo entro cui conviene aver raggiunto il tier (guida approssimativa)
TARGET_TIER_BY_TURN = {3: 2, 5: 3, 7: 4, 9: 5, 11: 6}


def _target_tier(turn):
    target = 1
    for t, tier in TARGET_TIER_BY_TURN.items():
        if turn is not None and turn >= t:
            target = tier
    return target


def advise(state):
    """Ritorna una lista di stringhe con i consigli, dal piu' importante."""
    if state.phase != "recruit":
        return ["In attesa della fase di acquisto..." if state.phase != "combat" else "Combattimento in corso."]

    tips = []
    gold = state.gold or 0
    tier = state.tavern_tier or 1

    # 1. Triple: due copie sul board + una nello shop
    board_names = Counter(m.name for m in state.board if m.name != "?")
    for m in state.shop:
        if m.name != "?" and board_names.get(m.name, 0) >= 2:
            tips.append(f"Compra {m.name}: completa un triplo.")

    # 1b. Carte chiave delle comp piu' forti
    tips.extend(key_card_tips(state))

    # 2. Salita di tier
    # Costo letto dallo schermo se disponibile (e' gia' scontato); altrimenti il costo pieno, con 1 oro di margine
    cost, margin = (state.upgrade_cost, 0) if state.upgrade_cost else (UPGRADE_BASE_COST.get(tier), 1)
    if cost is not None and tier < _target_tier(state.turn) and gold >= cost - margin:
        tips.append(f"Sali alla taverna {tier + 1} (sei indietro rispetto al turno {state.turn}).")

    # 3. Sinergie di tribu'
    tribes = Counter(m.tribe for m in state.board if m.tribe)
    if tribes:
        main_tribe, n = tribes.most_common(1)[0]
        for m in state.shop:
            if m.tribe == main_tribe and n >= 2:
                tips.append(f"{m.name} e' della tua tribu' principale ({main_tribe}).")

    # 4. Oro rimasto
    if gold >= 3 and not tips:
        high = max(state.shop, key=lambda m: m.tier, default=None)
        if high and high.name != "?":
            tips.append(f"Valuta {high.name} (tier {high.tier}) oppure fai roll.")
        else:
            tips.append("Fai roll dello shop o congela se ci sono buoni minion.")
    if gold == 0:
        tips.append("Oro finito: riordina il board e termina il turno.")
    return tips or ["Nessun consiglio forte: usa l'oro per roll o acquisto."]
