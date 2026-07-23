# Dashboard — hub-served twin view (week 5)

Served from the hub itself (proves local-first; judges' phones need no install).

    python -m hub.services.api --scenario stuck   # then open http://localhost:8080

- **Operations view — ✅ built** (`index.html`): event timeline rendering each
  action's cause → evidence → command → verification chain as connected cards,
  plus a live points table and a cognitive-event feed. Theme-aware. The
  narration log from `hub/main.py` is exactly this data.
- **Twin view — ✅ built (as inline SVG):** schematic floor plan bound to live
  twin points — occupancy glow (`house.occupied`), tank level bar
  (`water_tank.level_pct`), animated pipe flow (`tank.line.flow_lpm`) that turns
  red on `virtual.water.leak_suspected`, main-valve state + a pulsing suspect
  badge (`health.main_valve`), and a status strip. Data *is* the graphics.
  **Deviation from spec §10 (Three.js):** built dependency-free SVG — nothing to
  vendor, no CDN needed at the venue. A 3D/glTF pass stays a Phase-2 option.
- **Playback — ✅ built:** scrub the twin through stored state via the SQLite
  journal. `store.JournalReader` rebuilds a recorded run as the *same* frame
  contract the live WebSocket emits, so playback renders through the identical
  timeline/points code — no second renderer. Record with
  `python -m hub.main --scenario stuck --journal demo.db`, then
  `python -m hub.services.api --playback demo.db` and scrub back through the
  incident.

## Transport

`hub/services/api.py` — a **stdlib-only** HTTP + RFC 6455 WebSocket server (no
FastAPI/uvicorn, so the hub stays dependency-free on a 2 GB UNO Q). It taps the
same bus + twin the agents use, broadcasts every event and point-update, and
replays a bounded history to late-joining clients. Each client has its own
bounded send queue, so a slow phone can never stall the agent loop. Same topic
contract as the bus.

Decision record for Three.js over Unity/Godot/Omniverse: spec §10.
