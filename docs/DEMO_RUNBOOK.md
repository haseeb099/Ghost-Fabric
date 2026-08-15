# Ghost Fabric two-minute demo

## Ground rules

- Describe Ghost Fabric as a **fictional, simulation-first resilience demonstrator**.
- Say *synthetic fixture*, *simulated workflow recovery*, and *operator approval*.
- Describe the Eastern Europe context as abstracted public-reporting inspiration only; all nodes, coordinates, values, and timing are invented and generalized.
- Do not claim real-world prediction, targeting, autonomous action, or live operational awareness.
- Follow the on-screen **demo phase banner**; it is guided pacing only and does not authorize action.

## Pre-flight (two minutes before)

1. Start the backend and frontend, close the first-run operator guide, then confirm `API LIVE`.
2. Reset the scenario; verify event sequence `#001`, `100% MESH`, `NORTHSTAR` coordinator, and phase `Calm baseline`.
3. Keep speed at `1×` until the live demo begins.
4. Confirm the map says `FICTIONAL EXERCISE` and public weather is only environmental context.

## Timed script — 120 seconds

| Time | Operator action | Spoken line | Evidence on screen |
|---:|---|---|---|
| 0–12s | Leave baseline visible | “Ghost Fabric is a fictional training simulation for keeping a distributed civil resilience network usable when a relay fails. The exercise is informed by generalized public reporting, never operational data.” | Safety ribbon; public map labeled fictional; phase banner |
| 12–28s | Point to CHAMELEON graph bar | “This is not a single command center. The mesh exposes connectivity, alternate routes, coordinator reach, and measured recomputation time.” | Graph components, active links, solve time |
| 28–46s | Select `4×`, then advance feed once | “PROPHET scores only labeled synthetic evidence. It shows the uncertainty interval, thresholds, virtual-time countdown, and confirming signals.” | Confidence, countdown, 55/80 thresholds, evidence block |
| 46–58s | Point to false-positive guardrail | “A single-signal excursion does not become an alert. The fixture preserves missing data and requires multi-signal confirmation.” | Guardrail text; partial-quality count |
| 58–74s | Click `INJECT NODE LOSS` | “When the coordinator relay is lost, the graph recomputes deterministically and hands coordination to an available recovery node.” | Coordinator handoff animation; routing telemetry; audit event |
| 74–88s | Select `Civil bridge review` | “MIRROR compares declared tabletop branches from an approved fixture catalog. A human must choose; nothing executes.” | Branch cards; `mirror.*` audit events |
| 88–104s | Click `HUMAN APPROVAL REQUIRED` | “PHOENIX records approval, simulated execution, and verification as separate audited transitions. There is no autonomous restore.” | Workflow stepper; restored state |
| 104–120s | Filter audit to PHOENIX, then export | “Every state transition has a correlation ID and chained hash. The export includes the fixture identity and complete append-only record.” | Audit filter; export control; event hashes |

## Optional CITIZEN segment (add 40 seconds)

Use this when the audience cares about reaching civilians rather than restoring links.

| Operator action | Spoken line | Evidence on screen |
|---|---|---|
| Click `ADD DISTRICT DETECTION` twice | “Five thousand consenting phones are modeled as anonymous district counts. Two districts is a rumour, not a warning, so the advisory stays locked.” | `2/3 DISTRICTS`, state `CORROBORATING`, advisory button disabled |
| Click it until `CONFIRMED` | “Corroboration across independent districts is what earns confidence. This is evidence for a human, not a forecast, and it estimates nothing about any source.” | Confidence ring; `CONFIRMED`; guardrail text |
| Click `LOSE 30% SENSORS` | “Lose thirty percent of the grid and it still works, because no single device matters.” | Grid survival `70%`; still confirmed |
| Click `JAM ACTIVE CHANNEL` | “Jam SMS and the advisory falls back to community FM, then to an offline mesh and siren relay.” | Channel ladder: SMS jammed, FM in use |
| Click `APPROVE CIVILIAN ADVISORY` | “Only an operator can advise, and the advisory is recorded as simulation-only. Nothing is transmitted and nothing is targeted.” | `ADVISORY RECORDED`; `citizen.advisory_approved` audit event |

Say plainly if asked: the four-minute lead time is a labeled fixture value, and
the system never computes trajectories, source locations, coordinates, or any
targeting output.

## Claims ledger

| Claim | Evidence |
|---|---|
| Fixed scenario behavior | `backend/app/fixtures/broken-signal-v1.json`, seed `4107` |
| Forecast is synthetic and calibrated | `backend/app/fixtures/prophet-telemetry-v1.json`; PROPHET evidence UI |
| Tabletop branches are fixture-only | `backend/app/fixtures/mirror-fictional-network-partition.yaml`; `/mirror/catalog` |
| Coordinator/routing recovery is deterministic | Backend routing tests and chained audit events |
| Recovery needs approval and stepped verification | PHOENIX approve → execute → verify controls and workflow events |
| Audit is traceable | `/api/v1/audit/export` includes fixture metadata, correlation ID, hashes, and export hash |
| Citizen grid is anonymous and non-targeting | `backend/app/citizen_grid.py`; `backend/tests/test_citizen_grid.py` prohibited-term and guardrail tests |
| Advisory needs multi-district corroboration plus a human | `/citizen/warn` returns 409 below 3 districts / 55%; `citizen.advisory_approved` records `effect: simulation-only` |

## Recovery line

If a service is unavailable: “The console has a deterministic fixture fallback. This demo uses no live AI decision authority and no operational data.”

## Rehearsal evidence

Log three timed takes and reviewer feedback in `docs/DEMO_REHEARSAL_LOG.md`. Mark a rehearsal Ready only when all three are ≤120s and the reviewer confirms the safety phrasing.
