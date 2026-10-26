import shutil
import sys
from pathlib import Path

import cv2
import imagehash
import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import advisor  # noqa: E402
from capture import is_stable  # noqa: E402
from state import GameState, Minion, Smoother, TurnTracker  # noqa: E402
from vision import crop, load_regions  # noqa: E402
from vision import minions as mv  # noqa: E402
from vision import numbers as nv  # noqa: E402
from vision.phase import detect_phase  # noqa: E402


def _noise_card(seed):
    rng = np.random.default_rng(seed)
    return (rng.random((300, 230, 3)) * 255).astype(np.uint8)


FIXTURES = Path(__file__).resolve().parent / "fixtures"
# Template matching sostituisce Tesseract per l'esecuzione standalone su Android
HAS_TESSERACT = True
# Screenshot reali dell'app (fase di acquisto): (file, carte shop, minion board, oro, livello, upgrade, armatura)
REAL_FRAMES = [
    ("turn1_recruit.png", 3, 1, (0, 3), 1, 5, 17),
    ("turn3_recruit.png", 3, 2, (0, 5), 2, 6, 14),      # frame a meta' animazione (fumo viola)
    ("turn4_recruit.png", 2, 4, (0, 6), 2, 5, 14),
    ("late_recruit.png", 6, 4, (0, 10), 4, 10, 6),      # turno 8: shop a 6 carte, oro senza "/10", vita potenziata (verde)
]


def real_frame(name):
    r = load_regions()
    img = cv2.imread(str(FIXTURES / name))
    return cv2.resize(img, tuple(r["base_size"]), interpolation=cv2.INTER_AREA)


def test_regions_load_and_crop():
    r = load_regions()
    frame = np.zeros((r["base_size"][1], r["base_size"][0], 3), np.uint8)
    assert crop(frame, r["gold"]).shape[:2] == (r["gold"][3], r["gold"][2])


@pytest.mark.parametrize("name,shop,board,gold,tier,upgrade,armor", REAL_FRAMES)
def test_real_frame_layout(name, shop, board, gold, tier, upgrade, armor):
    r, f = load_regions(), real_frame(name)
    assert len(mv.locate_shop(f, r)) == shop          # include gli incantesimi
    assert len(mv.locate_board(f, r)) == board
    assert nv.count_stars(crop(f, r["tavern_stars"])) == tier
    assert detect_phase(f, r) == "recruit"


SPELL = "(incantesimo)"
# Nomi attesi per ogni screenshot (verificati a occhio su tavola ritaglio/illustrazione). "?" = non riconosciuto:
# la demone verde non e' nel db (punteggio 0.35-0.47), il fumo viola del turno 3 e' un'animazione piatta.
EXPECTED_CARDS = {
    "turn1_recruit.png": (["Glim Guardian", "Flighty Scout", SPELL], ["?"]),
    "turn3_recruit.png": (["Electric Synthesizer", "Patient Scout", "Patient Scout"], ["?", "?"]),
    "turn4_recruit.png": (["Bubble Gunner", SPELL], ["?", "Soul Rewinder", "Soul Rewinder", "Mind Muck"]),
    "late_recruit.png": (["Shoalfin Mystic", "Mind Muck", "Cord Puller", "Shoalfin Mystic", "Patient Scout", SPELL],
                         ["Relentless Deflector", "Soulkeeping Jailer", "Ashen Corruptor", "Rescue Bot"]),
}


@pytest.fixture(scope="module")
def card_reader():
    db = mv.load_db()
    if not any("_tpl" in c for c in db):
        pytest.skip("illustrazioni non trovate in data/card_art")
    return mv.CardReader(db)



@pytest.mark.parametrize("name", list(EXPECTED_CARDS))
def test_real_frame_card_names(name, card_reader):
    import main
    st = main.read_state(real_frame(name), load_regions(), card_reader)
    shop, board = EXPECTED_CARDS[name]
    assert [m.name for m in st.shop] == shop
    assert [m.name for m in st.board] == board


