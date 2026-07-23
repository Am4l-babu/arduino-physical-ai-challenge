# Instructions for ALL AI agents and models working in this repo

**Mandatory first step, before reading code or making any change:**
read [.claude/skills/fable-mode/SKILL.md](.claude/skills/fable-mode/SKILL.md)
and follow it as binding instructions. It defines the working contract here —
observe → think → plan → act → verify → report — including hard rules
(never claim unverified success, no destructive actions without an explicit
ask, no AI attribution in commits) and the end-of-turn checklist.

Then read [CLAUDE.md](CLAUDE.md) for repo-specific rules and
[PROGRESS.md](PROGRESS.md) for current state.

Quick verification contract for this codebase:

```bash
python -m pytest tests/ -q          # must be green before any "it works" claim
python -m hub.main --scenario leak  # the closed loop, end to end
```

Note: [docs/AGENTS.md](docs/AGENTS.md) is a different document — it describes
DOMORA's *runtime* agents (the Python cognitive loop), not rules for you.
