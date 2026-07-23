# Dashboard — Three.js twin view (week 5)

Served from the hub itself (proves local-first; judges' phones need no install).

- **Twin view:** schematic isometric house (glTF authored in Blender), layer
  toggles: occupancy glows, water flow along pipe splines, energy ribbons,
  alert badges on the offending asset. Data *is* the graphics — no vanity 3D.
- **Operations view:** event timeline rendering each action's
  cause → evidence → command → verification chain as connected cards; the
  narration log from `hub/main.py` is exactly this data.
- **Playback:** scrub the twin through stored state (the leak incident at 20×).
- Binding: WebSocket from `hub/services/api.py` (FastAPI) — points stream +
  event stream, same topic contract as the bus.

Decision record for Three.js over Unity/Godot/Omniverse: spec §10.
