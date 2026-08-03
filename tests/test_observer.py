"""Observer range-checking on the ENV and PANEL nodes' real topic contracts.

nodes/env_node/env_node.ino publishes domora/env1/living/temp_c etc., and
nodes/panel_node/panel_node.ino publishes domora/fp1/main_panel/voltage_v
etc. — these ranges didn't exist before the firmware did. A sensor that lies
(or a wiring fault feeding garbage ADC counts) must be quarantined loudly,
never trusted into the twin silently (hub/agents/observer.py's whole reason
to exist).
"""

from hub.agents.observer import Observer
from hub.core.bus import EventBus
from hub.twin.graph import KnowledgeGraph
from hub.twin.state import TwinState
from hub.main import HOUSE_CONFIG


def _make_observer():
    bus, twin = EventBus(), TwinState()
    graph = KnowledgeGraph.load(HOUSE_CONFIG)
    return Observer(bus, twin, graph, lambda *a: None), bus, twin


def test_valid_env_readings_reach_the_twin():
    obs, bus, twin = _make_observer()
    bus.publish("domora/env1/living/temp_c", {"value": 24.5})
    bus.publish("domora/env1/living/humidity_pct", {"value": 55.0})
    bus.publish("domora/env1/living/lux", {"value": 300.0})
    bus.publish("domora/env1/living/door", {"value": 1})
    assert twin.get("living.temp_c") == 24.5
    assert twin.get("living.humidity_pct") == 55.0
    assert twin.get("living.lux") == 300.0
    assert twin.get("living.door") == 1
    assert obs.rejected == 0


def test_impossible_temperature_is_quarantined_not_trusted():
    obs, bus, twin = _make_observer()
    bus.publish("domora/env1/living/temp_c", {"value": 512.0})  # e.g. a bad I2C read
    assert twin.get("living.temp_c") is None, "an out-of-range reading must never reach the twin"
    assert obs.rejected == 1
    assert twin.get("health.env1.temp_c") == "suspect"


def test_impossible_humidity_is_quarantined():
    obs, bus, twin = _make_observer()
    bus.publish("domora/env1/living/humidity_pct", {"value": -5.0})
    assert twin.get("living.humidity_pct") is None
    assert obs.rejected == 1


def test_valid_panel_readings_reach_the_twin():
    """Every topic nodes/panel_node/panel_node.ino publishes, on the real keys."""
    obs, bus, twin = _make_observer()
    bus.publish("domora/fp1/main_panel/power_w", {"value": 1840.0})
    bus.publish("domora/fp1/main_panel/voltage_v", {"value": 231.4})
    bus.publish("domora/fp1/main_panel/frequency_hz", {"value": 49.9})
    bus.publish("domora/fp1/main_panel/power_factor", {"value": 0.94})
    bus.publish("domora/fp1/main_panel/energy_kwh", {"value": 128.6})
    bus.publish("domora/fp1/panel.ct1/current_a", {"value": 8.4})

    # main_panel.power_w is the exact key hub/agents/energy.py reads — this
    # assertion is what ties the firmware's topic to the NILM consumer.
    assert twin.get("main_panel.power_w") == 1840.0
    assert twin.get("main_panel.voltage_v") == 231.4
    assert twin.get("main_panel.frequency_hz") == 49.9
    assert twin.get("main_panel.power_factor") == 0.94
    assert twin.get("main_panel.energy_kwh") == 128.6
    assert twin.get("panel.ct1.current_a") == 8.4
    assert obs.rejected == 0


def test_garbage_mains_voltage_is_quarantined():
    obs, bus, twin = _make_observer()
    # What a failed Modbus read looks like if it is ever mis-parsed rather
    # than returning NAN: a raw register value straight through as volts.
    bus.publish("domora/fp1/main_panel/voltage_v", {"value": 65535.0})
    assert twin.get("main_panel.voltage_v") is None
    assert obs.rejected == 1
    assert twin.get("health.fp1.voltage_v") == "suspect"


def test_power_factor_above_one_is_quarantined():
    obs, bus, twin = _make_observer()
    bus.publish("domora/fp1/main_panel/power_factor", {"value": 1.4})  # physically impossible
    assert twin.get("main_panel.power_factor") is None
    assert obs.rejected == 1


def test_current_beyond_the_clamps_ceiling_is_quarantined():
    obs, bus, twin = _make_observer()
    # SCT-013-030 is a 30 A clamp; 45 A is the clamp or its calibration
    # lying, not a real load it could have measured.
    bus.publish("domora/fp1/panel.ct2/current_a", {"value": 45.0})
    assert twin.get("panel.ct2.current_a") is None
    assert obs.rejected == 1


def test_a_real_mains_surge_is_recorded_not_quarantined():
    """The failure mode of the guard itself, not of the sensor.

    Spec §11.1 wants brownouts and surges logged — that is a stated reason
    this node exists. A voltage range drawn tightly around 230 V nominal
    would silently discard exactly the events worth keeping, so both ends of
    the PZEM-004T v3's real 80-260 V measurement span must survive.
    """
    obs, bus, twin = _make_observer()
    bus.publish("domora/fp1/main_panel/voltage_v", {"value": 258.0})   # surge
    assert twin.get("main_panel.voltage_v") == 258.0
    bus.publish("domora/fp1/main_panel/voltage_v", {"value": 82.0})    # brownout
    assert twin.get("main_panel.voltage_v") == 82.0
    assert obs.rejected == 0