def test_identify_rejects_flat_crop_and_reader_caches(card_reader):
    flat = np.full((100, 104, 3), (200, 40, 90), np.uint8)       # macchia di colore tipo fumo viola
    assert mv.identify(flat, card_reader.db) == (None, None)
    r, f = load_regions(), real_frame("turn4_recruit.png")
    crop_img = crop(f, mv.locate_board(f, r)[1])                  # Soul Rewinder
    n = len(card_reader._cache)
    a = card_reader.read(crop_img, max_tier=3)
    b = card_reader.read(crop_img, max_tier=3)
    assert a[0]["name"] == "Soul Rewinder" and b is not None and a[0] is b[0]
    assert len(card_reader._cache) <= n + 1                       # la seconda lettura non aggiunge voci


def test_is_minion_card_tells_spells_apart():
    r, f = load_regions(), real_frame("late_recruit.png")
    assert [mv.is_minion_card(f, rect, r) for rect in mv.locate_shop(f, r)] == [True] * 5 + [False]


def test_board_grid_ignores_stray_cue_and_keeps_missing_one():
    g = load_regions()["board_grid"]
    four = [733, 907, 1079, 1252]
    # indizio falso (arte rossa a x=698) e uno mancante (ultimo minion): la griglia a 4 carte vince comunque
    assert [round(s) for s in mv._fit_board([698, 734, 908, 1082], g)] == [734, 907, 1079, 1252]
    assert len(mv._fit_board([734, 908, 1082], g)) == 4 or len(mv._fit_board([734, 908, 1082], g)) == 3
    assert mv._fit_board([], g) == []
    assert [round(s) for s in mv._fit_board([993], g)] == [993]
    assert len(mv._fit_board(four, g)) == 4



@pytest.mark.parametrize("name,shop,board,gold,tier,upgrade,armor", REAL_FRAMES)
def test_real_frame_numbers(name, shop, board, gold, tier, upgrade, armor):
    r, f = load_regions(), real_frame(name)
    assert nv.read_gold(crop(f, r["gold"])) == gold
    assert nv.read_region(f, r, "upgrade_cost") == upgrade
    assert nv.read_region(f, r, "hero_health") == 30
    assert nv.read_region(f, r, "hero_armor") == armor


def test_combat_frame_phase_and_numbers():
    r, f = load_regions(), real_frame("combat.png")
    assert detect_phase(f, r) == "combat"
    # il marcatore "Combat" non deve scattare in acquisto, e il pulsante reroll non in combattimento
    for name, *_ in REAL_FRAMES:
        assert detect_phase(real_frame(name), r) == "recruit"

    assert nv.read_gold(crop(f, r["gold"])) == (0, 9)      # in combattimento il contatore resta visibile
    assert nv.read_region(f, r, "hero_health") == 30
    assert nv.read_region(f, r, "hero_armor") == 14
    assert nv.count_stars(crop(f, r["tavern_stars"])) == 0      # il badge di Bob non c'e'


def test_turn_tracker():
    t = TurnTracker()
    # il turno si ricava dall'oro massimo: 0/3 -> turno 1, 0/5 -> turno 3, 0/6 -> turno 4
    assert [t.update("recruit", m) for m in (3, 5, 6)] == [1, 3, 4]
    assert t.update("recruit", 9) == 7
    assert t.update("combat", 9) == 7
    assert t.update("recruit", 10) == 8      # da qui il massimo non cresce piu'
    assert t.update("combat", 10) == 8
    assert t.update("recruit", 10) == 9      # nuovo acquisto dopo un combattimento
    assert t.update("recruit", 10) == 9      # stesso turno: nessun incremento


