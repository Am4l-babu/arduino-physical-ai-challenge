"""The real-time twin: last-known state of every point, with provenance.

Every value carries {value, t, source, confidence}. Silence is meaningful:
a point that stops updating goes stale, and staleness is itself a signal
(dead node, Wi-Fi hole, power loss in that room).
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

STALE_AFTER = 15  # ticks without update before a point is considered stale


@dataclass
class Point:
    value: Any
    t: int
    source: str
    confidence: float = 1.0


class TwinState:
    def __init__(self) -> None:
        self.points: Dict[str, Point] = {}
        self.now: int = 0
        self.on_set = None  # optional journal hook: fn(key, Point)

    def set(self, key: str, value: Any, source: str, confidence: float = 1.0) -> None:
        p = Point(value, self.now, source, confidence)
        self.points[key] = p
        if self.on_set is not None:
            self.on_set(key, p)

    def get(self, key: str, default: Any = None) -> Any:
        p = self.points.get(key)
        return p.value if p is not None else default

    def point(self, key: str) -> Optional[Point]:
        return self.points.get(key)

    def age(self, key: str) -> Optional[int]:
        p = self.points.get(key)
        return self.now - p.t if p is not None else None

    def is_stale(self, key: str) -> bool:
        age = self.age(key)
        return age is None or age > STALE_AFTER

    def snapshot(self) -> Dict[str, Any]:
        return {k: p.value for k, p in self.points.items()}
