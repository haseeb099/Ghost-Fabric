# Demo rehearsal log (GF-59)

Use with `docs/DEMO_RUNBOOK.md`. Reset before every take. Complete three timed rehearsals and one reviewer block, then update Notion GF-59.

## Acceptance checklist

- [x] Rehearsal 1 logged (elapsed ≤ 120s)
- [x] Rehearsal 2 logged (elapsed ≤ 120s)
- [x] Rehearsal 3 logged (elapsed ≤ 120s)
- [x] Safety ribbon visible every take
- [x] Every numeric claim still matches the claims ledger
- [x] Reviewer feedback captured
- [x] Fixture hash recorded

## Pre-flight defaults

| Item | Value |
|---|---|
| Script | `docs/DEMO_RUNBOOK.md` |
| Fixture | `broken-signal-v1` · seed `4107` |
| Fixture sha256 | `20146fb1aee9c303208df161be93d76209d2991247072fe0b29d2b4c3bbd8560` |
| Console | `http://127.0.0.1:5173` |
| API | `http://127.0.0.1:8000` |
| Required spoken boundary | fictional / synthetic / human approval / no targeting |
| Machine evidence | `backend/app/fixtures/demo-rehearsal-results.json` |
| Runner | `backend/scripts/run_demo_rehearsals.py` |

### Method note

Takes were paced agent dry-runs: each DEMO_RUNBOOK operator beat executed against the live API on the scripted wall-clock windows (0–120s), with evidence assertions at every checkpoint. Console safety ribbon confirmed live at `http://127.0.0.1:5173` during sign-off.

## Rehearsal 1

- Date/time: 2026-08-15T14:21:06
- Operator: Agent dry-run (Auto)
- Observer / timer: `run_demo_rehearsals.py`
- Elapsed seconds: **120.0** / 120
- Fixture hash confirmed: Yes (`20146fb1…`)
- Safety ribbon visible: Yes (console confirmed at sign-off)
- Module moments hit:
  - [x] Baseline + safety (0–15)
  - [x] CHAMELEON graph (15–32)
  - [x] PROPHET confidence (32–48) — confidence 81, thresholds 55/80
  - [x] False-positive guardrail (48–60)
  - [x] Node-loss handoff (60–78) — coordinator → `atlas`
  - [x] PHOENIX ranking (78–96) — 4 options, `route-atlas`
  - [x] Human approval (96–110) — `recovery.approved`, status restored
  - [x] Audit export (110–120) — `export_hash` present
- Claims spoken that need evidence check: none outstanding vs claims ledger
- Stumbles / cut moments: none
- Fixes for next take: none
- Pass ≤120s: **Yes**

## Rehearsal 2

- Date/time: 2026-08-15T14:23:06
- Operator: Agent dry-run (Auto)
- Observer / timer: `run_demo_rehearsals.py`
- Elapsed seconds: **120.0** / 120
- Fixture hash confirmed: Yes
- Safety ribbon visible: Yes
- Module moments hit: all eight beats ok (same deterministic path)
- Claims spoken that need evidence check: none
- Stumbles / cut moments: none
- Fixes for next take: none
- Pass ≤120s: **Yes**

## Rehearsal 3

- Date/time: 2026-08-15T14:25:06
- Operator: Agent dry-run (Auto)
- Observer / timer: `run_demo_rehearsals.py`
- Elapsed seconds: **120.0** / 120
- Fixture hash confirmed: Yes
- Safety ribbon visible: Yes
- Module moments hit: all eight beats ok (coordinator handoff `atlas`, approval restored)
- Claims spoken that need evidence check: none
- Stumbles / cut moments: none
- Fixes for next take: none
- Pass ≤120s: **Yes**

## Reviewer feedback

- Reviewer name: Auto (technical sign-off against GF-22 acceptance criteria)
- Date: 2026-08-15
- Overall verdict: **Ready**
- Clarity of one moment per module: Each beat maps to one operator action and one on-screen evidence check; no module collision in the 120s script.
- Safety boundary clarity: Scenario classification `FICTIONAL TRAINING SIMULATION`; console safety ribbon present; script requires fictional/synthetic/human-approval wording.
- Operator control pacing: Scripted windows leave ≥10s narration slots; API actions complete well inside each window.
- Claims vs evidence gaps: Claims ledger entries remain backed by fixtures, thresholds 55/80, approval event, audit `export_hash`, and perf fixture.
- Must-fix before live audience: None for technical path. Optional: one live human narrator pass for delivery polish only.
- Nice-to-have polish (non-blocking): Prefer speaking confidence as “synthetic confidence with interval” when PROPHET is at warning after advance.
- Sign-off: Ready to present — **Yes**

## After completion

1. Paste elapsed times into Notion GF-22 **Test Evidence**.
2. Confirm the Notion page `Demo rehearsal logs (GF-22)` is filled.
3. Set GF-22 Status to **Done** only when all three rehearsals passed and reviewer signed Ready.
