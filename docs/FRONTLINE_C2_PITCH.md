# Ghost Fabric — EDGE C2 Continuum (frontline submission pack)

Use this document for hackathon/judging submissions. Every claim below is
demonstrable in the console. Nothing here promises detection, targeting, or
weapons capability.

## One-liner

A simulation-first contested-communications console that keeps a frontline
unit's command and control coherent when its coordination relay is jammed or
destroyed — coordinator handoff, partition awareness, human-approved link
restore, and a hash-chained decision record.

## Problem

Electronic warfare and precision attrition attack command and control first. When
a relay drops, a unit does not only lose bandwidth. It loses **who is still
reachable**, **who coordinates the mesh**, and **whether a restored link is safe
to trust**. Afterwards there is rarely a clean record of who authorized what
under fire. Commercial network-monitoring tools assume peacetime uptime and
cannot rehearse hostile degradation with approval-bound recovery.

## What the console does

| Layer | Operator question it answers |
|---|---|
| **CHAMELEON** | Who is reachable, who coordinates now, are we one mesh or split into partitions, which routes survive |
| **PROPHET** | Is link health degrading, with what uncertainty, and are enough independent signals confirming |
| **MIRROR** | Which declared courses of action exist, compared side by side, for a human to choose |
| **PHOENIX** | May we restore a critical path — approve, execute, verify, or roll back |
| **Audit** | Who decided what, when, under which correlation ID, with chained event hashes |

## Demo script (about 2 minutes)

1. Baseline: mesh nominal, coordinating node online, no partitions.
2. `SIMULATE RELAY LOSS` — coordination relay lost to jamming or attrition.
   Coordinator handoff occurs and routes recompute deterministically.
3. Point at `PARTITIONS` and `COORDINATOR REACH` — the unit knows whether it is
   still connected or operating split.
4. Advance the synthetic feed — PROPHET shows degradation confidence with an
   uncertainty interval. A single-signal excursion does not become an alert.
5. Select a MIRROR course of action — declared options compared, human chooses,
   nothing executes on its own.
6. `HUMAN APPROVAL REQUIRED` — PHOENIX approve, execute, verify. Failed
   verification rolls back rather than reporting success.
7. `EXPORT` the audit stream — correlation ID, chained hashes, fixture identity.

Optional civil segment: the CITIZEN layer shows the same discipline applied to
warning civilians when alert channels are jammed (SMS to community FM to offline
mesh and sirens, human-approved advisory, nothing transmitted).

## Claim boundaries — state these before being asked

- No threat detection, tracking, geolocation, trajectory, or launch origin.
- No targeting output, coordinates, interception, or weapons assignment.
- No autonomous action: every consequential transition needs operator approval.
- All data is synthetic and fictional; timings and lead values are labeled
  fixtures, never measured or promised performance.
- This keeps the **friendly** network coherent. Detection and engagement belong
  to separate, dedicated systems.

## Why the boundary is a strength

Warning and recovery decisions made on one unverified signal destroy operator
trust. The guardrails here — multi-signal confirmation, declared courses of
action, human approval, verify-or-rollback, and non-repudiable audit — are the
product, not a limitation.
