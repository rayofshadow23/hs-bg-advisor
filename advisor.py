"""Euristiche e strategie per Hearthstone Battlegrounds, ispirate alle guide e curve di Jeefhs."""
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

# Minion di Tier 1 con token / economia (Jeef: priorità assoluta al Turno 1 per permettere doppio acquisto al Turno 3)
ECONOMY_TIER_1 = {
    "sellemental", "shell collector", "southsea busker", "deck swabber",
    "razorfen geomancer", "cord puller", "cord-puller", "picky eater",
    "harmless bonehead", "buzzing vermin", "suspicious prisonguard",
    "passenger", "alleycat", "murloc tidehunter", "scanchest", "flighty scout"
}

# Minion con Scudo Divino o Fendente (Cleave) che Jeef consiglia di mettere a sinistra (primi attaccanti)
FIRST_ATTACKERS = {
    "crackling cyclone", "deflect-o-bot", "foe reaper 4000", "wildfire elemental",
    "mecha-jaraxxus", "blade collector", "bronze warden", "annoy-o-tron",
    "glowscale", "righteous protector"
}

# Minion motore di scaling / passivi che Jeef consiglia di proteggere a destra dietro i Taunt
PROTECTED_MINIONS = {
    "titus rivendare", "baron rivendare", "brann bronzebeard", "drakkari enchanter",
    "moira bronzebeard", "nomi, kitchen nightmare", "kalecgos, arcane aspect",
    "mama bear", "lightfang enforcer", "peggy brittlebone"
}


