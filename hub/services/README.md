# hub/services — adapters to the real world (week 2+)

The core runtime is dependency-free by design; everything with a heavier
footprint lives here behind the same topic contract:

- `mqtt_bridge.py` ✅ — paho-mqtt ↔ `hub.core.bus` bridge. Role-filtered
  directions (hub: cmd out / data in; node: data out / cmd in) make loops
  impossible; inbound messages are queue-pumped so the twin stays
  single-threaded. mTLS ✅: pass `tls=` with the identity from
  `tools/gen_certs.py`; broker ACLs confine each cert CN to its namespace.
- `store.py` ✅ — SQLite (WAL) journaling: twin changes, action records
  (cause/evidence/expected/observed/outcome). Rollup tables: TODO.
- `api.py` — FastAPI + WebSocket for the dashboard: live points + events. TODO.

Rule: nothing in `hub/agents/` or `hub/twin/` may import from here.
