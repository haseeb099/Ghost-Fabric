# MIRROR Tabletop Scenario DSL — GF-38

**Status:** Fixture-only design  
**Scope:** Deterministic, doctrine-level tabletop branch comparison  
**Non-goal:** Individual profiling, targeting, influence operations, or
external action execution

## DSL

Scenarios live under `backend/app/fixtures/` as YAML and require:

- `classification: synthetic-training`;
- a fixed seed;
- 1–12 decision points with 2–4 declared branches each; and
- descriptive conditions/outcomes only.

The parser rejects undeclared fields and prohibited decision content. YAML is
loaded with `safe_load`; it has no executable-action field or callback model.

## Approved fixture catalog

The initial eight synthetic scenarios are:

1. regional communications partition;
2. DNS resolution drift;
3. inter-region route leak;
4. relay certificate expiry;
5. telemetry evidence gap;
6. regional latency spike;
7. node identity mismatch; and
8. canonical audit-store outage.

`load_mirror_catalog` loads them in stable filename order and rejects duplicate
scenario IDs. Tests validate every fixture and replay each scenario twice with
identical choices.

## Replay contract

`replay_tabletop` accepts one declared branch for every decision point and
returns the ordered, deterministic fixture trace. Missing or unknown choices
are rejected. It does not mutate systems, issue commands, or decide a
recovery.

`backend/app/mirror_engine.py` supplies a stepwise event loop: it presents a
declared decision, accepts a declared human selection, records its fixture
outcome, and completes only after every decision point is resolved. The same
fixture and selections replay identically; the current test runs 100 repeats.
Every emitted event advances a configurable positive virtual-time step
(default 1,000 ms), so replay timing is deterministic and independent of wall
clock time.

`backend/app/mirror_audit.py` maps the resulting declared trace to the existing
canonical `EventEnvelope`/`AuditStore` flow as `mirror.*` events. Each payload
is marked `tabletop-fixture-only` and includes the virtual timestamp; the
adapter emits no command or side effect.

The console displays three fixture branches side by side with explicit
`COMPARE`/`SELECTED` states. Selecting a card remains an operator decision and
creates the existing canonical branch-selection audit event.

Time-travel debugging is event-sourced: select any canonical MIRROR event
sequence and rebuild the read-only trace prefix through that sequence. A
rewound view never mutates the active scenario or resumes execution by itself.

## Safety review

Before adding a fixture, verify it:

1. uses only synthetic/approved training material;
2. contains no person-level attributes, real targets, weapon content, or
   influence-operation logic;
3. describes choices as bounded tabletop assumptions; and
4. labels every outcome as fixture-only, not an operational prediction.

The automated catalog review enforces the synthetic classification, bounded
branch counts, strict schema, prohibited-content filter, unique IDs, and
deterministic replay for every fixture.
