import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import advisor  # noqa: E402
from overlay_server import StateServer, to_payload  # noqa: E402
from state import GameState, Minion  # noqa: E402


def sample_state():
    return GameState(
        phase="recruit", gold=5, max_gold=5, tavern_tier=2, upgrade_cost=6, turn=3, hero_health=30,
        shop=[Minion("Cord Puller", 1, "Mech", 1, 1), Minion("(incantesimo)", is_spell=True)],
        board=[Minion("Annoy-o-Tron", 1, "Mech", 1, 2)],
        shop_rects=[[525, 282, 104, 100], [697, 282, 104, 100]], board_rects=[[682, 478, 104, 100]])


def test_payload_has_rects_stats_and_tips():
    st = sample_state()
    p = to_payload(st, advisor.structured_advise(st), seq=7)
    assert p["seq"] == 7 and p["base_size"] == [2000, 900] and p["phase"] == "recruit"
    assert p["shop"][0] == {"name": "Cord Puller", "tier": 1, "tribe": "Mech", "attack": 1, "health": 1,
                            "spell": False, "rect": [525, 282, 104, 100]}
    assert p["shop"][1]["spell"] is True and p["board"][0]["rect"] == [682, 478, 104, 100]
    assert p["tips"] and {"text", "action", "card_index", "role", "score"} <= set(p["tips"][0])
    json.dumps(p)  # serializzabile


def test_server_serves_latest_state():
    srv = StateServer("127.0.0.1", 0).start()  # porta 0: libera a caso
    try:
        url = f"http://127.0.0.1:{srv.port}/state"
        first = json.load(urllib.request.urlopen(url, timeout=3))
        assert first["phase"] == "unknown" and first["seq"] == 0
        st = sample_state()
        srv.publish(st, advisor.structured_advise(st))
        second = json.load(urllib.request.urlopen(url, timeout=3))
        assert second["seq"] == 1 and second["shop"][0]["name"] == "Cord Puller"
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{srv.port}/altro", timeout=3)
            assert False, "doveva dare 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.stop()
