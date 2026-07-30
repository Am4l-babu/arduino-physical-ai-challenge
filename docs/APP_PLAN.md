# DOMORA Studio — App Build Plan

> **What this is.** The premium, JARVIS-class front-end for DOMORA — the
> "OS" the user experiences. "OS" is the *product name*, not a real operating
> system: this is a web application (the **DOMORA Studio / Web** surface from
> the ecosystem list) that sits on top of the hub runtime already built in
> this repo and makes the house feel alive.
>
> **What this is not.** Not a rewrite of the hub. Not the full multi-year
> vision. AR/VR, robotics, drones, offline local-LLM voice, multi-house /
> factory / hospital modes stay in the spec's Phase-3+/Tier-F backlog
> ([docs/DOMORA_SPEC.md](DOMORA_SPEC.md) §6.4, §20). This plan builds the
> parts that are real and buildable now, in thin vertical slices, each one
> driven by data the hub actually emits.

---

## 0 · Grounding — what the backend already gives us

The app is a **client** of the hub. No new hub logic is required for the UI to
be impressive; the intelligence already runs. The contract we build against:

### Live transport — `GET /ws` (RFC 6455, already in [hub/services/api.py](../hub/services/api.py))
Three message shapes arrive over the socket:

| `type` | Fields | Meaning |
|---|---|---|
| `snapshot` | `t`, `points{key → {value,t,source,confidence}}` | Full twin state on connect |
| `point` | `key`, `value`, `t`, `source`, `confidence` | One twin point changed |
| `event` | `topic`, `payload`, `t` | A bus event (cognition + raw sensor) |

### Real twin point keys (what the house *is*, right now)
```
house.occupied            bool      whole-house occupancy fusion
house.fixtures_open       int/bool  taps/valves open
living.pir, living.radar  bool      raw room presence
tank.line.flow_lpm        float     main line flow (L/min)
water_tank.level_pct       float     tank fill %
main_valve.valve_state    "open"|"closed"
pump.pump_state           "on"|"off"
pump.current_a            float     pump CT-clamp current
main_panel.power_w        float     whole-house power (NILM source)
virtual.water.leak_suspected    bool  + virtual.water.leak_evidence
virtual.pump.dryrun_suspected   bool  + virtual.pump.dryrun_evidence
virtual.tank.slope, virtual.tank.empty_eta_ticks
health.main_valve, health.pump  "suspect" when independently doubted
```
NILM (energy scenario) adds a per-appliance ledger (fridge / kettle / lamp)
recovered from `main_panel.power_w` alone.

### Cognitive event topics (the "mind" of the house — this is the wow)
```
domora/plan/action        payload.action = {id,cause,evidence,command_topic,expectation,status}
domora/act/dispatched     payload.action (command sent)
domora/verify/confirmed   payload.action_id (independent sensor agreed)
domora/alert/critical     payload.action_id, payload.reason (escalation)
domora/alert/veto         safety.py refused an action
domora/cmd/pump/off       raw command
domora/<node>/<sys>/<pt>  raw sensor traffic
```

### Scenarios to demo against (`--scenario`)
`leak` (flagship close-the-valve loop) · `stuck` (valve fails → escalation) ·
`energy` (NILM disaggregation) · `dryrun` / `dryrun_stuck` (pump protection).

**Design principle inherited from the repo: _data is the graphics._** Every
pixel that moves is bound to a real point or event above. No fake dials.

---

## 1 · Design language — "DOMORA" (unique, not a clone)

A single, ownable visual system. Dark-first, glass, soft glow, depth, calm.
Not a copy of VisionOS / Nothing / Tesla — it borrows the *principles*
(depth, restraint, living motion) and commits to its own tokens.

**Core idea: the house is an organism; the UI is its nervous system.**
State is communicated primarily through **color-as-health** and **ambient
motion**, exactly the vocabulary the brief asks for:

| State | Token | Meaning |
|---|---|---|
| 🟢 Normal | `--st-ok` | healthy / nominal |
| 🟡 Warning | `--st-warn` | attention, not urgent |
| 🔴 Critical | `--st-crit` | leak / escalation / danger |
| 🔵 Learning | `--st-learn` | model still calibrating |
| 🟣 Prediction | `--st-pred` | a forecast / simulated future |