@dataclass
class Tip:
    text: str
    action: str = "INFO"  # "BUY", "UPGRADE", "ROLL", "HOLD", "FREEZE", "INFO"
    card_index: Optional[int] = None
    card_name: Optional[str] = None
    role: str = ""  # "core", "add-on", "triple", "tribe", "tier", "freeze"
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
# Turno indicativo entro cui conviene aver raggiunto il tier (curva Jeef: T2 al turno 2, T3 al turno 5, T4 al 7)
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
    turn = state.turn
    max_gold = state.max_gold
    is_early_turn = (turn is not None and turn <= 4) or (max_gold is not None and max_gold <= 6)

    # ---------------------------------------------------------
    # 0. CURVE STANDARDIZZATE JEEFHS PER TURNO (Turni 1..5)
    # ---------------------------------------------------------

    # Turno 1 (3 oro): Priorità token/economia + divieto assoluto di roll
    is_turn_1 = (turn == 1) or (turn is None and max_gold == 3)
    if is_turn_1:
        econ_found = False
        for idx, m in enumerate(state.shop):
            if m.name != "?" and _norm(m.name) in ECONOMY_TIER_1:
                tips.append(Tip(
                    text=f"Turno 1 (Jeef): compra {m.name} per economia/token (fondamentale per doppio acquisto al Turno 3).",
                    action="BUY",
                    card_index=idx,
                    card_name=m.name,
                    role="core",
                    score=12.0
                ))
                econ_found = True
        if not econ_found and state.shop:
            valid_shop = [(i, m) for i, m in enumerate(state.shop) if m.name != "?"]
            if valid_shop:
                best_i, best_m = valid_shop[0]
                tips.append(Tip(
                    text=f"Turno 1: compra {best_m.name} (nessun token disponibile nello shop).",
                    action="BUY",
                    card_index=best_i,
                    card_name=best_m.name,
                    role="core",
                    score=9.0
                ))
        tips.append(Tip(
            text="Regola Jeef: NON rollare mai al Turno 1 (lo spreco di 1 oro compromette la curva iniziale).",
            action="HOLD",
            score=3.0
        ))

    # Turno 2 (4 oro): Upgrade obbligatorio al Tier 2
    is_turn_2 = (turn == 2) or (turn is None and max_gold == 4)
    if is_turn_2 and tier == 1 and gold >= (state.upgrade_cost or 4):
        tips.append(Tip(
            text="Turno 2: fai sempre l'upgrade alla taverna 2 (costa 4 oro).",
            action="UPGRADE",
            role="tier",
            score=15.0
        ))

    # Turno 3 (5 oro): Non livellare. Vendi token per 2 acquisti oppure compra 1 pezzo + magia/hero power
    is_turn_3 = (turn == 3) or (turn is None and max_gold == 5)
    if is_turn_3:
        has_econ_board = any(_norm(m.name) in ECONOMY_TIER_1 for m in state.board if m.name != "?")
        if has_econ_board:
            tips.append(Tip(
                text="Turno 3 (Curva Jeef): vendi il token/minion economico e compra 2 minion a 6 oro totali.",
                action="INFO",
                score=9.5
            ))
        else:
            tips.append(Tip(
                text="Turno 3 (Jeef): compra 1 minion solido + incantesimo da 1 oro (o conserva oro). Non salire di taverna e non rollare.",
                action="INFO",
                score=9.0
            ))

    # Turno 4 (6 oro): Doppio acquisto di stabilizzazione tempo (3+3 oro)
    is_turn_4 = (turn == 4) or (turn is None and max_gold == 6)
    if is_turn_4 and gold >= 6:
        tips.append(Tip(
            text="Turno 4 (Jeef): compra 2 minion per stabilizzare il board e non perdere vita prima di salire al Turno 5.",
            action="INFO",
            score=9.0
        ))

    # Turno 5 (7 oro): Upgrade a Taverna 3 (curva standard)
    is_turn_5 = (turn == 5) or (turn is None and max_gold == 7)
    upgrade_to_3_cost = state.upgrade_cost if state.upgrade_cost is not None else 5
    if is_turn_5 and tier <= 2 and gold >= upgrade_to_3_cost:
        tips.append(Tip(
            text="Turno 5: fai l'upgrade alla taverna 3 (curva standard a 7 oro).",
            action="UPGRADE",
            role="tier",
            score=14.0
        ))

    # ---------------------------------------------------------
    # 1. TRIPLE & TIMING DI SCOPERTA ("HOLDING TRIPLES" DI JEEF)
    # ---------------------------------------------------------
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
            # Regola timing tripli di Jeef:
            if tier == 2 and (turn is not None and turn < 5):
                tips.append(Tip(
                    text=f"Timing Triplo (Jeef): con Taverna 2 scopriresti un Tier 3. Valuta di congelare e scoprire al Turno 5 (Taverna 3) per un Tier 4 decisivo!",
                    action="INFO",
                    score=8.5
                ))
            elif tier == 3 and (turn is not None and turn >= 6):
                tips.append(Tip(
                    text="Timing Triplo (Jeef): se puoi salire a Taverna 4 a breve, conserva la tripla per scoprire un Tier 5 (motore di vittoria).",
                    action="INFO",
                    score=8.0
                ))

    # ---------------------------------------------------------
    # 1b. CARTE CHIAVE DELLE COMP (HSReplay Tier List)
    # ---------------------------------------------------------
    tips.extend(structured_key_card_tips(state))

    # ---------------------------------------------------------
    # 2. SALITA DI TIER PER TURNI AVANZATI O RECUPERO RITARDI
    # ---------------------------------------------------------
    cost, margin = (state.upgrade_cost, 0) if state.upgrade_cost else (UPGRADE_BASE_COST.get(tier), 1)
    if cost is not None and tier < _target_tier(turn) and gold >= cost - margin:
        if not any(t.action == "UPGRADE" for t in tips):
            tips.append(Tip(
                text=f"Sali alla taverna {tier + 1} (sei indietro rispetto al turno {turn}).",
                action="UPGRADE",
                role="tier",
                score=4.0
            ))

    # ---------------------------------------------------------
    # 3. SINERGIE DI TRIBU'
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 4. REGOLA DEL DIVIETO DI ROLL PRECOCE (Turni 1..4)
    # ---------------------------------------------------------
    if is_early_turn and 0 < gold < 3:
        tips.append(Tip(
            text="Regola Jeef: NON rollare nei turni 1-4. Conserva l'oro o compra incantesimi (ogni roll precoce sacrifica statistiche).",
            action="HOLD",
            score=3.5
        ))

    # ---------------------------------------------------------
    # 5. REGOLA DEL CONGELAMENTO ("NEVER FREEZE FOR ONE" DI JEEF)
    # ---------------------------------------------------------
    if gold <= 1:
        has_triple_in_shop = any(m.name != "?" and board_names.get(m.name, 0) >= 2 for m in state.shop)
        key_buys = [t for t in structured_key_card_tips(state) if t.action == "BUY"]

        if has_triple_in_shop:
            tips.append(Tip(
                text="Freeze (Jeef): CONGELA lo shop, c'e' una tripla da chiudere al prossimo turno.",
                action="FREEZE",
                role="freeze",
                score=7.5
            ))
        elif len(key_buys) >= 2:
            tips.append(Tip(
                text="Freeze (Jeef): CONGELA lo shop (ci sono almeno 2 carte chiave per il tuo board).",
                action="FREEZE",
                role="freeze",
                score=6.5
            ))
        elif len(key_buys) == 1 and not has_triple_in_shop:
            tips.append(Tip(
                text="Freeze (Jeef): NON congelare per una sola carta (sprecheresti il refresh naturale di inizio turno).",
                action="INFO",
                role="freeze",
                score=4.5
            ))

    # ---------------------------------------------------------
    # 6. POSIZIONAMENTO DEL BOARD (JEEF BOARD ORDERING)
    # ---------------------------------------------------------
    board_lower = {_norm(m.name) for m in state.board if m.name != "?"}
    if board_lower:
        if any(name in FIRST_ATTACKERS for name in board_lower):
            tips.append(Tip(
                text="Posizionamento (Jeef): minion con Scudo Divino o Fendente (Cleave) a sinistra per primi attacchi.",
                action="INFO",
                score=2.2
            ))
        if any(name in PROTECTED_MINIONS for name in board_lower):
            tips.append(Tip(
                text="Posizionamento (Jeef): proteggi Brann/Titus/Drakkari/motori passivi all'estrema destra dietro i Taunt.",
                action="INFO",
                score=2.1
            ))
        if len(state.board) >= 4:
            tips.append(Tip(
                text="Posizionamento (Jeef): posiziona i Taunt a destra per evitare che i contraccolpi colpiscano i tuoi attaccanti principali.",
                action="INFO",
                score=1.8
            ))

    # ---------------------------------------------------------
    # 7. GESTIONE DELL'ORO RIMASTO
    # ---------------------------------------------------------
    if gold >= 3 and not any(t.action == "BUY" for t in tips):
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
        elif not is_early_turn:
            tips.append(Tip(text="Fai roll dello shop o congela se ci sono buoni minion.", action="ROLL"))

    if gold == 0:
        tips.append(Tip(text="Oro finito: riordina il board e termina il turno.", action="HOLD"))

    if tips:
        tips = sorted(tips, key=lambda x: -x.score)
    return tips or [Tip(text="Nessun consiglio forte: usa l'oro per roll o acquisto.", action="INFO")]


def advise(state):
    """Ritorna una lista di stringhe con i consigli, dal piu' importante (retrocompatibilita')."""
    return [t.text for t in structured_advise(state)]
