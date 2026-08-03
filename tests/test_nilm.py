"""NILM tests: the pipeline must recover appliances from the aggregate alone.

The simulator's ground truth (VirtualLoads.truth) never touches the bus —
the disaggregator sees only the summed noisy wattage, like a real CT clamp.
"""

from hub.core.bus import EventBus
from hub.main import run
from hub.twin.nilm import EdgeDetector, SignatureClusterer
from sim.virtual_loads import CtChain, VirtualLoads


def test_edge_detector_finds_clean_steps_despite_noise():
    det = EdgeDetector(threshold_w=20.0)
    signal = [100.0] * 10 + [1900.0] * 10 + [100.0] * 10  # kettle-shaped
    signal = [w + ((i * 7919) % 13 - 6) * 0.25 for i, w in enumerate(signal)]  # ±1.5 W noise
    events = [e for i, w in enumerate(signal) if (e := det.update(i, w))]
    deltas = [round(d) for _, d in events]
    assert len(deltas) == 2
    assert 1750 < deltas[0] < 1850 and -1850 < deltas[1] < -1750


def test_clusterer_groups_repeats_and_separates_appliances():
    clu = SignatureClusterer()
    for magnitude in (150, 152, 1800, 148, 60, 1795, 151):
        clu.assign(magnitude)
    means = sorted(round(c["mean_w"]) for c in clu.clusters)
    counts = {round(c["mean_w"]): c["n"] for c in clu.clusters}
    assert len(clu.clusters) == 3, "fridge, kettle, lamp — not seven clusters"
    assert means[0] == 60 and 148 <= means[1] <= 152 and 1795 <= means[2] <= 1800
    assert counts[means[1]] == 4, "all four fridge edges landed in one cluster"


def test_energy_scenario_disaggregates_and_labels():
    s = run(scenario="energy", quiet=True)
    nilm = s["nilm"]
    labels = {c["label"]: c for c in nilm["clusters"]}

    assert len(nilm["clusters"]) == 3
    assert "kettle" in labels, "interactive labelling must rename the 1.8 kW cluster"
    assert 1750 <= labels["kettle"]["mean_w"] <= 1850
    assert labels["kettle"]["events"] == 2  # one ON + one OFF edge

    # energy ledger: kettle 1800 W x 15 s = 7.5 Wh (small detection lag allowed)
    assert 6.5 <= nilm["energy_wh"]["kettle"] <= 8.0
    # fridge: 2 cycles x 20 s x 150 W = 1.67 Wh, still unlabelled
    fridge_key = next(k for k in nilm["energy_wh"] if k != "kettle"
                      and 1.0 <= nilm["energy_wh"][k] <= 2.5)
    assert fridge_key.startswith("cluster"), "unlabelled clusters keep generated names"


def test_water_scenarios_unaffected_by_energy_agent():
    s = run(scenario="leak", quiet=True)
    assert len(s["confirmed"]) == 1 and s["final_flow_lpm"] == 0.0


def _cluster_magnitudes(ct_chain=None):
    """Drive the panel simulator through the real NILM primitives, one path each."""
    bus = EventBus()
    samples = []
    bus.subscribe("domora/fp1/main_panel/power_w",
                  lambda _topic, payload: samples.append(payload["value"]))
    loads = VirtualLoads(bus, ct_chain=ct_chain)
    for t in range(120):
        loads.tick(t)

    det, clu = EdgeDetector(), SignatureClusterer()
    for t, watts in enumerate(samples):
        event = det.update(t, watts)
        if event is not None:
            clu.assign(abs(event[1]))
    return sorted(c["mean_w"] for c in clu.clusters)


def test_ct_derived_power_keeps_appliances_separable():
    """POWER_FROM_PZEM = 0 degrades the magnitudes but must not break NILM.

    nodes/panel_node/panel_node.ino can only report `I x V x assumed_PF` when
    no PZEM sits on the incomer. Every appliance is then scaled by its own
    assumed_PF/true_PF ratio — so the question this test answers is whether
    the three appliances still land in three distinct clusters afterwards,
    which is what the whole node exists to make possible.
    """
    ideal = _cluster_magnitudes()
    derived = _cluster_magnitudes(ct_chain=CtChain())

    assert len(ideal) == 3, "baseline: lamp, fridge, kettle"
    assert len(derived) == 3, "the CT-derived path must not merge or split appliances"
    # Still ordered lamp < fridge < kettle, still far apart enough to cluster.
    assert derived[0] < derived[1] < derived[2]


def test_ct_derived_power_misstates_loads_by_their_power_factor():
    """The cost of POWER_FROM_PZEM = 0, measured rather than claimed.

    This is the failure path of the derived config: a CT clamp cannot measure
    the power factor the firmware divides out, so the reported wattage of any
    load is scaled by assumed_PF/true_PF. The kettle (resistive, PF 1.0) comes
    out slightly low; the fridge (compressor motor, PF 0.62) comes out ~53%
    high. Clustering survives that (test above) but the energy ledger does
    not, which is exactly why config.h.example recommends POWER_FROM_PZEM = 1
    whenever the PZEM is on the incomer.
    """
    chain = CtChain()
    derived = _cluster_magnitudes(ct_chain=chain)
    lamp, fridge, kettle = derived

    def expected(true_w, true_pf):
        return true_w * chain.assumed_pf / true_pf

    assert abs(kettle - expected(1800.0, 1.00)) < 20.0    # 1710 W: 5% understated
    assert abs(fridge - expected(150.0, 0.62)) < 20.0     # 230 W: 53% overstated
    assert abs(lamp - expected(60.0, 0.95)) < 20.0        # 60 W: PF matches, accurate

    # The direction of the error matters: a motor reads high, a heater reads low.
    assert fridge > 150.0 and kettle < 1800.0
