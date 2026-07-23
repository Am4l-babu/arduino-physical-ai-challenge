"""Knowledge graph: what the house IS — rooms, assets, and typed connections.

This is what lets reasoning generalize: "close the valve upstream of the
leak" is a graph traversal, not an AI problem. Loaded from config/house.json.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


class KnowledgeGraph:
    def __init__(self, assets: List[dict], edges: List[dict]) -> None:
        self.assets: Dict[str, dict] = {a["id"]: a for a in assets}
        self.edges: List[dict] = edges

    @classmethod
    def load(cls, path: Path) -> "KnowledgeGraph":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data["assets"], data["edges"])

    def related(self, asset_id: str, rel: str, reverse: bool = False) -> List[str]:
        if reverse:
            return [e["src"] for e in self.edges if e["rel"] == rel and e["dst"] == asset_id]
        return [e["dst"] for e in self.edges if e["rel"] == rel and e["src"] == asset_id]

    def upstream_shutoff(self, asset_id: str) -> Optional[str]:
        """Walk `feeds` edges backwards until a controllable valve is found."""
        frontier = [asset_id]
        seen = set()
        while frontier:
            current = frontier.pop(0)
            if current in seen:
                continue
            seen.add(current)
            for feeder in self.related(current, "feeds", reverse=True):
                if self.assets.get(feeder, {}).get("type") == "valve":
                    return feeder
                frontier.append(feeder)
        return None

    def of_type(self, asset_type: str) -> List[str]:
        return [a_id for a_id, a in self.assets.items() if a["type"] == asset_type]
