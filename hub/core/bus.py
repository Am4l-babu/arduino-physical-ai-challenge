"""In-process event bus with MQTT-style topics.

The whole hub speaks this one topic contract. In production the bus is
bridged to a real MQTT broker (see hub/services/); in simulation and tests
it runs standalone, so the closed loop needs zero infrastructure.

Topic scheme:  domora/<node>/<asset>/<point>          sensor data
               domora/cmd/<asset>/<command>           actuation commands
               domora/plan/action                     planner -> actor
               domora/verify/<outcome>                verifier results
               domora/alert/<severity>                escalations
"""

from typing import Callable, Dict, List, Tuple


class EventBus:
    def __init__(self) -> None:
        self._subs: List[Tuple[str, Callable[[str, dict], None]]] = []

    def subscribe(self, pattern: str, callback: Callable[[str, dict], None]) -> None:
        self._subs.append((pattern, callback))

    def publish(self, topic: str, payload: dict) -> None:
        for pattern, cb in list(self._subs):
            if self._match(pattern, topic):
                cb(topic, payload)

    @staticmethod
    def _match(pattern: str, topic: str) -> bool:
        pp = pattern.split("/")
        tp = topic.split("/")
        for i, seg in enumerate(pp):
            if seg == "#":
                return True
            if i >= len(tp) or (seg != "+" and seg != tp[i]):
                return False
        return len(pp) == len(tp)
