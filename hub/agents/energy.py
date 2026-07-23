"""EnergySense — the NILM virtual sensor as an agent.

Reads one twin point (main_panel.power_w), and writes per-appliance state
and an energy ledger the house never had hardware to measure:

  nilm.<name>.state       on / off
  nilm.<name>.power_w     the signature wattage
  nilm.<name>.energy_wh   accumulated per appliance

Clusters start unlabelled; label_nearest() is the "what just turned on?"
one-tap flow the dashboard exposes in week one of a deployment.
"""

from hub.agents.base import Agent
from hub.twin.nilm import EdgeDetector, SignatureClusterer, TICK_SECONDS


class EnergySense(Agent):
    name = "energy"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.detector = EdgeDetector()
        self.clusterer = SignatureClusterer()
        self.labels = {}      # cluster_id -> human name
        self.on_since = {}    # cluster_id -> (t_on, magnitude_w)
        self.energy_wh = {}   # display name -> accumulated Wh

    def _key(self, cluster_id: int) -> str:
        return self.labels.get(cluster_id, f"cluster{cluster_id}")

    def tick(self, t: int) -> None:
        watts = self.twin.get("main_panel.power_w")
        if watts is None:
            return
        event = self.detector.update(t, watts)
        if event is None:
            return
        t_ev, delta = event
        cluster = self.clusterer.assign(abs(delta))
        key = self._key(cluster["id"])
        tag = "" if cluster["id"] in self.labels else " (unlabelled — ask the user)"

        if delta > 0:
            self.on_since[cluster["id"]] = (t_ev, abs(delta))
            self.twin.set(f"nilm.{key}.state", "on", source="nilm", confidence=0.8)
            self.twin.set(f"nilm.{key}.power_w", round(cluster["mean_w"]), source="nilm")
            self.say(t, f"+{delta:.0f} W edge -> {key} ON{tag}")
        else:
            self.twin.set(f"nilm.{key}.state", "off", source="nilm", confidence=0.8)
            started = self.on_since.pop(cluster["id"], None)
            if started is not None:
                t_on, magnitude = started
                wh = magnitude * (t_ev - t_on) * TICK_SECONDS / 3600.0
                self.energy_wh[key] = round(self.energy_wh.get(key, 0.0) + wh, 3)
                self.twin.set(f"nilm.{key}.energy_wh", self.energy_wh[key], source="nilm")
                self.say(t, f"{delta:.0f} W edge -> {key} OFF after {t_ev - t_on}s "
                            f"({wh:.2f} Wh this run)")
            else:
                self.say(t, f"{delta:.0f} W edge -> {key} OFF (no matching ON seen)")

    def label_nearest(self, watts: float, name: str) -> str:
        """The interactive-labelling flow: name the cluster closest to `watts`."""
        if not self.clusterer.clusters:
            return ""
        cluster = min(self.clusterer.clusters, key=lambda c: abs(c["mean_w"] - watts))
        old_key = self._key(cluster["id"])
        self.labels[cluster["id"]] = name
        if old_key in self.energy_wh:  # migrate ledger + twin points to the new name
            self.energy_wh[name] = self.energy_wh.pop(old_key)
            for suffix in ("state", "power_w", "energy_wh"):
                value = self.twin.get(f"nilm.{old_key}.{suffix}")
                if value is not None:
                    self.twin.set(f"nilm.{name}.{suffix}", value, source="nilm")
        self.say(self.twin.now, f"labelled {old_key} ({cluster['mean_w']:.0f} W) as '{name}'")
        return name

    def report(self) -> dict:
        return {
            "clusters": [
                {"label": self._key(c["id"]), "mean_w": round(c["mean_w"]), "events": c["n"]}
                for c in self.clusterer.clusters
            ],
            "energy_wh": dict(self.energy_wh),
        }
