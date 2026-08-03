"""The node identity map is the single source of the board-to-role assumption.

nodes/README.md records an assumption, not a confirmed layout: one ESP32-C6
carries the whole water side, so the VALVE and TANK roles share the identity
"fp2". These tests prove the promise hub/config/nodes.py makes about that
assumption — that flipping it (a two-board water side) is ONE edit there,
propagating to every simulator and the PKI defaults with no other file
touched, and that the hub's cognition never cared which board a point
arrived from in the first place.
"""

from hub.config import nodes
from hub.core.bus import EventBus
from hub.main import run
from sim.virtual_house import VirtualHouse
from sim.virtual_loads import VirtualLoads
from sim.virtual_pump import VirtualPump


def _node_ids_published(sim_factory, ticks=3):
    """Run a simulator against a bare bus; return {topic: node_id_segment}."""
    bus = EventBus()
    seen = {}
    bus.subscribe("domora/#", lambda t, p: seen.setdefault(t, t.split("/")[1]))
    sim = sim_factory(bus)
    for t in range(ticks):
        sim.tick(t)
    return seen


def test_simulators_publish_under_their_declared_roles():
    """Every sim topic carries the identity its role constant declares."""
    house = _node_ids_published(VirtualHouse)
    assert house[f"domora/{nodes.VALVE_NODE}/tank.line/flow_lpm"] == nodes.VALVE_NODE
    assert house[f"domora/{nodes.VALVE_NODE}/main_valve/valve_state"] == nodes.VALVE_NODE
    assert house[f"domora/{nodes.TANK_NODE}/water_tank/level_pct"] == nodes.TANK_NODE
    assert house[f"domora/{nodes.ENV_NODE}/living/radar"] == nodes.ENV_NODE

    pump = _node_ids_published(VirtualPump)
    assert set(pump.values()) == {nodes.TANK_NODE}, \
        "everything the pump sim publishes is the TANK role"

    loads = _node_ids_published(VirtualLoads)
    assert set(loads.values()) == {nodes.PANEL_NODE}


def test_pki_default_covers_every_identity_the_sims_use():
    """nodes/README.md's 'matching tools/gen_certs.py's defaults' — as a test.

    An identity a simulator publishes under but the PKI never provisions is a
    board that cannot authenticate to the real broker: exactly the kind of
    drift that stays invisible until hardware bring-up week.
    """
    published = set()
    for factory in (VirtualHouse, VirtualPump, VirtualLoads):
        published |= set(_node_ids_published(factory).values())
    # Guard against this test passing vacuously: an empty `published` (say,
    # the wildcard tap silently breaking) would satisfy <= trivially.
    assert published, "the sims must have published under at least one identity"
    assert published <= set(nodes.default_pki_nodes())


def test_pki_default_dedupes_shared_boards():
    """VALVE and TANK share one board today -> one cert, not two."""
    defaults = nodes.default_pki_nodes()
    assert len(defaults) == len(set(defaults))
    assert defaults == ["fp1", "fp2", "env1"], \
        "the derived default must match the long-standing CLI default"


def test_splitting_the_water_side_is_one_edit(monkeypatch):
    """THE claim this module exists to keep true.

    If the demo rig needs two boards for the water side, the entire change
    is TANK_NODE in hub/config/nodes.py. Simulate exactly that edit and
    watch it propagate: the pump sim and the house sim's tank level move to
    the new identity, flow/valve stay put, and the PKI default grows to
    provision the new board — with zero edits to any simulator.
    """
    monkeypatch.setattr(nodes, "TANK_NODE", "fp3")

    pump = _node_ids_published(VirtualPump)
    assert set(pump.values()) == {"fp3"}, "tank+pump topics follow the repoint"

    house = _node_ids_published(VirtualHouse)
    assert house["domora/fp3/water_tank/level_pct"] == "fp3", \
        "the level probe rides the tank board"
    assert house[f"domora/{nodes.VALVE_NODE}/tank.line/flow_lpm"] == "fp2", \
        "valve-side topics stay on the valve board"

    assert nodes.default_pki_nodes() == ["fp1", "fp2", "fp3", "env1"], \
        "the new board gets a cert without a second list to remember"


def test_closed_loops_are_identity_agnostic(monkeypatch):
    """The hub's cognition keys on assets, never on which board reported them.

    Run both flagship loops with every water identity repointed to ids no
    config has ever mentioned. Detection, actuation, and verification must
    all still close — proving a future physical re-shuffle of sensors across
    boards is a nodes.py edit, not a hub change.
    """
    monkeypatch.setattr(nodes, "VALVE_NODE", "fp8")
    monkeypatch.setattr(nodes, "TANK_NODE", "fp9")

    leak = run(scenario="leak", quiet=True)
    assert len(leak["confirmed"]) == 1 and leak["final_flow_lpm"] == 0.0

    dry = run(scenario="dryrun", quiet=True)
    assert len(dry["confirmed"]) == 1 and dry["failed"] == [], \
        "dry-run cut must verify through the CT clamp on the repointed board"
