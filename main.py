"""Loop principale: cattura -> visione -> stato -> consigli (output terminale o finestra grafica)."""
import argparse
import time

import cv2

import advisor
import capture
from state import GameState, Minion, Smoother, TurnTracker
from vision import crop, load_regions
from vision import minions as mv
from vision import numbers as nv
from vision.phase import detect_phase
from vision.renderer import draw_overlay


def read_cards(frame, rects, reader, max_tier=None, regions=None, kind="board"):
    """Riconosce le carte (nome, tier, tribu', attacco/vita); se regions e' dato, salta quelle dello shop
    che non sono minion (incantesimi). kind: 'shop' | 'board' (posizione delle cifre sotto la carta)."""
    out = []
    # sul board le carte sono tutte minion: le cifre si leggono sull'intera riga (vedi read_strip_stats)
    strip = nv.read_strip_stats(frame, rects, kind) if kind == "board" else None
    for i, rect in enumerate(rects):
        if regions is not None and not mv.is_minion_card(frame, rect, regions):
            out.append(Minion("(incantesimo)", is_spell=True))
            continue
        card, _ = reader.read(crop(frame, rect), max_tier=max_tier)
        att, hp = strip[i] if strip else nv.read_minion_stats(frame, rect, kind)
        out.append(Minion(card["name"], card["tier"], card.get("tribe", ""), att, hp) if card
                   else Minion(attack=att, health=hp))
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
        st.shop_rects = mv.locate_shop(frame, regions)
        st.shop = read_cards(frame, st.shop_rects, reader, tier, regions, "shop")
        st.board_rects = mv.locate_board(frame, regions)
        st.board = read_cards(frame, st.board_rects, reader, tier + 1 if tier else None, kind="board")
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", help="seriale adb se hai piu' dispositivi")
    ap.add_argument("--interval", type=float, default=0.7)
    ap.add_argument("--gui", action="store_true", help="mostra finestra video con overlay grafico in tempo reale")
    ap.add_argument("--serve", type=int, nargs="?", const=8765, metavar="PORT",
                    help="pubblica lo stato in JSON su http://host:PORT/state per l'app overlay Android (default 8765)")
    ap.add_argument("--serve-host", default="127.0.0.1", help="0.0.0.0 per collegare il telefono via Wi-Fi")
    ap.add_argument("--image", help="invece di adb, usa un'immagine statica (utile per test e demo)")
    args = ap.parse_args()

    regions = load_regions()
    db = mv.load_db()
    if not db:
        print("cards.json mancante: i minion saranno '?' (esegui tools/build_card_db.py)")
    elif not any("_tpl" in c for c in db):
        print("illustrazioni non trovate in data/card_art (o in $HS_BG_CARD_ART): riconoscimento solo per hash, molto meno preciso")
    reader = mv.CardReader(db)
    smoother, tracker = Smoother(), TurnTracker()
    server = None
    if args.serve:
        from overlay_server import StateServer
        server = StateServer(args.serve_host, args.serve).start()
        print(f"Server overlay su http://{args.serve_host}:{server.port}/state "
              f"(cavo: adb reverse tcp:{server.port} tcp:{server.port})")
    prev, last_print = None, None
    st = GameState()
    structured_tips = []

    if args.image:
        raw = cv2.imread(args.image)
        if raw is None:
            raise SystemExit(f"Impossibile leggere il file immagine: {args.image}")
        frame = cv2.resize(raw, tuple(regions["base_size"]), interpolation=cv2.INTER_AREA)
        st = read_state(frame, regions, reader)
        st.turn = tracker.update(st.phase, st.max_gold)
        structured_tips = advisor.structured_advise(st)
        print(f"\n[turno {st.turn}] fase={st.phase} oro={st.gold}/{st.max_gold} taverna={st.tavern_tier} "
              f"(upgrade {st.upgrade_cost}) vita={st.hero_health}+{st.hero_armor}")
        print("  shop :", ", ".join(m.name for m in st.shop) or "-")
        print("  board:", ", ".join(m.name for m in st.board) or "-")
        for t in structured_tips:
            print("  >", t.text)
        if server:
            server.publish(st, structured_tips)
            input("Server attivo: premi Invio per chiudere...")
        if args.gui:
            rendered = draw_overlay(frame, st, structured_tips, regions)
            cv2.namedWindow("Hearthstone BG Advisor", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Hearthstone BG Advisor", 1400, 630)
            cv2.imshow("Hearthstone BG Advisor", rendered)
            print("Finestra grafica aperta: premi qualsiasi tasto sulla finestra (o 'q') per chiudere.")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        return

    if args.gui:
        cv2.namedWindow("Hearthstone BG Advisor", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Hearthstone BG Advisor", 1400, 630)

    try:
        while True:
            frame = capture.grab_frame(tuple(regions["base_size"]), args.serial)
            if capture.is_stable(prev, frame):
                st = smoother.update(read_state(frame, regions, reader))
                st.turn = tracker.update(st.phase, st.max_gold)
                structured_tips = advisor.structured_advise(st)
                if server:
                    server.publish(st, structured_tips)
                tips = [t.text for t in structured_tips]
                key = (st.phase, st.gold, st.max_gold, st.tavern_tier, tuple(m.name for m in st.shop), tuple(tips))
                if key != last_print:
                    print(f"\n[turno {st.turn}] fase={st.phase} oro={st.gold}/{st.max_gold} taverna={st.tavern_tier} "
                          f"(upgrade {st.upgrade_cost}) vita={st.hero_health}+{st.hero_armor}")
                    print("  shop :", ", ".join(m.name for m in st.shop) or "-")
                    print("  board:", ", ".join(m.name for m in st.board) or "-")
                    for t in tips:
                        print("  >", t)
                    last_print = key

            if args.gui:
                rendered = draw_overlay(frame, st, structured_tips, regions)
                cv2.imshow("Hearthstone BG Advisor", rendered)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            prev = frame
            time.sleep(args.interval)
    finally:
        if args.gui:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
