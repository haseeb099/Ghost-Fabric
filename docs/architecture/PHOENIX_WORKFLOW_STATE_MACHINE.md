# PHOENIX Workflow State Machine — GF-40

**Status:** Integrated simulation implementation; external delivery review pending  
**Scope:** Deterministic, reversible simulation workflows  
**Non-goal:** Autonomous or external recovery execution

## States

```text
alert → approval → execution → verify → restored
                               └→ rollback → failed
```

| State | Meaning | Entry guard |
|---|---|---|
| `alert` | A reversible recovery option was identified | Fixture/simulation event |
| `approval` | Operator review is required | Named recovery option |
| `execution` | A simulated action is recorded | Explicit `operator` approval |
| `verify` | Simulated action awaits outcome verification | Simulated execution record |
| `restored` | Verification passed | Verification result |
| `rollback` | Verification failed; reversal required | Failed verification |
| `failed` | Rollback completed; manual review continues | Rollback completion |

## Safety and audit rules

- Only the `operator` role can move a workflow from `approval` to `execution`.
- The current fixture approval threshold is one authenticated `operator`;
  `approval_policy` is returned with the read model so a reviewed multi-party
  policy can be introduced without changing the execution boundary.
- Execution is a recorded simulation step, never an external side effect.
- Every transition includes workflow/correlation IDs, prior and next state,
  actor, and reason before it is emitted to the canonical audit stream.
- A failed verification cannot become `restored`; rollback is mandatory.
- No CHAMELEON state, AI response, or client UI event substitutes for approval.

## Current implementation

`backend/app/phoenix_workflow.py` supplies the deterministic state machine and
`/api/v1/phoenix/approve` maps an operator-approved recovery option through
the simulated transitions, persisting each one as a canonical
`EventEnvelope`. `/api/v1/phoenix/rollback` supports an operator-triggered,
reversible simulated rollback after `restored`.

`backend/app/phoenix_notifications.py` records notification intent in the
same persisted scenario snapshot. Its `simulation-outbox` channel does no
network I/O: PagerDuty, Slack, or any other delivery adapter remains blocked
until security and operations approve its credentials, payload contract,
retries, and failure behavior.

## Review gates before external delivery

1. Security confirms role/identity and approval evidence requirements.
2. Operations approves option templates, verification evidence, and rollback
   criteria for each simulated workflow.
3. Product/safety confirms each action remains reversible and simulation-only.