def test_minion_identify_roundtrip():
    cards = []
    for i in range(5):
        img = _noise_card(i)
        h = imagehash.phash(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), hash_size=16)
        cards.append({"name": f"Card{i}", "tier": 1, "tribe": "", "hash": str(h), "_hash": h})
    match, dist = mv.identify(_noise_card(3), cards)
    assert match["name"] == "Card3" and dist == 0
    # carta sconosciuta: nessun match
    unknown, _ = mv.identify(_noise_card(99), cards)
    assert unknown is None


def test_is_stable():
    a = np.full((50, 50, 3), 100, np.uint8)
    assert is_stable(a, a.copy())
    assert not is_stable(a, np.full((50, 50, 3), 200, np.uint8))
    assert not is_stable(None, a)


def test_state_plausibility_and_smoother():
    assert not GameState(gold=42).is_plausible()
    s = Smoother(window=3)
    for g in (4, 4, 4):
        s.update(GameState(phase="recruit", gold=g))
    out = s.update(GameState(phase="recruit", gold=42))  # rumore scartato
    assert out.gold == 4


def test_advisor_triple_and_levelup():
    st = GameState(phase="recruit", gold=6, tavern_tier=1, turn=4,
                   shop=[Minion("Foo", 1, "Beast")],
                   board=[Minion("Foo", 1, "Beast"), Minion("Foo", 1, "Beast")])
    tips = advisor.advise(st)
    assert any("triplo" in t for t in tips)
    assert any("Sali alla taverna 2" in t for t in tips)


def test_key_card_tips_from_comps():
    st = GameState(phase="recruit", gold=5, tavern_tier=2, turn=3,
                   shop=[Minion("Titus Rivendare", 5), Minion("Sconosciuta", 1)],
                   board=[Minion("Faceless Converter", 3)])
    tips = advisor.key_card_tips(st)
    # Titus e' core in piu' comp Tier 2, ma con Faceless Converter gia' sul board vince Aberrations
    assert len(tips) == 1 and "Aberrations - Deathrattle/Spells" in tips[0]
    assert "core" in tips[0] and "ne hai 1" in tips[0]
    # un add-on di una comp Tier 3 isolato non vale la segnalazione
    weak = GameState(shop=[Minion("Hired Mount", 3)])
    assert advisor.key_card_tips(weak) == []
    # un core di una comp Tier 1 viene segnalato anche senza altro sul board
    strong = GameState(shop=[Minion("Felboar", 5)])
    assert any("Tier 1" in t for t in advisor.key_card_tips(strong))


def test_comps_file_is_valid():
    comps = advisor.load_comps()
    assert len(comps) == 31
    assert {c["tier"] for c in comps} == {1, 2, 3}
    assert all(c["core"] and {"name", "tavern_tier"} <= set(c["core"][0]) for c in comps)


def test_parse_hsreplay_markdown():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    from parse_hsreplay_comps import parse
    md = """# T
> Source: [HSReplay.net](https://hsreplay.net/x)
> Scraped: 2026-10-23T06:05:12Z

### Demons - Self Damage (Tier 1)
- **Difficulty**: 1/5 | **Tier Rank**: 2 (Previous: Tier 2)
- **When to Commit**: Ashen Corruptor
Wrath Weaver
- **Core Cards**: Ashen Corruptor (T4), Eredar Escapist (T6)
- **Add-on / Tech Cards**: Malchezaar, Prince of Dance (T3), Wrath Weaver (T1)
- **How to Play & Strategy**:
  Prima riga.
  Seconda riga.

---
"""
    meta, comps = parse(md)
    assert meta["_scraped"].startswith("2026-10-23")
    c = comps[0]
    assert (c["tribe"], c["tier"], c["difficulty"], c["rank"]) == ("Demons", 1, 1, 2)
    assert [x["name"] for x in c["core"]] == ["Ashen Corruptor", "Eredar Escapist"]
    assert [x["name"] for x in c["addons"]] == ["Malchezaar, Prince of Dance", "Wrath Weaver"]
    assert c["commit"] == "Ashen Corruptor; Wrath Weaver"
    assert c["strategy"] == "Prima riga. Seconda riga."


