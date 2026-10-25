"""Motore di analisi e advisory autonomo per esecuzione standalone (PC o Android/Chaquopy).

Fornisce un'interfaccia ad alte prestazioni che riceve frame raw (BGR o RGBA da ImageReader Android),
esegue la pipeline di visione, aggiorna lo stato temporale (Smoother + TurnTracker), calcola i consigli
strategici di Jeefhs e restituisce il payload JSON pronto per il rendering dell'overlay.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

import advisor
import capture
from overlay_server import BASE_SIZE, to_payload
from state import GameState, Minion, Smoother, TurnTracker
from vision import crop, load_regions
from vision import minions as mv
from vision import numbers as nv
from vision.phase import detect_phase

logger = logging.getLogger("StandaloneEngine")


class StandaloneEngine:
    """Motore stateful per l'analisi dei frame in tempo reale."""

    def __init__(
        self,
        card_art_dir: Optional[str] = None,
        cards_json_path: Optional[str] = None,
        regions_yaml_path: Optional[str] = None,
    ):
        # Carica configurazione regioni
        if regions_yaml_path:
            self.regions = load_regions(Path(regions_yaml_path))
        else:
            self.regions = load_regions()

        self.base_size: Tuple[int, int] = tuple(self.regions.get("base_size", BASE_SIZE))

        # Carica database carte
        if cards_json_path:
            db_path = Path(cards_json_path)
            self.db = mv.load_db(db_path)
        else:
            self.db = mv.load_db()

        self.reader = mv.CardReader(self.db)
        self.smoother = Smoother()
        self.tracker = TurnTracker()

        self.seq = 0
        self.prev_frame: Optional[np.ndarray] = None
        self.last_state = GameState()
        self.last_tips = []
        self.last_payload_json = json.dumps(
            to_payload(self.last_state, self.last_tips, self.seq, self.base_size),
            ensure_ascii=False,
        )

    def reset(self):
        """Reimposta lo stato per una nuova partita."""
        self.smoother = Smoother()
        self.tracker = TurnTracker()
        self.prev_frame = None
        self.seq = 0
        self.last_state = GameState()
        self.last_tips = []
        self.last_payload_json = json.dumps(
            to_payload(self.last_state, self.last_tips, self.seq, self.base_size),
            ensure_ascii=False,
        )

    def _read_cards(self, frame: np.ndarray, rects: list, max_tier: Optional[int] = None, kind: str = "board"):
        out = []
        strip = nv.read_strip_stats(frame, rects, kind) if kind == "board" else None
        for i, rect in enumerate(rects):
            if kind == "shop" and not mv.is_minion_card(frame, rect, self.regions):
                out.append(Minion("(incantesimo)", is_spell=True))
                continue
            card, _ = self.reader.read(crop(frame, rect), max_tier=max_tier)
            att, hp = strip[i] if strip else nv.read_minion_stats(frame, rect, kind)
            if card:
                out.append(Minion(card["name"], card["tier"], card.get("tribe", ""), att, hp))
            else:
                out.append(Minion(attack=att, health=hp))
        return out

    def read_state_from_frame(self, frame: np.ndarray) -> GameState:
        """Esegue l'estrazione visiva dello stato da un frame normalizzato base_size."""
        st = GameState(phase=detect_phase(frame, self.regions))
        gold = nv.read_gold(crop(frame, self.regions["gold"]))
        if gold:
            st.gold, st.max_gold = gold
        st.hero_health = nv.read_region(frame, self.regions, "hero_health")
        st.hero_armor = nv.read_region(frame, self.regions, "hero_armor")

        if st.phase == "recruit":
            st.tavern_tier = nv.count_stars(crop(frame, self.regions["tavern_stars"])) or None
            st.upgrade_cost = nv.read_region(frame, self.regions, "upgrade_cost")
            tier = st.tavern_tier
            st.shop_rects = mv.locate_shop(frame, self.regions)
            st.shop = self._read_cards(frame, st.shop_rects, tier, kind="shop")
            st.board_rects = mv.locate_board(frame, self.regions)
            st.board = self._read_cards(frame, st.board_rects, tier + 1 if tier else None, kind="board")

        return st

    def process_frame_bgr(self, frame_bgr: np.ndarray, force_update: bool = False) -> str:
        """Processa un'immagine BGR già dimensionata o da ridimensionare a base_size."""
        h, w = frame_bgr.shape[:2]
        if (w, h) != self.base_size:
            frame = cv2.resize(frame_bgr, self.base_size, interpolation=cv2.INTER_AREA)
        else:
            frame = frame_bgr

        if force_update or capture.is_stable(self.prev_frame, frame):
            st = self.smoother.update(self.read_state_from_frame(frame))
            st.turn = self.tracker.update(st.phase, st.max_gold)
            tips = advisor.structured_advise(st)

            self.seq += 1
            self.last_state = st
            self.last_tips = tips
            self.last_payload_json = json.dumps(
                to_payload(st, tips, self.seq, self.base_size),
                ensure_ascii=False,
            )

        self.prev_frame = frame
        return self.last_payload_json

    def process_frame_rgba_bytes(
        self,
        rgba_bytes: bytes,
        width: int,
        height: int,
        row_stride: int = 0,
        force_update: bool = False,
    ) -> str:
        """Riceve un buffer byte RGBA (es. ImageReader Android) e restituisce il JSON."""
        # Se c'è row padding (stride > width * 4)
        if row_stride > 0 and row_stride != width * 4:
            arr = np.frombuffer(rgba_bytes, dtype=np.uint8).reshape((height, row_stride))
            arr = arr[:, :width * 4].reshape((height, width, 4))
        else:
            arr = np.frombuffer(rgba_bytes, dtype=np.uint8).reshape((height, width, 4))

        frame_bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        return self.process_frame_bgr(frame_bgr, force_update=force_update)


# Singleton helper per Chaquopy
_engine_instance: Optional[StandaloneEngine] = None


def get_engine() -> StandaloneEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = StandaloneEngine()
    return _engine_instance


def process_rgba(rgba_bytes: bytes, width: int, height: int, row_stride: int = 0, force_update: bool = False) -> str:
    """Funzione ponte globale invocabile direttamente da Kotlin via Chaquopy."""
    return get_engine().process_frame_rgba_bytes(rgba_bytes, width, height, row_stride, force_update=force_update)


def reset_engine():
    """Funzione ponte per resettare lo stato all'inizio di una nuova partita."""
    get_engine().reset()
