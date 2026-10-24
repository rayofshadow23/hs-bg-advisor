"""Loop principale: cattura -> visione -> stato -> consigli (solo output a terminale)."""
import argparse
import time

import advisor
import capture
from state import GameState, Minion, Smoother, TurnTracker
from vision import crop, load_regions
from vision import minions as mv
from vision import numbers as nv
from vision.phase import detect_phase


def read_cards(frame, rects, reader, max_tier=None, regions=None):
    """Riconosce le carte; se regions e' dato, salta quelle dello shop che non sono minion (incantesimi)."""
    out = []
    for rect in rects:
        if regions is not None and not mv.is_minion_card(frame, rect, regions):
            out.append(Minion("(incantesimo)"))
            continue
        card, _ = reader.read(crop(frame, rect), max_tier=max_tier)
        out.append(Minion(card["name"], card["tier"], card.get("tribe", "")) if card else Minion())
    return out


def read_state(frame, regions, reader):
    st = GameState(phase=detect_phase(frame, regions))
    gold = nv.read_gold(crop(frame, regions["gold"]))
    if gold:
        st.gold, st.max_gold = gold
    st.hero_health = nv.read_region(frame, regions, "hero_health")
    st.hero_armor = nv.read_region(frame, regions, "hero_armor")
    if st.phase == "recruit":
        # Bob e i suoi pulsanti esistono solo in acquisto: in combattimento quelle zone mostrano altro
        st.tavern_tier = nv.count_stars(crop(frame, regions["tavern_stars"])) or None
        st.upgrade_cost = nv.read_region(frame, regions, "upgrade_cost")
        tier = st.tavern_tier  # nel negozio ci sono carte fino al tier della taverna; sul board puo' esserci 1 in piu'
        st.shop = read_cards(frame, mv.locate_shop(frame, regions), reader, tier, regions)
        st.board = read_cards(frame, mv.locate_board(frame, regions), reader, tier + 1 if tier else None)
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", help="seriale adb se hai piu' dispositivi")
    ap.add_argument("--interval", type=float, default=0.7)
    args = ap.parse_args()

    regions = load_regions()
    db = mv.load_db()
    if not db:
        print("cards.json mancante: i minion saranno '?' (esegui tools/build_card_db.py)")
    elif not any("_tpl" in c for c in db):
        print("illustrazioni non trovate in data/card_art (o in $HS_BG_CARD_ART): riconoscimento solo per hash, molto meno preciso")
    reader = mv.CardReader(db)
    smoother, tracker = Smoother(), TurnTracker()
    prev, last_print = None, None
    while True:
        frame = capture.grab_frame(tuple(regions["base_size"]), args.serial)
        if capture.is_stable(prev, frame):
            st = smoother.update(read_state(frame, regions, reader))
            st.turn = tracker.update(st.phase, st.max_gold)
            tips = advisor.advise(st)
            key = (st.phase, st.gold, st.max_gold, st.tavern_tier, tuple(m.name for m in st.shop), tuple(tips))
            if key != last_print:
                print(f"\n[turno {st.turn}] fase={st.phase} oro={st.gold}/{st.max_gold} taverna={st.tavern_tier} "
                      f"(upgrade {st.upgrade_cost}) vita={st.hero_health}+{st.hero_armor}")
                print("  shop :", ", ".join(m.name for m in st.shop) or "-")
                print("  board:", ", ".join(m.name for m in st.board) or "-")
                for t in tips:
                    print("  >", t)
                last_print = key
        prev = frame
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
