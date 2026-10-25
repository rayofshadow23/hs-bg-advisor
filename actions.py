"""Azioni legali nella fase di acquisto e loro effetto sullo stato (base per ricerca e valutazione).

Regole di gioco usate (valori standard di Battlegrounds):
  comprare un minion 3 oro, vendere +1 oro, roll 2 oro, salire di taverna = state.upgrade_cost,
  board massimo 7 minion, mano massima 10 carte. Gli incantesimi della taverna costano SPELL_COST
  (approssimazione: la maggior parte costa 1) e non occupano posto sul board.
Limiti noti: la mano e il congelamento non sono ancora letti dallo schermo (state.hand vuota = sconosciuta),
quindi PLAY compare solo quando la mano e' nota; i tripli non sono ancora simulati in apply().
"""
import copy
from dataclasses import dataclass
from typing import Optional

from advisor import UPGRADE_BASE_COST
from state import GameState, Minion

BUY_COST, SELL_REFUND, ROLL_COST, SPELL_COST = 3, 1, 2, 1
BOARD_MAX, HAND_MAX, MAX_TIER = 7, 10, 6

BUY, SELL, PLAY, ROLL, LEVEL_UP, FREEZE, END_TURN = "BUY", "SELL", "PLAY", "ROLL", "LEVEL_UP", "FREEZE", "END_TURN"


@dataclass(frozen=True)
class Action:
    kind: str
    index: Optional[int] = None    # posizione nello shop (BUY), sul board (SELL) o nella mano (PLAY)
    source: str = ""               # SELL: "board" | "hand"

    def __str__(self):
        extra = f" {self.source}[{self.index}]" if self.index is not None else ""
        return f"{self.kind}{extra}"


def level_up_cost(state):
    """Costo per salire di taverna: quello letto, altrimenti il costo massimo di tabella."""
    if state.upgrade_cost is not None:
        return state.upgrade_cost
    return UPGRADE_BASE_COST.get(state.tavern_tier or 1)


def buy_cost(card):
    return SPELL_COST if card.is_spell else BUY_COST


def legal_actions(state: GameState):
    """Tutte le azioni possibili adesso. Fuori dalla fase di acquisto c'e' solo l'attesa (lista vuota)."""
    if state.phase != "recruit" or state.gold is None:
        return []
    gold, acts = state.gold, []
    hand_full = len(state.hand) >= HAND_MAX
    for i, card in enumerate(state.shop):
        if gold >= buy_cost(card) and (card.is_spell or not hand_full):
            acts.append(Action(BUY, i))
    for i, card in enumerate(state.hand):
        if not card.is_spell and len(state.board) < BOARD_MAX:
            acts.append(Action(PLAY, i))
    for i in range(len(state.board)):
        acts.append(Action(SELL, i, "board"))
    for i in range(len(state.hand)):
        acts.append(Action(SELL, i, "hand"))
    if gold >= ROLL_COST:
        acts.append(Action(ROLL))
    cost = level_up_cost(state)
    if state.tavern_tier is not None and state.tavern_tier < MAX_TIER and cost is not None and gold >= cost:
        acts.append(Action(LEVEL_UP))
    if state.shop:
        acts.append(Action(FREEZE))
    acts.append(Action(END_TURN))
    return acts


def apply(state: GameState, action: Action) -> GameState:
    """Nuovo stato dopo l'azione (lo stato di partenza non cambia). Solleva ValueError se illegale.

    ROLL lascia lo shop vuoto (le carte nuove sono sconosciute: lo gestira' la valutazione a valore atteso)."""
    if action not in legal_actions(state):
        raise ValueError(f"azione non legale: {action}")
    st = copy.deepcopy(state)
    if action.kind == BUY:
        card = st.shop.pop(action.index)
        st.gold -= buy_cost(card)
        if not card.is_spell:
            st.hand.append(card)
    elif action.kind == PLAY:
        st.board.append(st.hand.pop(action.index))
    elif action.kind == SELL:
        (st.board if action.source == "board" else st.hand).pop(action.index)
        st.gold += SELL_REFUND
    elif action.kind == ROLL:
        st.gold -= ROLL_COST
        st.shop, st.frozen = [], False
    elif action.kind == LEVEL_UP:
        st.gold -= level_up_cost(st)
        st.tavern_tier += 1
        st.upgrade_cost = UPGRADE_BASE_COST.get(st.tavern_tier)
    elif action.kind == FREEZE:
        st.frozen = not st.frozen
    elif action.kind == END_TURN:
        st.phase = "combat"
    return st
