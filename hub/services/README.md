# hub/services — adapters to the real world (week 2+)

The core runtime is dependency-free by design; everything with a heavier
footprint lives here behind the same topic contract:

- `mqtt_bridge.py` ✅ — paho-mqtt ↔ `hub.core.bus` bridge. Role-filtered
  directions (hub: cmd out / data in; node: data out / cmd in) make loops
  impossible; inbound messages are queue-pumped so the twin stays
  single-threaded. mTLS ✅: pass `tls=` with the identity from
  `tools/gen_certs.py`; broker ACLs confine each cert CN to its namespace.
  Verified against a real, apt-installed Mosquitto deployed on the actual
  UNO Q — hub (agents+twin) on the board, a simulated field node reaching
  it over real Wi-Fi from a separate machine: the leak loop closes end to
  end over the real network, not just localhost or a test-spawned broker.
- `store.py` ✅ — SQLite (WAL) journaling: twin changes, action records
  (cause/evidence/expected/observed/outcome). Rollup tables: TODO.
- `api.py` ✅ — stdlib-only HTTP + WebSocket (no FastAPI — the hub must run
  dependency-free on the UNO Q) for the dashboard: live points + events +
  journal playback. Verified running as a live service on the board itself.

`tools/gen_certs.py --broker-host <ip>` puts the broker's real LAN address
in its cert's SAN — without it, the broker cert only validates for
localhost/127.0.0.1 and any real network client (a real ESP32, or a hub
reached from off-board) fails TLS hostname verification. Found this the
first time the broker was tested against something other than loopback.

Rule: nothing in `hub/agents/` or `hub/twin/` may import from here.
