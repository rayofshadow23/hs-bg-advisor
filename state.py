"""Stato di gioco letto dallo schermo."""
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Minion:
    name: str = "?"
    tier: int = 0
    tribe: str = ""
    attack: Optional[int] = None
    health: Optional[int] = None
    is_spell: bool = False              # incantesimo della taverna (nello shop, senza goccia della vita)


@dataclass
class GameState:
    phase: str = "unknown"          # recruit | combat | menu | unknown
    gold: Optional[int] = None
    max_gold: Optional[int] = None      # il contatore mostra "oro/massimo", es. 0/5
    tavern_tier: Optional[int] = None   # numero di stelle del badge
    upgrade_cost: Optional[int] = None  # costo attuale per salire di livello
    hero_health: Optional[int] = None
    hero_armor: Optional[int] = None
    turn: Optional[int] = None          # non e' sullo schermo: vedi TurnTracker
    shop: list = field(default_factory=list)
    board: list = field(default_factory=list)
    hand: list = field(default_factory=list)   # non ancora letta dallo schermo: lista vuota = sconosciuta
    frozen: Optional[bool] = None              # shop congelato? non ancora letto
    shop_rects: list = field(default_factory=list)
    board_rects: list = field(default_factory=list)

    def is_plausible(self):
        """Controlli di coerenza per scartare letture OCR rumorose."""
        if self.gold is not None and not 0 <= self.gold <= 10:
            return False
        if self.max_gold is not None and not 3 <= self.max_gold <= 10:
            return False
        if None not in (self.gold, self.max_gold) and self.gold > self.max_gold:
            return False
        if self.tavern_tier is not None and not 1 <= self.tavern_tier <= 6:
            return False
        if self.hero_health is not None and not 0 <= self.hero_health <= 60:
            return False
        return True


class Smoother:
    """Vota a maggioranza sugli ultimi N valori di ogni campo scalare."""

    FIELDS = ("phase", "gold", "max_gold", "tavern_tier", "upgrade_cost", "hero_health", "hero_armor")

    def __init__(self, window=3):
        self.hist = {f: deque(maxlen=window) for f in self.FIELDS}

    def update(self, state: GameState) -> GameState:
        if state.is_plausible():
            for f in self.FIELDS:
                v = getattr(state, f)
                if v is not None:
                    self.hist[f].append(v)
        for f in self.FIELDS:
            if self.hist[f]:
                setattr(state, f, Counter(self.hist[f]).most_common(1)[0][0])
        return state


class TurnTracker:
    """Il numero del turno non compare sullo schermo, ma l'oro massimo e' turno + 2 (tetto 10).

    Fino al turno 7 il turno si ricava dall'oro massimo; dal turno 8 in poi l'oro massimo e' 10,
    quindi si conta ogni passaggio da combattimento ad acquisto."""

    def __init__(self):
        self.turn = None
        self._last_phase = None

    def update(self, phase, max_gold):
        if max_gold is not None and max_gold < 10:
            self.turn = max_gold - 2
        elif max_gold == 10 and (self.turn is None or self.turn < 8):
            self.turn = 8
        elif phase == "recruit" and self._last_phase == "combat" and self.turn is not None:
            self.turn += 1
        if phase in ("recruit", "combat"):
            self._last_phase = phase
        return self.turn
