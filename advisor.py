"""Euristiche v1 per i consigli in fase di acquisto. Solo suggerimenti: nessun input al telefono."""
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

COMPS_PATH = Path(__file__).resolve().parent / "data" / "comps.json"
# Peso della comp in base al tier HSReplay (1 = migliore); le carte add-on pesano la meta' dei core.
TIER_WEIGHT = {1: 3, 2: 2, 3: 1}
ADDON_FACTOR = 0.5
MIN_SCORE = 2  # sotto questa soglia la carta non viene segnalata


@dataclass
class Tip:
    text: str
    action: str = "INFO"  # "BUY", "UPGRADE", "ROLL", "HOLD", "INFO"
    card_index: Optional[int] = None
    card_name: Optional[str] = None
    role: str = ""  # "core", "add-on", "triple", "tribe", "tier"
    score: float = 0.0
    comp_name: str = ""


def load_comps(path=COMPS_PATH):
    """Carica le comp generate da tools/parse_hsreplay_comps.py. Lista vuota se il file manca."""
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)["comps"]


COMPS = load_comps()


def _norm(name):
    return name.strip().lower()


def structured_key_card_tips(state, comps=None):
    """Segnala le carte dello shop che servono a una comp HSReplay in formato strutturato.

    Punteggio = peso del tier della comp (x0.5 se la carta e' solo add-on)
                + carte core gia' sul board (1 ciascuna) + add-on gia' sul board (0.5 ciascuna).
    Si segnala solo sopra MIN_SCORE: una comp forte, oppure una gia' avviata."""
    comps = COMPS if comps is None else comps
    board = {_norm(m.name) for m in state.board if m.name != "?"}
    tips = []
    for idx, m in enumerate(state.shop):
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
            tips.append(Tip(
                text=f"{m.name}: {role} di {c['name']} (Tier {c['tier']}, ne hai {have} sul board).",
                action="BUY",
                card_index=idx,
                card_name=m.name,
                role=role,
                score=score,
                comp_name=c["name"]
            ))
    return sorted(tips, key=lambda x: -x.score)


def key_card_tips(state, comps=None):
    """Ritorna la lista di consigli testuali per le carte chiave (retrocompatibilita')."""
    return [t.text for t in structured_key_card_tips(state, comps)]


# Costo base per salire al tier successivo (scende di 1 ogni turno senza salire; qui usiamo il massimo)
UPGRADE_BASE_COST = {1: 5, 2: 7, 3: 8, 4: 11, 5: 11}
# Turno indicativo entro cui conviene aver raggiunto il tier (guida approssimativa: turno 2 -> tier 2)
TARGET_TIER_BY_TURN = {2: 2, 5: 3, 7: 4, 9: 5, 11: 6}


def _target_tier(turn):
    target = 1
    for t, tier in TARGET_TIER_BY_TURN.items():
        if turn is not None and turn >= t:
            target = tier
    return target


def structured_advise(state):
    """Ritorna una lista di oggetti Tip con dettagli per rendering e automazioni."""
    if state.phase != "recruit":
        msg = "In attesa della fase di acquisto..." if state.phase != "combat" else "Combattimento in corso."
        return [Tip(text=msg, action="INFO")]

    tips = []
    gold = state.gold or 0
    tier = state.tavern_tier or 1

    # 0. Regola fondamentale Turno 2: si fa SEMPRE l'upgrade della taverna al Tier 2 (costo 4 oro)
    is_turn_2 = (state.turn == 2) or (state.turn is None and state.max_gold == 4)
    if is_turn_2 and tier == 1 and gold >= (state.upgrade_cost or 4):
        tips.append(Tip(
            text="Turno 2: fai sempre l'upgrade alla taverna 2 (costa 4 oro).",
            action="UPGRADE",
            role="tier",
            score=15.0
        ))

    # 1. Triple: due copie sul board + una nello shop
    board_names = Counter(m.name for m in state.board if m.name != "?")
    for idx, m in enumerate(state.shop):
        if m.name != "?" and board_names.get(m.name, 0) >= 2:
            tips.append(Tip(
                text=f"Compra {m.name}: completa un triplo.",
                action="BUY",
                card_index=idx,
                card_name=m.name,
                role="triple",
                score=10.0
            ))

    # 1b. Carte chiave delle comp piu' forti
    tips.extend(structured_key_card_tips(state))

    # 2. Salita di tier per turni successivi o ritardi rispetto alla curva
    cost, margin = (state.upgrade_cost, 0) if state.upgrade_cost else (UPGRADE_BASE_COST.get(tier), 1)
    if cost is not None and tier < _target_tier(state.turn) and gold >= cost - margin:
        if not any(t.action == "UPGRADE" for t in tips):
            tips.append(Tip(
                text=f"Sali alla taverna {tier + 1} (sei indietro rispetto al turno {state.turn}).",
                action="UPGRADE",
                role="tier",
                score=4.0
            ))

    # 3. Sinergie di tribu'
    tribes = Counter(m.tribe for m in state.board if m.tribe)
    if tribes:
        main_tribe, n = tribes.most_common(1)[0]
        for idx, m in enumerate(state.shop):
            if m.tribe == main_tribe and n >= 2:
                tips.append(Tip(
                    text=f"{m.name} e' della tua tribu' principale ({main_tribe}).",
                    action="BUY",
                    card_index=idx,
                    card_name=m.name,
                    role="tribe",
                    score=2.0
                ))

    # 4. Oro rimasto
    if gold >= 3 and not tips:
        valid_shop = [(i, m) for i, m in enumerate(state.shop) if m.name != "?"]
        if valid_shop:
            high_idx, high = max(valid_shop, key=lambda x: x[1].tier)
            tips.append(Tip(
                text=f"Valuta {high.name} (tier {high.tier}) oppure fai roll.",
                action="BUY",
                card_index=high_idx,
                card_name=high.name,
                role="tier",
                score=1.0
            ))
        else:
            tips.append(Tip(text="Fai roll dello shop o congela se ci sono buoni minion.", action="ROLL"))
    if gold == 0:
        tips.append(Tip(text="Oro finito: riordina il board e termina il turno.", action="HOLD"))
    if tips:
        tips = sorted(tips, key=lambda x: -x.score)
    return tips or [Tip(text="Nessun consiglio forte: usa l'oro per roll o acquisto.", action="INFO")]


def advise(state):
    """Ritorna una lista di stringhe con i consigli, dal piu' importante (retrocompatibilita')."""
    return [t.text for t in structured_advise(state)]