**Design tokens (CSS custom properties, single source of truth in `tokens.css`):**
- **Color:** near-black layered backgrounds (`--bg-0`…`--bg-2`), glass panels
  (`--glass` = translucent + `backdrop-filter: blur()` + hairline border),
  one cool accent (`--accent`, electric cyan-blue), the five state hues above,
  each with a matched low-alpha glow (`--*-glow`).
- **Type:** one geometric/grotesk UI face (system stack fallback, no CDN),
  one mono for data. Scale: 11 / 12 / 13 / 15 / 18 / 24 / 40. Tight tracking
  on display sizes.
- **Space:** 4px base grid (4/8/12/16/24/32). Generous. Nothing crowded.
- **Radius / shadow:** `--r-1: 10px`, `--r-2: 16px`, `--r-3: 24px`; soft,
  large, low-opacity shadows + inner top-highlight for the glass edge.
- **Motion:** one shared easing (`--ease: cubic-bezier(.22,.61,.36,1)`),
  durations 120/200/320/500ms. A slow ambient "breathing" keyframe for the
  living-organism feel. **Respect `prefers-reduced-motion`.**
- **Depth:** consistent elevation ladder (bg → panel → glass card → modal →
  HUD overlay), each with more blur + brighter edge.

Light mode exists (tokens flip) but **dark is the designed default**, per brief.

---

## 2 · Tech decision (with rationale, not just a pick)

**Chosen: a self-contained web app — no build step, no CDN, no framework
runtime — served straight from the existing hub HTTP server.**

Why this and not React/Vite/Tailwind:
- The hub must run on a **2 GB UNO Q** and the demo promise is *"judge's phone
  needs no install, served from the hub, works at a venue with no internet"*
  — already proven for the current dashboard. A CDN-less, build-less app keeps
  that property intact. A React/Three bundle *can* be served statically too,
  but it adds a node toolchain, a build artifact to keep in sync, and CDN/font
  temptations that break at the venue.
- Repo rule: **stdlib in `hub/` core; heavier deps behind `hub/services/`.**
  The front-end stays dependency-free; anything heavy (a real LLM for AI chat)
  goes behind a `hub/services/` adapter, off by default.
- fable-mode: *delete complexity, stdlib before framework, thin slices.*

How we stay maintainable without a framework:
- **ES modules**, one file per screen/component, native `import`. No bundler.
- A tiny (~60-line) shared render/reactivity helper (`core/store.js`,
  `core/dom.js`) — a signal-ish store + a `h()` tag helper. Not React; just
  enough to avoid string-soup.
- **Hash router** (`#/home`, `#/ai`, `#/energy`, …) — instant, offline, no
  server routing needed.
- **Web standards for polish:** CSS `backdrop-filter`, CSS grid, View
  Transitions API (progressive), Web Animations, inline SVG, Canvas/WebGL only
  where a 2D/SVG version can't carry the idea.
- **3D twin:** ship the **isometric SVG/CSS "2.5D" living house first**
  (immediate, dependency-free, on-brand). A real Three.js twin is a later,
  *locally-vendored* enhancement — backlog, not blocker. (Matches the
  deliberate SVG-over-Three.js call already made in PROGRESS.md.)

**One small, tested hub change** is required: the current handler only serves
`/`, `/index.html`, `/ws`, `/health`, `/playback.json`. We extend it to serve a
static **`studio/`** directory (correct content-types + path-traversal guard).
This lands with a test (simulation-first applies to hub code).

---

## 3 · Folder structure

