"""NILM — non-intrusive load monitoring from one panel CT (spec §9.2).

Phase-1 approach, deliberately classical (Hart-lineage event detection):
robust, explainable, and it runs in pure Python on the hub. Deep NILM waits
until the house has produced its own labelled data.

  EdgeDetector        finds power steps (ΔP ≥ threshold) between stable levels
  SignatureClusterer  groups step magnitudes into appliance signatures,
                      incrementally — no training pass, no dataset needed

The wattage of a step IS the appliance's fingerprint at this resolution;
labels come from the human ("what just turned on?") during week one.
"""

TICK_SECONDS = 1.0  # simulation and node sampling both run at 1 Hz


class EdgeDetector:
    """State machine: STABLE -> TRANSITION -> STABLE, emitting the net step.

    Waiting for the level to settle (rather than diffing adjacent samples)
    makes multi-sample ramps read as one event, not several.
    """

    def __init__(self, threshold_w: float = 20.0, settle_w: float = 8.0) -> None:
        self.threshold = threshold_w
        self.settle = settle_w
        self._stable = None
        self._prev = None
        self._in_transition = False

    def update(self, t: int, watts: float):
        """Feed one sample; returns (t, delta_w) when a step completes, else None."""
        event = None
        if self._prev is None:
            self._prev = self._stable = watts
            return None
        if not self._in_transition:
            if abs(watts - self._stable) >= self.threshold:
                self._in_transition = True
        else:
            if abs(watts - self._prev) <= self.settle:  # level has settled
                delta = watts - self._stable
                if abs(delta) >= self.threshold:
                    event = (t, delta)
                self._stable = watts
                self._in_transition = False
        self._prev = watts
        return event


class SignatureClusterer:
    """Incremental 1-D clustering of |ΔP| with proportional tolerance."""

    def __init__(self, tol_frac: float = 0.15, tol_min_w: float = 30.0) -> None:
        self.tol_frac = tol_frac
        self.tol_min = tol_min_w
        self.clusters = []  # [{"id": int, "mean_w": float, "n": int}]

    def assign(self, magnitude_w: float) -> dict:
        best = None
        for c in self.clusters:
            tol = max(self.tol_min, self.tol_frac * c["mean_w"])
            if abs(magnitude_w - c["mean_w"]) <= tol:
                best = c
                break
        if best is None:
            best = {"id": len(self.clusters) + 1, "mean_w": magnitude_w, "n": 0}
            self.clusters.append(best)
        best["n"] += 1
        best["mean_w"] += (magnitude_w - best["mean_w"]) / best["n"]
        return best
