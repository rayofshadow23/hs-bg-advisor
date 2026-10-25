import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import actions as A  # noqa: E402
from actions import Action  # noqa: E402
from state import GameState, Minion  # noqa: E402


def mk(gold=5, tier=2, shop=None, board=None, hand=None, upgrade=6):
    return GameState(phase="recruit", gold=gold, max_gold=gold, tavern_tier=tier, upgrade_cost=upgrade,
                     shop=shop if shop is not None else [Minion("A", 1), Minion("B", 2)],
                     board=board or [], hand=hand or [])


def kinds(state):
    return [str(a) for a in A.legal_actions(state)]


def test_no_actions_outside_recruit():
    assert A.legal_actions(GameState(phase="combat", gold=5)) == []
    assert A.legal_actions(GameState(phase="recruit", gold=None)) == []


def test_buy_needs_three_gold():
    assert Action(A.BUY, 0) in A.legal_actions(mk(gold=3))
    assert not any(a.kind == A.BUY for a in A.legal_actions(mk(gold=2)))


def test_spell_costs_one_and_ignores_full_hand():
    spell = Minion("(incantesimo)", is_spell=True)
    full = [Minion(f"H{i}") for i in range(10)]
    st = mk(gold=1, shop=[spell, Minion("A", 1)], hand=full)
    assert [a for a in A.legal_actions(st) if a.kind == A.BUY] == [Action(A.BUY, 0)]


def test_buy_blocked_with_full_hand():
    st = mk(gold=6, hand=[Minion(f"H{i}") for i in range(10)])
    assert not any(a.kind == A.BUY for a in A.legal_actions(st))


def test_roll_and_level_up_thresholds():
    assert Action(A.ROLL) in A.legal_actions(mk(gold=2))
    assert Action(A.ROLL) not in A.legal_actions(mk(gold=1))
    assert Action(A.LEVEL_UP) in A.legal_actions(mk(gold=6, upgrade=6))
    assert Action(A.LEVEL_UP) not in A.legal_actions(mk(gold=5, upgrade=6))
    assert Action(A.LEVEL_UP) not in A.legal_actions(mk(gold=10, tier=6, upgrade=5))


def test_level_up_falls_back_to_table_cost():
    st = mk(gold=5, tier=1, upgrade=None)
    assert Action(A.LEVEL_UP) in A.legal_actions(st)  # costo massimo del tier 1 = 5


def test_sell_always_possible_even_with_zero_gold():
    st = mk(gold=0, board=[Minion("X", 1)])
    assert Action(A.SELL, 0, "board") in A.legal_actions(st)
    assert A.legal_actions(st)[-1] == Action(A.END_TURN)


def test_play_requires_board_space():
    hand = [Minion("H", 1)]
    assert Action(A.PLAY, 0) in A.legal_actions(mk(hand=hand))
    full = mk(hand=hand, board=[Minion(f"B{i}") for i in range(7)])
    assert not any(a.kind == A.PLAY for a in A.legal_actions(full))


def test_freeze_needs_a_shop():
    assert Action(A.FREEZE) in A.legal_actions(mk())
    assert Action(A.FREEZE) not in A.legal_actions(mk(shop=[]))


def test_apply_buy_play_sell_gold_flow():
    st = mk(gold=5)
    st = A.apply(st, Action(A.BUY, 0))
    assert (st.gold, [m.name for m in st.hand], [m.name for m in st.shop]) == (2, ["A"], ["B"])
    st = A.apply(st, Action(A.PLAY, 0))
    assert [m.name for m in st.board] == ["A"] and st.hand == []
    st = A.apply(st, Action(A.SELL, 0, "board"))
    assert st.gold == 3 and st.board == []


def test_apply_does_not_mutate_and_rejects_illegal():
    st = mk(gold=5)
    A.apply(st, Action(A.ROLL))
    assert st.gold == 5 and len(st.shop) == 2
    with pytest.raises(ValueError):
        A.apply(mk(gold=1), Action(A.ROLL))


def test_apply_level_up_and_roll():
    st = A.apply(mk(gold=8, tier=2, upgrade=6), Action(A.LEVEL_UP))
    assert (st.gold, st.tavern_tier, st.upgrade_cost) == (2, 3, 8)
    st = A.apply(mk(gold=4), Action(A.ROLL))
    assert st.gold == 2 and st.shop == []


def test_every_legal_action_is_applicable():
    st = mk(gold=7, board=[Minion("X", 1)], hand=[Minion("H", 1)])
    for a in A.legal_actions(st):
        A.apply(st, a)


def test_end_turn_moves_to_combat():
    assert A.apply(mk(), Action(A.END_TURN)).phase == "combat"
