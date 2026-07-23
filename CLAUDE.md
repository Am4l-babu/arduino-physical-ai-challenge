# Claude instructions — DOMORA

**FIRST, before anything else:** load and follow
[.claude/skills/fable-mode/SKILL.md](.claude/skills/fable-mode/SKILL.md) —
the working contract (observe → think → plan → act → verify → report) that
every AI model or agent in this repo operates under. If your tooling doesn't
auto-load skills, read that file with your file-reading tool now and treat
it as binding instructions. The rules below are repo-specific additions to it.

Solo project (no assignee tracking). Working rules for any AI-assisted session:

- Read `PROGRESS.md` first; update it when starting/finishing a component.
  `PLAN.md` is a scope contract — new ideas go to the spec's Phase 2 lists,
  not into the plan.
- **Simulation-first is non-negotiable:** any new behavior lands in `sim/` +
  a scenario test in `tests/` (success AND failure path) before hardware.
  Run `python -m pytest tests/ -q` before claiming anything works.
- The expectation contract is the architecture: never add an autonomous
  action without a falsifiable Expectation and a named independent sensor
  that verifies it. If it can't be verified, it must not be autonomous.
- `hub/agents/safety.py` stays ML-free and dumb. Additions to the capability
  table require a stated invariant review in the PR/commit message.
- Life-safety claims: DOMORA supplements, never replaces, certified
  detectors. Keep that wording in all docs and UI.
- Python: stdlib-only in `hub/` core (it must run on a 2 GB UNO Q);
  heavier deps live behind `hub/services/` adapters.
- Git: no AI attribution in commits. Don't push to any remote without an
  explicit ask.