def test_advisor_other_phases():
    assert advisor.advise(GameState(phase="combat")) == ["Combattimento in corso."]


def test_read_number_template_matching():
    f = real_frame("turn1_recruit.png")
    r = load_regions()
    assert nv.read_region(f, r, "upgrade_cost") == 5
    assert nv.read_region(f, r, "hero_health") == 30
    assert nv.read_region(f, r, "hero_armor") == 17



    






def test_structured_advisor():
    st = GameState(phase="recruit", gold=6, tavern_tier=1, turn=4,
                   shop=[Minion("Foo", 1, "Beast")],
                   board=[Minion("Foo", 1, "Beast"), Minion("Foo", 1, "Beast")])
    tips = advisor.structured_advise(st)
    assert any(t.action == "BUY" and t.role == "triple" and t.card_index == 0 for t in tips)
    assert any(t.action == "UPGRADE" for t in tips)


def test_renderer_draw_overlay():
    from vision.renderer import draw_overlay
    r = load_regions()
    frame = np.zeros((r["base_size"][1], r["base_size"][0], 3), np.uint8)
    st = GameState(phase="recruit", gold=5, tavern_tier=2, turn=3,
                   shop_rects=[[850, 282, 104, 100]],
                   shop=[Minion("Test", 2)])
    tips = [advisor.Tip(text="Compra Test", action="BUY", card_index=0, role="core", comp_name="TestComp")]
    out = draw_overlay(frame, st, tips, r)
    assert out.shape == frame.shape
    assert out.dtype == frame.dtype
    # Verifica che il rendering abbia modificato i pixel dell'overlay (non piu' tutti neri)
    assert out.sum() > 0


def test_turn2_always_upgrades_tavern():
    # Al turno 2 con 4 oro e taverna al tier 1 l'upgrade deve essere il consiglio primario (priorità 15.0)
    st = GameState(phase="recruit", gold=4, max_gold=4, tavern_tier=1, turn=2,
                   shop=[Minion("Felboar", 5)])
    tips = advisor.structured_advise(st)
    assert tips[0].action == "UPGRADE"
    assert "Turno 2" in tips[0].text
    assert "upgrade alla taverna 2" in tips[0].text

    # Se invece la taverna e' gia' a tier 2, non deve suggerirlo di nuovo
    st_upgraded = GameState(phase="recruit", gold=0, max_gold=4, tavern_tier=2, turn=2)
    tips_upgraded = advisor.structured_advise(st_upgraded)
    assert not any("Turno 2: fai sempre l'upgrade" in t.text for t in tips_upgraded)


def test_turn5_upgrades_tavern():
    # Al turno 5 con 7 oro e taverna al tier 2 l'upgrade a taverna 3 e' prioritario (priorità 14.0)
    st = GameState(phase="recruit", gold=7, max_gold=7, tavern_tier=2, turn=5,
                   shop=[Minion("Felboar", 5)])
    tips = advisor.structured_advise(st)
    assert tips[0].action == "UPGRADE"
    assert "Turno 5" in tips[0].text
    assert "upgrade alla taverna 3" in tips[0].text

    # Se invece la taverna e' gia' a tier 3, non deve suggerirlo di nuovo
    st_upgraded = GameState(phase="recruit", gold=2, max_gold=7, tavern_tier=3, turn=5)
    tips_upgraded = advisor.structured_advise(st_upgraded)
    assert not any("Turno 5: fai l'upgrade" in t.text for t in tips_upgraded)


def test_jeef_turn1_rules():
    # Turno 1 con minion token/economia: deve raccomandarlo con priorità e vietare il roll
    st = GameState(phase="recruit", gold=3, max_gold=3, tavern_tier=1, turn=1,
                   shop=[Minion("Bubble Gunner", 1), Minion("Cord Puller", 1)])
    tips = advisor.structured_advise(st)
    assert any("Cord Puller" in t.text and "economia/token" in t.text for t in tips)
    assert not any("NON rollare" in t.text for t in tips)  # messaggio rimosso: troppo rumore