```
studio/                         # the app (served statically by the hub)
  index.html                    # shell: <domora-app> mount, imports app.js
  app.js                        # boot: router + live socket + shell chrome
  tokens.css                    # design tokens (single source of truth)
  base.css                      # reset, glass primitives, motion, layout
  core/
    store.js                    # reactive store (signals) + twin state model
    socket.js                   # /ws client: reconnect, snapshot/point/event
    twin.js                     # derived house model (rooms, health, systems)
    dom.js                      # h() tag helper + mount/patch
    router.js                   # hash router
    format.js                   # units, time, number formatting
  ui/                           # reusable components
    glass-card.js  stat-tile.js  meter.js  sparkline.js  chip.js
    health-dot.js  timeline.js  toast.js  command-bar.js
  screens/
    home.js                     # Phase 1 — the Live Home (hero)
    ai.js                       # Phase 2 — DOMORA AI chat
    energy.js  water.js  security.js  environment.js   # Phase 3
    room.js  appliance.js  sensor.js                   # Phase 4
    history.js  insights.js  settings.js               # Phase 5
  assets/                       # inline-friendly icons (SVG), no binaries/CDN
hub/services/
  api.py                        # + static studio/ serving (tested)
  ai_query.py                   # DOMORA AI grounded query engine (stdlib, tested)
  llm_adapter.py                # OPTIONAL cloud/local LLM behind an interface (off by default)
tests/
  test_studio_serving.py        # static serving + traversal guard
  test_ai_query.py              # grounded answers over a known twin state
```

Nothing here touches `hub/core`, `hub/agents/safety.py`, or the twin logic.

---

## 4 · Screen inventory & data bindings (build order)

Each screen names the **real points/topics** it binds to, so it is impossible
to build a fake one. Definition-of-done per phase is in §5.

### Phase 1 — **Live Home** (the hero; do this first)
- **Living house view**: isometric SVG house, each zone (Living, Kitchen,
  Utility/Water, Panel) tinted by a computed **health color** derived from its
  bound points (leak/dryrun/valve-suspect → red; slope warnings → yellow;
  learning → blue). Ambient "breathing" glow when nominal.
  - Bindings: `house.occupied`, `living.pir/radar`, `tank.line.flow_lpm`,
    `water_tank.level_pct`, `main_valve.valve_state`, `pump.*`,
    `virtual.water.leak_suspected`, `virtual.pump.dryrun_suspected`,
    `health.main_valve`, `health.pump`, `main_panel.power_w`.
- **Live vitals rail**: power now, water flow, tank %, occupancy, system
  health — glass stat tiles with sparklines fed from the point stream.
- **"The house is thinking" strip**: the latest `domora/plan → act → verify`
  chain as a live, animated one-liner (reuses cognition topics).
- Tapping a zone → Room page (Phase 4).

### Phase 2 — **DOMORA AI** (chat, grounded on the twin)
Conversational surface that answers *from the digital twin*, not a generic bot.
- Backend `hub/services/ai_query.py`: intent match → query twin/NILM/journal →
  templated NL answer + a small "evidence" payload the UI renders as a card.
  Deterministic, offline, **tested**. Handles the brief's example prompts:
  *"Why is today's power high?"* (→ NILM ledger deltas), *"How much water was
  used yesterday?"* (→ flow integral from journal), *"Which appliance is
  becoming unhealthy?"* (→ `health.*` + vibration/RUL when present),
  *"What changed while I was away?"* (→ event journal filtered by occupancy),
  *"Run a simulation" / "what if the pump stays on?"* (→ hand to sim scenario).
- `hub/services/llm_adapter.py`: optional. If an API key + network exist, the
  same grounded context is handed to a real LLM for free-form phrasing;
  **off by default**, never required, never in `hub/core`. (See
  [.claude/skills/claude-api] if wiring a Claude backend.)
- UI: chat transcript with streamed tokens, evidence cards, quick-prompt chips,
  and a mic affordance stubbed for future voice (voice itself = backlog).

### Phase 3 — **Dashboards** (Energy / Water / Security) — ✅ shipped, Environment deferred

- **Energy**: live power, NILM appliance breakdown (real ledger via GET
  /nilm), a this-session trend chart (journal-backed under `--playback`,
  live buffer otherwise). Built to the `dataviz` skill's method.
- **Water**: flow + tank level trend charts, valve/pump/leak/dry-run status,
  and the real incident list (cause→evidence→command→verify). The full
  scrub-back replay isn't duplicated here — the whole app already gets it
  for free when the server runs `--playback` (§0), so a second bespoke
  scrubber on this one page would be redundant, not additive.
