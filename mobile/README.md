# DOMORA Mobile

A native Flutter client for the DOMORA hub — full parity with the web
[`studio/`](../studio) app, talking to the exact same backend over the exact
same contract. See [docs/APP_PLAN.md §9](../docs/APP_PLAN.md) for the plan
this was built against.

## What it talks to

Nothing here is a new backend surface. Every screen is a client of endpoints
the hub already serves ([hub/services/api.py](../hub/services/api.py)):

| Endpoint | Used by |
|---|---|
| `GET /ws` | everything live — `snapshot` / `point` / `event` frames |
| `POST /ai` | the AI chat screen |
| `GET /nilm` | Energy's appliance breakdown, Appliance detail, Insights |
| `GET /graph` | Settings (the real house knowledge graph) |
| `GET /history?key=` | journal-backed trend charts (`--playback` runs only) |
| `GET /playback.json` | History's scrubber |

Unlike Studio — which the hub *serves*, so relative URLs just work — this app
is a separate OS process, often on a separate device, so it has to be told
`host:port` somewhere. **It does not gate on that**: the app opens straight
into the Home screen every time, with a previously-saved address (if any)
dialed in the background. **Settings → Hub connection** is where an address
is entered or changed, persisted via `shared_preferences` — at any point
after launch, never as a precondition for it. Whenever the hub isn't live, a
tap-through banner (every tab) and the app-bar status pill both point at that
same card, so getting connected stays one tap away without blocking anything
else in the meantime.

## Running it

```bash
# 1. start a hub (any scenario: leak, stuck, energy, dryrun, dryrun_stuck)
python -m hub.services.api --scenario stuck

# 2. run the app, then open Settings → Hub connection and enter the address
flutter run                      # 10.0.2.2:8080 from the Android emulator
```

For History to have anything to scrub, record a journal first and serve it:

```bash
python -m hub.main --scenario stuck --journal demo.db
python -m hub.services.api --playback demo.db
```

## Structure

```text
lib/
  core/     store · hub_client · twin · nilm · insights · playback · format
  widgets/  glass_card · stat_tile · health_dot · line_chart · bar_chart · incident_row
  screens/  app_shell · home · ai · energy · water · security
            room · appliance · sensor · history · insights · settings · search
```

**Dependencies are deliberately minimal** — `web_socket_channel`, `http`,
`shared_preferences`, and nothing else. No state-management package
(`ChangeNotifier` + `AnimatedBuilder` mirrors `studio/core/store.js` directly)
and no charting package (`CustomPainter` line chart + widget-composed bar
chart, built to the same mark specs as `studio/ui/*.js`, reusing the palette
already validated during the Studio build).

## Tests

```bash
flutter test      # 56 tests
flutter analyze
```

Every fixture in `test/fixtures/` is a **real response captured from a
running hub in this repo** — real `/ws` frame streams from `stuck` and
`energy` runs, a real `/nilm` ledger, a real `/graph`, a real `/history`
series, and a real `/playback.json` built from an actual recorded journal.
None of it is hand-written JSON, and the HTTP fixtures are replayed as raw
bytes so screens parse exactly what the server sent.

## Honest limits

Carried over unchanged from [docs/APP_PLAN.md §7](../docs/APP_PLAN.md):

- **No manual actuation, anywhere — including search.** The only actuation
  path in this system is the planner dispatching through
  [hub/agents/safety.py](../hub/agents/safety.py)'s capability table, and
  `CLAUDE.md` requires an explicit invariant review before that table changes.
  The search screen navigates; it does not command.
- **No LLM.** AI answers come from `hub/services/ai_query.py`, which is
  deterministic and grounded in the real twin / NILM ledger / journal.
- Appliance health score, remaining-useful-life, failure probability, and
  sound/vibration analysis are **not computed anywhere in this codebase** —
  the Appliance page says so rather than showing invented numbers.
- Doors, windows, glass-break, smoke, and gas have **no node reporting them**
  yet; Security lists them as not connected rather than faking widgets.
- No 3D twin, no voice, no login/roles/accounts.
- iOS is unbuildable without a Mac/Xcode. Android is the ship target; the web
  target is useful for fast iteration, but browser CORS blocks its
  cross-origin HTTP calls (the WebSocket is unaffected), so HTTP-backed
  screens degrade to their honest empty states there. Native targets have no
  such restriction.
