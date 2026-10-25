"""Pubblica lo stato letto dallo schermo come JSON su HTTP, per l'app overlay Android (strada A).

Il PC fa cattura + visione + advisor; il telefono interroga GET /state e disegna i consigli sopra il gioco.
Collegamento via cavo:  adb reverse tcp:8765 tcp:8765  (l'app usa 127.0.0.1:8765)
Collegamento Wi-Fi:      avvia con --serve-host 0.0.0.0 e metti l'IP del PC nell'app.
Le coordinate sono nello spazio normalizzato 2000x900 (regions.yaml); l'app le scala allo schermo.
"""
import json
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_SIZE = (2000, 900)


def _cards(cards, rects):
    out = []
    for i, m in enumerate(cards):
        rect = list(rects[i]) if i < len(rects) else None
        out.append({"name": m.name, "tier": m.tier, "tribe": m.tribe, "attack": m.attack,
                    "health": m.health, "spell": m.is_spell, "rect": rect})
    return out


def to_payload(state, tips, seq=0, base_size=BASE_SIZE):
    """Dizionario JSON-serializzabile con stato, carte (con rettangoli) e consigli ordinati."""
    return {
        "seq": seq, "base_size": list(base_size), "phase": state.phase, "turn": state.turn,
        "gold": state.gold, "max_gold": state.max_gold, "tavern_tier": state.tavern_tier,
        "upgrade_cost": state.upgrade_cost, "hero_health": state.hero_health, "hero_armor": state.hero_armor,
        "shop": _cards(state.shop, state.shop_rects), "board": _cards(state.board, state.board_rects),
        "tips": [{"text": t.text, "action": t.action, "card_index": t.card_index, "card_name": t.card_name,
                  "role": t.role, "score": t.score, "comp": t.comp_name} for t in tips],
    }


class StateServer:
    """Server HTTP in un thread: publish() aggiorna lo stato, GET /state lo restituisce."""

    def __init__(self, host="127.0.0.1", port=8765):
        self._lock = threading.Lock()
        self._seq = 0
        self._body = json.dumps({"seq": 0, "phase": "unknown", "tips": [], "shop": [], "board": [],
                                 "base_size": list(BASE_SIZE)}).encode()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.split("?")[0] not in ("/state", "/"):
                    self.send_error(404)
                    return
                with outer._lock:
                    body = outer._body
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # niente righe di log a ogni richiesta (ogni 0,4 s)
                pass

        self.httpd = ThreadingHTTPServer((host, port), Handler)
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def publish(self, state, tips):
        with self._lock:
            self._seq += 1
            self._body = json.dumps(to_payload(state, tips, self._seq), ensure_ascii=False).encode()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
