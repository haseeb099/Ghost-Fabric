# PHOENIX Pre-Approved Automation Policy — GF-42

**Status:** Simulation catalog shipped; auto-execute forbidden  
**Fixture:** `backend/app/fixtures/phoenix-preapproved-templates-v1.json`

## Decision

Expose a **read-only** catalog of P3-style templates so operators can see which
situations *could* be pre-scoped. Matching a template **never** advances the
workflow. An authenticated operator must still call approve → execute → verify.

## Why not auto-approve

Safety rules require human approval at every consequential recovery decision.
Silent auto-execution would violate the PHOENIX audit model and demo claims.

## API surface

`phoenix.pre_approved` on the scenario snapshot / workflow read model:

- `templates[]` with `policy_id`, `when`, `bounded_effects`
- `auto_execute: false` always
- `requires_operator_confirm: true` on every template (enforced at load)

## Metrics (future)

Automation rate and false-alarm recovery time remain undefined until a reviewed
dry-run mode exists. Do not publish rates from this catalog alone.
