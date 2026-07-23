"""Base classes for DOMORA's cognitive agents.

The design deliberately mirrors how an agentic assistant works:

  observe   -> read the world before acting (never act on assumptions)
  think     -> turn raw readings into meaning, with confidence attached
  plan      -> every intended action states its EXPECTED EFFECT up front
  act       -> execute through a narrow, auditable interface
  verify    -> check reality against the expectation; never trust an ACK
  escalate  -> when verification fails, say so plainly and hand off
  learn     -> fold outcomes back into baselines

Each agent owns exactly one of these responsibilities and communicates
only via the bus and the twin — no agent calls another directly.
"""

import itertools
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from hub.core.bus import EventBus
from hub.twin.graph import KnowledgeGraph
from hub.twin.state import TwinState

_action_ids = itertools.count(1)


@dataclass
class Expectation:
    """The falsifiable claim an action makes about the world."""

    point: str
    predicate: Callable[[object], bool]
    describe: str
    deadline_ticks: int


@dataclass
class Action:
    command_topic: str
    payload: dict
    cause: str
    evidence: dict
    expectation: Expectation
    id: int = field(default_factory=lambda: next(_action_ids))
    dispatched_at: Optional[int] = None
    retries: int = 0
    status: str = "proposed"  # proposed | vetoed | dispatched | confirmed | failed


class Agent:
    name = "agent"

    def __init__(self, bus: EventBus, twin: TwinState, graph: KnowledgeGraph, narrate: Callable[[int, str, str], None]) -> None:
        self.bus = bus
        self.twin = twin
        self.graph = graph
        self._narrate = narrate

    def say(self, t: int, message: str) -> None:
        self._narrate(t, self.name, message)

    def tick(self, t: int) -> None:  # pragma: no cover - overridden
        pass
