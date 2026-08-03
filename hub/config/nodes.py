"""Node identity map — THE one place the board-to-role assumption lives.

Every MQTT identity is a physical board with an mTLS cert whose CN doubles
as its broker-ACL username (tools/gen_certs.py), so "which roles share a
node id" is really "which sensors share a circuit board". That is a
hardware-layout fact, and this module is where it is stated — the
simulators, the PKI defaults, and the docs all derive from here rather
than each hardcoding their own copy of the assumption.

The assumption currently encoded (see nodes/README.md for the physical
reasoning): docs/BOM_ORDER.md budgets ONE ESP32-C6 for the whole water
side, so the valve role and the tank role share the identity "fp2". That
is stated, not confirmed — nobody has yet decided whether one board's
leads can reach both the main-line valve and the roof tank in the demo
rig. If the rig needs two boards, the split is one edit here:

    TANK_NODE = "fp3"   # (and provision the new cert: tools/gen_certs.py)

tests/test_node_identity.py proves that claim by doing exactly that edit
in-memory and watching the sims, the PKI defaults, and the closed loop
all follow. Consumers must read these via module attribute
(``nodes.TANK_NODE``), not ``from ... import TANK_NODE`` — a from-import
copies the value at import time, which is precisely how a repoint here
would silently fail to propagate.

Roles, not boards, get names: PANEL_NODE is "the identity whole-house
electrical data arrives under" wherever it physically lives.
"""

# 3x CT clamp + PZEM at the consumer unit -> whole-house NILM.
# Firmware: nodes/panel_node/  Simulator stand-in: sim/virtual_loads.py
PANEL_NODE = "fp1"

# Main valve + line flow meter (the leak loop's actuator and its
# independent verification sensor). Firmware: nodes/tank_node/
# Simulator stand-in: sim/virtual_house.py
VALVE_NODE = "fp2"

# Tank level + pump CT + pump relay (the dry-run loop).
# Firmware: nodes/tank_node/  Simulator stand-in: sim/virtual_pump.py
# Same board as VALVE_NODE today — the assumption described above.
TANK_NODE = "fp2"

# BME280 / radar / PIR / lux / reed in the living room.
# Firmware: nodes/env_node/  Simulated occupancy: sim/virtual_house.py
ENV_NODE = "env1"

# ESP32-S3 audio events — a PLAN.md week-7 stretch. Has a constant so the
# name is decided in one place, but stays out of default_pki_nodes() until
# the firmware exists, matching the long-standing CLI default.
PERCEPTION_NODE = "perc1"


def default_pki_nodes() -> list:
    """The identities tools/gen_certs.py provisions when --nodes is omitted.

    Derived, not listed, so a split (TANK_NODE = "fp3") grows the PKI
    automatically. Order-preserving dedupe: today VALVE_NODE and TANK_NODE
    are the same board and must yield one cert, not two.
    """
    return list(dict.fromkeys([PANEL_NODE, VALVE_NODE, TANK_NODE, ENV_NODE]))