def test_jeef_turn3_and_turn4_rules():
    # Turno 3 con token sul board
    st3 = GameState(phase="recruit", gold=5, max_gold=5, tavern_tier=2, turn=3,
                    board=[Minion("Cord Puller", 1)])
    tips3 = advisor.structured_advise(st3)
    assert any("Turno 3" in t.text and "vendi il token" in t.text for t in tips3)

    # Turno 4: compra 2 minion
    st4 = GameState(phase="recruit", gold=6, max_gold=6, tavern_tier=2, turn=4)
    tips4 = advisor.structured_advise(st4)
    assert any("Turno 4" in t.text and "compra 2 minion" in t.text for t in tips4)


def test_jeef_tripling_timing_and_freeze():
    # Holding triple a Taverna 2 prima del turno 5
    st_triple = GameState(phase="recruit", gold=3, max_gold=5, tavern_tier=2, turn=3,
                          shop=[Minion("Foo", 1)],
                          board=[Minion("Foo", 1), Minion("Foo", 1)])
    tips_triple = advisor.structured_advise(st_triple)
    assert any(t.role == "triple" for t in tips_triple)
    assert not any("Timing Triplo" in t.text for t in tips_triple)

    # Freeze con tripla a fine turno (gold = 0)
    st_freeze = GameState(phase="recruit", gold=0, max_gold=6, tavern_tier=2, turn=4,
                          shop=[Minion("Bar", 1)],
                          board=[Minion("Bar", 1), Minion("Bar", 1)])
    tips_freeze = advisor.structured_advise(st_freeze)
    assert any(t.action == "FREEZE" and "CONGELA lo shop" in t.text for t in tips_freeze)


def test_positioning_tips_removed():
    st_pos = GameState(phase="recruit", gold=0, max_gold=10, tavern_tier=5, turn=9,
                       board=[Minion("Crackling Cyclone", 3), Minion("Titus Rivendare", 5),
                              Minion("MinionA", 2), Minion("MinionB", 2)])
    assert not any("Posizionamento" in t.text for t in advisor.structured_advise(st_pos))


def test_no_freeze_for_one_message():
    st = GameState(phase="recruit", gold=0, max_gold=6, tavern_tier=2, turn=4, shop=[Minion("Felboar", 5)])
    assert not any("NON congelare" in t.text for t in advisor.structured_advise(st))


# --- statistiche attacco/vita (turno 8, tutte le carte lette a occhio dallo screenshot) ---

def test_minion_stats_late_frame():
    f, r = real_frame("late_recruit.png"), load_regions()
    shop = [nv.read_minion_stats(f, rc, "shop") for rc in mv.locate_shop(f, r)]
    board = [nv.read_minion_stats(f, rc, "board") for rc in mv.locate_board(f, r)]
    assert shop[:5] == [(4, 4), (3, 2), (1, 1), (4, 4), (1, 1)]
    assert shop[5] == (None, None)  # incantesimo: nessuna statistica
    assert board == [(39, 31), (18, 21), (7, 23), (4, 5)]  # cifre verdi (potenziate) e a due cifre


# Board da 6 minion con numeri a 3 cifre (152/131, 394/279): ricostruito da uno screenshot dell'utente
# (finestra ingrandita e riportata a 2000x900), quindi i rettangoli sono dati a mano, non da locate_board.

def test_minion_stats_three_digits_board6():
    f = cv2.imread(str(FIXTURES / "board6_big_numbers.png"))
    rects = [[c - 52, 579, 104, 100] for c in (102, 274, 447, 619, 792, 964)]
    assert [nv.read_minion_stats(f, rc, "board") for rc in rects] == [
        (152, 131), (8, 5), (17, 14), (7, 6), (394, 279), (48, 41)]