- **Security**: occupancy + the real alert feed. Doors/windows/motion-beyond-
  radar/glass-break/smoke/gas have **no simulator or hardware publishing
  them yet** — the screen says so explicitly (a "not yet connected" list)
  rather than showing fabricated toggles.
- **Environment** (temp/humidity/pressure/lux/CO₂ via `env1/*`): **deferred,
  not built.** No scenario in `sim/` publishes these — the ENV node firmware
  exists and compiles but nothing simulates its readings, so this screen
  would have to be entirely fabricated or entirely empty. Revisit once
  `sim/` gains an environment simulator; until then it's intentionally
  absent from the nav rather than shipped as a placeholder.

### Phase 4 — **Detail pages** (Room / Appliance / Sensor) — ✅ shipped

- **Room**: the 3 real zones (living/utility/panel) — state, real points,
  health, and (utility only — the only zone anything ever acts on) the real
  action list. No 3D view, predictions, automation, or maintenance
  suggestions: none of that is computed anywhere in this codebase.
- **Appliance**: reads GET /nilm. Health score, RUL, failure-probability, and
  sound/vibration analysis are explicitly labelled **not computed** rather
  than estimated — this system has no per-appliance current/sound/vibration
  sensing to estimate them from, only aggregate-power disaggregation.
- **Sensor**: fully generic — works for *any* twin point key, since every
  point shares one shape (value/t/source/confidence). Live value, source,
  confidence, age (same staleness convention as hub/twin/state.py), trend,
  raw-values table. No calibration UI — nothing in the backend exposes
  calibration to control.

### Phase 5 — **Command, History, Insights, Settings** — ✅ shipped

- **Command bar** (`⌘K` / Ctrl+K): searches screens, rooms, and live twin
  points, then navigates. **Search-and-navigate only — does not issue
  commands.** This system's only actuation path is the planner dispatching
  through `hub/agents/safety.py`'s capability table; a manual "type a
  command, it runs" surface is a new safety-relevant capability, and
  CLAUDE.md requires an explicit invariant review for capability-table
  changes. That's the project owner's call, not something to add via a
  search box as a side effect of a UI pass.
- **History**: scrubs a real recorded journal (GET `/playback.json`),
  reconstructing twin + action state *at the scrubbed tick* — genuinely
  time-aware, not a full dump with a slider on top. Kept as its own local
  state, not the live store, so scrubbing the past can never corrupt what
  other tabs show as "now." Honest fallback when the server wasn't started
  with `--journal`/`--playback`. Search/filter/bookmarks not built — the
  scrubber plus the reconstructed points/action tables cover the
  useful case; add those only if a real workflow needs them.
- **AI Insights**: prioritized cards (critical/warning/info) derived from
  real signals already shown elsewhere — leak, dry-run, health-suspect,
  low tank, escalated/retrying actions, top NILM consumer. A different
  presentation of real state, not a new inference engine.
- **Settings**: House/Nodes read from the real house knowledge graph (new
  GET `/graph`, `hub/config/house.json`). AI lists the real supported
  intents. Users is honest: no accounts/roles/auth exist in this build.

### Backlog (spec Phase 2+, only if time — do **not** start without an ask)
Device-add wizard · visual automation builder · node map drag-drop · real
Three.js twin · offline voice/wake-word · user roles & login providers ·
installer/developer modes · multi-house.

---

## 5 · Phased delivery — definition of done per phase

Simulation-first: run the app against a live scenario and **watch it behave**,
not just compile. `python -m pytest tests/ -q` must stay green for any hub
change.

