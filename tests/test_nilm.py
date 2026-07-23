"""NILM tests: the pipeline must recover appliances from the aggregate alone.

The simulator's ground truth (VirtualLoads.truth) never touches the bus —
the disaggregator sees only the summed noisy wattage, like a real CT clamp.
"""

from hub.main import run
from hub.twin.nilm import EdgeDetector, SignatureClusterer


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