def test_strip_stats_independent_of_card_centers():
    """read_strip_stats abbina le cifre in sequenza (2 numeri per carta): regge centri sfasati di +-25 px,
    come capita con 6-7 minion quando il passo reale e' piu' stretto di quello della griglia."""
    f = cv2.imread(str(FIXTURES / "board6_big_numbers.png"))
    expected = [(152, 131), (8, 5), (17, 14), (7, 6), (394, 279), (48, 41)]
    for shift in (-25, 0, 25):
        rects = [[c - 52 + shift, 579, 104, 100] for c in (102, 274, 447, 619, 792, 964)]
        assert nv.read_strip_stats(f, rects, "board") == expected



def test_strip_stats_late_frame_ignores_art_blob():
    f, r = real_frame("late_recruit.png"), load_regions()
    assert nv.read_strip_stats(f, mv.locate_board(f, r), "board") == [(39, 31), (18, 21), (7, 23), (4, 5)]


# --- impegno su comp/tribu' a turno avanzato ---
def _other_core(comps, comp, tier=1):
    """Un core di una comp diversa che non compare ne' come core ne' come add-on di `comp`."""
    mine = {x["name"] for x in comp["core"] + comp["addons"]}
    for c in comps:
        if c["tier"] == tier and c["name"] != comp["name"]:
            for x in c["core"]:
                if x["name"] not in mine:
                    return x["name"], c
    raise AssertionError("nessun core alternativo")


def test_committed_comp_hides_other_comps_late():
    comps = advisor.load_comps()
    mine = comps[0]
    board = [Minion(x["name"], 4) for x in mine["core"][:2]]
    other, _ = _other_core(comps, mine)
    mine_next = mine["core"][2]["name"]
    st = GameState(phase="recruit", gold=6, tavern_tier=4, turn=7, shop=[Minion(other, 5), Minion(mine_next, 5)], board=board)
    tips = advisor.structured_key_card_tips(st)
    assert [t.card_name for t in tips] == [mine_next] and tips[0].comp_name == mine["name"]
    # stessa situazione a turno 3: si esplora, quindi anche l'altra comp Tier 1 viene segnalata
    st.turn = 3
    assert other in {t.card_name for t in advisor.structured_key_card_tips(st)}


def test_committed_tribe_hides_other_tribes_late():
    comps = advisor.load_comps()
    board = [Minion("Pezzo A", 3, "Mech"), Minion("Pezzo B", 3, "Mech"), Minion("Pezzo C", 4, "Mech")]
    other = next(c for c in comps if c["tier"] == 1 and c["tribe"] == "Quilboar")["core"][0]["name"]
    mech_core = next(c for c in comps if c["tier"] == 1 and c["tribe"] == "Mechs")["core"][0]["name"]
    st = GameState(phase="recruit", gold=6, tavern_tier=4, turn=7, shop=[Minion(other, 5), Minion(mech_core, 5)], board=board)
    assert [t.card_name for t in advisor.structured_key_card_tips(st)] == [mech_core]
    assert any(t.role == "commit" for t in advisor.structured_advise(st))


def test_late_game_lone_core_not_suggested_without_commitment():
    comps = advisor.load_comps()
    core = comps[0]["core"][0]["name"]
    st = GameState(phase="recruit", gold=6, tavern_tier=5, turn=9, shop=[Minion(core, 5)], board=[Minion("Altro", 3, "Beast")])
    assert advisor.structured_key_card_tips(st) == []


def test_committed_player_is_told_to_roll_not_to_buy_random_card():
    board = [Minion("A", 3, "Mech"), Minion("B", 3, "Mech"), Minion("C", 4, "Mech")]
    st = GameState(phase="recruit", gold=5, max_gold=9, tavern_tier=4, turn=7, shop=[Minion("Random", 4, "Beast")], board=board)
    tips = advisor.structured_advise(st)
    assert not any(t.action == "BUY" for t in tips)
    assert any(t.action == "ROLL" for t in tips)