| Phase | Deliverable | Done when (observable) |
|---|---|---|
| **0 · Foundation** | tokens.css, base.css, app shell, router, live socket, store, static `studio/` serving + test | `python -m hub.services.api --scenario leak` serves `studio/` at `/`; the shell connects, shows a live status dot, and logs real snapshot/point/event frames from the running scenario. `test_studio_serving.py` green. |
| **1 · Live Home** | The hero screen, fully bound | Running `--scenario stuck`, the Utility/water zone turns **red** as the leak is suspected and the valve badge shows *suspect*; occupancy glow tracks `house.occupied`; the thinking-strip shows the real `plan→act→verify` chain. Screen-recorded as proof. |
| **2 · DOMORA AI** | `ai_query.py` + chat screen | With `--scenario energy`, asking *"why is power high?"* returns the real kettle/fridge/lamp breakdown from the NILM ledger with an evidence card. `test_ai_query.py` green (deterministic answers over a fixed twin). |
| **3 · Dashboards** | Energy/Water/Security/Environment | Each renders live points + at least one journal-backed historical chart, dark+light, mobile+desktop, no horizontal body scroll. |
| **4 · Detail pages** | Room / Appliance / Sensor | Drill-down from Home and dashboards works; each page bound to real points; honest RUL labelling. |
| **5 · Command/History/Insights/Settings** | ⌘K, history scrub, insights, settings | Command bar searches real entities and can replay an incident; insights cards derive from real state. |

Ship each phase end-to-end before widening. An MVP that runs beats an
architecture that doesn't.

---

## 6 · Verification & guardrails

- **Every UI claim is verified by running a scenario and observing** (record
  the screen). "It compiles / looks right" is not done.
- **Test the failure path**: the stuck-valve escalation and dry-run-stuck
  paths must render correctly, not just the happy leak-close.
- **Hub changes are tested** (`tests/`), stdlib-only, no `hub/core` deps added.
- **Safety unchanged**: `hub/agents/safety.py` stays ML-free; the UI issues
  only commands the capability table already allows. No new autonomous action.
- **Life-safety wording** ("supplements, never replaces certified detectors")
  stays visible, per repo rule and brief.
- **Accessibility**: honor `prefers-reduced-motion` and `prefers-color-scheme`;
  keyboard-navigable; sufficient contrast on glass.
- **Responsive**: desktop / tablet / mobile / touch, landscape + portrait;
  wide content scrolls inside its own container, never the body.
- **No AI attribution in commits; no pushing without an explicit ask.**

---

## 7 · Honest limits (state these; don't paper over them)

- "3D digital twin" ships first as **2.5D SVG/CSS**, not WebGL. Real 3D is a
  named backlog enhancement.
- "Voice mode / offline speech / wake word" is **not** in this plan (backlog).
  A mic affordance may appear as a stub.
- "DOMORA AI" is **grounded query first** (deterministic, offline). A real LLM
  is an optional, off-by-default adapter — not the default experience, and it
  needs network + a key it won't have at the venue.
- Predictions are the spec's honest **anomaly/trend** estimates, labelled as
  such — never presented as certainty.
- Login/roles, device wizard, automation builder, node map = backlog; the app
  runs single-user against the live hub until those land.

---

## 8 · First execution slice (what the next session does)

1. **Phase 0**, in order: `tokens.css` → `base.css` → `core/{store,socket,
   dom,router}.js` → `studio/index.html` + `app.js` shell → extend
   `hub/services/api.py` to serve `studio/` (+ `test_studio_serving.py`).
   **DoD:** the shell connects to a live `--scenario leak` run and shows real
   frames. Run it, watch it, record it.
2. **Phase 1 — Live Home**, then stop and show it before widening.

> Track this as the **DOMORA Studio** front-end line. It extends (does not
> replace) the week-5 dashboard already in `dashboard/`. PLAN.md's competition
> scope contract is untouched; this is the owner-prioritized product surface.

---

## 9 · DOMORA Mobile (Flutter) — full Studio parity, native client

A native Android/iOS app (`mobile/`, standard `flutter create` layout) that
is a **client of the exact same hub** Studio already talks to — `/ws`, `/ai`,
`/nilm`, `/graph`, `/history`, `/playback.json`. No new backend surface for
parity; the whole data contract in §0 already applies unchanged. Scope:
full parity with the web Studio (owner's explicit choice over a thinner
companion), built in the same phase order, each phase verified against the
real running hub before the next starts.

**Key difference from the web app, and why it matters:** Studio is *served
by* the hub, so relative URLs just work. A Flutter app is a separate OS
process (often a separate device) — it needs to be told where the hub is.
A **Connect screen** (host:port, defaults to `10.0.2.2:8080` on the Android
emulator — the emulator's alias for the host machine's `localhost` — editable
for a real device on the LAN) persists the URL via `shared_preferences` and
gates the rest of the app.

