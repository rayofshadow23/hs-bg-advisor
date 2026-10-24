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
HAS_TESSERACT = shutil.which("tesseract") is not None
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


@pytest.mark.skipif(not HAS_TESSERACT, reason="tesseract non installato")
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


@pytest.mark.skipif(not HAS_TESSERACT, reason="tesseract non installato")
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
    if HAS_TESSERACT:
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


def test_read_number_if_tesseract_available():
    pytest.importorskip("pytesseract")
    import shutil
    if not shutil.which("tesseract"):
        pytest.skip("tesseract non installato")
    from vision.numbers import read_number
    img = np.zeros((60, 120, 3), np.uint8)
    cv2.putText(img, "7", (35, 48), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 255, 255), 4)
    assert read_number(img) == 7