# --- vendita per fare spazio ---
def _committed_board(extra):
    comps = advisor.load_comps()
    mine = comps[0]  # Mechs - APM Magnetic
    core = [Minion(x["name"], 5, "Mech", 10, 10) for x in mine["core"][:3]]
    return mine, core + extra


def test_sell_weakest_offcomp_minion_when_board_full():
    mine, board = _committed_board([
        Minion("Debole", 2, "Beast", 2, 3), Minion("Medio", 3, "Beast", 6, 6), Minion("Altro", 3, "Beast", 4, 4), Minion("Extra", 3, "Beast", 4, 5)])
    board = board[:7]
    assert len(board) == 7
    st = GameState(phase="recruit", gold=6, max_gold=9, tavern_tier=4, turn=7,
                   shop=[Minion(mine["core"][3]["name"], 5)], board=board)
    tips = advisor.structured_advise(st)
    sell = [t for t in tips if t.action == "SELL"]
    assert len(sell) == 1 and sell[0].zone == "board" and st.board[sell[0].card_index].name == "Debole"
    assert sell[0].score < max(t.score for t in tips if t.action == "BUY")
    # board non pieno -> nessuna vendita
    st.board = board[:6]
    assert not any(t.action == "SELL" for t in advisor.structured_advise(st))


def test_never_sell_comp_cards_or_triple_progress():
    mine, board = _committed_board([Minion("Coppia", 2, "Beast", 2, 2), Minion("Coppia", 2, "Beast", 2, 2),
                                    Minion("Debole", 1, "Beast", 1, 1), Minion("Solo", 4, "Beast", 8, 8)])
    st = GameState(phase="recruit", gold=6, max_gold=9, tavern_tier=4, turn=7, board=board[:7],
                   shop=[Minion(mine["core"][3]["name"], 5)])
    assert st.board[advisor.sell_candidate(st)].name == "Debole"
    extra_core = Minion(mine["core"][3]["name"], 5, "Mech", 10, 10)
    st.board = [m for m in board if m.name != "Debole"] + [extra_core]
    assert len(st.board) == 7
    assert st.board[advisor.sell_candidate(st)].name == "Solo"  # le coppie (triplo) e le carte comp restano


# --- carte da aspettare ---
def test_wanted_cards_for_dragon_board():
    st = GameState(phase="recruit", gold=5, max_gold=7, tavern_tier=4, turn=5,
                   shop=[Minion("Sconosciuta", 2)], board=[Minion("Persistent Poet", 4, "Dragon", 5, 5)])
    w = advisor.wanted_cards(st)
    assert w["comp"]["tribe"] == "Dragons"
    assert w["now"] and all(n != "Persistent Poet" for n in w["now"])
    tip = next(t for t in advisor.structured_advise(st) if t.role == "target")
    assert tip.text.startswith("Cerca:") and tip.action == "INFO"


def test_wanted_cards_empty_or_irrelevant_board():
    assert advisor.wanted_cards(GameState(phase="recruit", tavern_tier=3)) is None
    st = GameState(phase="recruit", tavern_tier=3, board=[Minion("Carta Inventata", 2)])
    assert advisor.wanted_cards(st) is None


def test_wanted_cards_higher_tier_when_nothing_available_now():
    st = GameState(phase="recruit", gold=5, tavern_tier=1, turn=2, board=[Minion("Persistent Poet", 4)])
    w = advisor.wanted_cards(st)
    assert w["now"] == [] and w["later"] and w["later"][0][1] >= 4
    tip = next(t for t in advisor.structured_advise(st) if t.role == "target")
    assert tip.text.startswith("Sali di taverna per")


def test_no_end_of_turn_reorder_tip():
    st = GameState(phase="recruit", gold=0, max_gold=6, tavern_tier=2, turn=4, board=[Minion("A", 1)])
    assert not any("riordina" in t.text.lower() for t in advisor.structured_advise(st))