**Packages** (kept to the official/minimal set — same "delete complexity"
instinct as Studio's zero-dependency web build, just not zero-dependency-able
in Flutter): `web_socket_channel` (the `/ws` client), `http` (GET/POST to
everything else), `shared_preferences` (persist the hub URL). No charting
library — custom `CustomPainter` line/bar charts reusing the **exact
validated hex values** already in `studio/tokens.css` (categorical
`#3987e5/#d95926/#199e70` dark, `#2a78d6/#eb6834/#1baf7a` light; state
`#3ee08a/#f5b955/#ff5d6c/#6c8dff/#c084fc`) as Dart constants — the palette
was already run through the `dataviz` skill's validator once; it doesn't
get re-derived, just ported. No state-management package — `ChangeNotifier`
+ `ListenableBuilder` (Flutter SDK) mirrors `studio/core/store.js`'s shape
(points map, actions map, feed, connection status) directly.

**Structure:**
```
mobile/
  lib/
    main.dart
    theme/tokens.dart          # ported color/spacing/radius constants
    core/
      store.dart                # ChangeNotifier mirroring core/store.js
      hub_client.dart            # WebSocket + http client, connect-screen aware
      twin.dart                  # derive*() pure functions, ported from core/twin.js
      insights.dart              # ported from core/insights.js
    widgets/
      glass_card.dart  stat_tile.dart  health_dot.dart  chip.dart
      line_chart.dart  bar_chart.dart  # CustomPainter, same mark specs as ui/*.js
    screens/
      connect.dart  home.dart  ai.dart  energy.dart  water.dart  security.dart
      room.dart  appliance.dart  sensor.dart
      history.dart  insights.dart  settings.dart
  test/
    # fed the SAME captured real /ws frames already saved during the Studio
    # build (stuck_frames.json / energy_frames.json) — real data, not new
    # hand-written fixtures, same discipline as Studio's headless verification
```

**Navigation:** `BottomNavigationBar` for Home/AI/Energy/Water/Security
(Studio's top tabs); an app-bar menu for History/Insights/Settings;
`Navigator.push` for Room/Appliance/Sensor detail pages. A search icon opens
a search screen (mobile's equivalent of ⌘K) — **search-and-navigate only,
same as Studio's command bar, for the same reason:** this system's only
actuation path is the planner through `hub/agents/safety.py`'s capability
table, and CLAUDE.md requires an explicit invariant review before that
table changes. A mobile search box doesn't get to add actuation as a side
effect either.

**Phase order** (same reasoning as §5 — thin vertical slices, verify each
against the live hub before widening):

| Phase | Deliverable | Done when |
|---|---|---|
| A | ✅ Scaffold, theme, hub_client (WS+HTTP), store, Connect screen, Home | ✅ Running app connects to a live `--scenario stuck` hub and the Home screen shows the real leak/valve-suspect state, verified by actually running the app (not just `flutter analyze`) |
| B | ✅ AI chat | ✅ Real grounded answers from POST /ai render in a chat UI |
| C | ✅ Energy/Water/Security | ✅ Real charts (CustomPainter line + widget-composed bars, ported mark specs) + real alerts |
| D | ✅ Room/Appliance/Sensor | ✅ Same click-through drill-down as Studio (Home zone → Room → Sensor; Energy bar → Appliance) |
| E | ✅ History/Insights/Settings + search | ✅ Playback scrub (verified time-aware), real insight cards, real /graph data |

**All five phases shipped.** 47 tests + `flutter analyze` clean; verified live
against real running hubs (real WebSocket + real HTTP), and the compiled app
was screenshotted mid-incident rendering the real cognitive chain
(`leak:main_line → line flow falls below 0.1 L/min · pending` at t=43).

**Honest limits carried over unchanged from §7:** no manual actuation, no
LLM by default, no 3D twin, no voice, no login/roles. iOS is unbuildable
without a Mac/Xcode from this environment — Android + web (`flutter run -d
chrome`, useful for fast iteration) are the targets actually exercised here.
