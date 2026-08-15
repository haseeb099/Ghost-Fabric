# Value prop — Financial / market infrastructure (GF-24)

## Problem

Operational resilience programs need proof of control: who approved what, when, under which correlation ID — especially when analytics are involved.

## Solution

Ghost Fabric binds **human approval** to recovery workflows, records **subject/role** on durable events, and exports a **hash-chained audit** suitable for rehearsal evidence packs.

## Why us (now)

- Append-only audit with `export_hash`.  
- Non-authoritative AI explanations with fixture fallback (`mode: fixture|provider`).  
- Idempotent mutations (`X-Command-ID`).  
- Versioned REST (`/api/v1`) and committed OpenAPI contract.

## Pilot ask

Controlled rehearsal environment only — synthetic telemetry, no production market data. Success = complete audit chain for fail → approve → export in under the agreed script time.

## Compliance note

FedRAMP / SOC 2 / NERC readiness are **roadmap items**, not current certifications. Do not imply certified status in outbound materials.
