# PROPHET Model Architecture — GF-35

**Status:** Design accepted for simulation pilot  
**Scope:** Explainable, non-authoritative scoring over labeled synthetic fixtures  
**Non-goals:** Production ML accuracy claims, live customer-data training, autonomous alerting

## Decision

Ghost Fabric ships a **fixture-calibrated scoring pipeline** as the PROPHET model for the pilot. Live LSTM / isolation-forest training is deferred until an ML owner, labeled incident corpus, and evaluation gate exist.

| Layer | Choice | Rationale |
|---|---|---|
| Signal catalog | Bandwidth, latency, mesh density, spectrum occupancy, logistics tempo, error rate (fixture-labeled) | Matches demo evidence UI; expandable without changing authority |
| Scoring | Deterministic weighted scoring + labeled false-positive guardrails | Reproducible, reviewable, no invented accuracy |
| Explainability | Contribution weights + confidence interval from fixture calibration | SHAP-equivalent narrative without claiming model fidelity |
| Feature store | In-process fixture windows (`prophet-telemetry-v1.json`) | Kafka/Redis deferred (GF-37) |
| Fallback | `ProviderNeutralAdapter` fixture mode | Demo remains usable if any external model API is absent |
| Authority | Review-only | Never authorizes PHOENIX recovery or mesh failover |

## Signal catalog (pilot)

| ID | Source | Unit | Role |
|---|---|---|---|
| `spectrum` | Synthetic occupancy | % | Contributing signal |
| `logistics` | Synthetic tempo index | idx | Contributing signal |
| `network` | Mesh message density | idx | Contributing signal |
| Fixture extras | `prophet-telemetry-v1` samples | mixed | Baseline noise, partial quality, labeled FP |

## Training / evaluation boundary

1. **Pilot:** scores are computed from versioned fixtures with seed `4107`.
2. **Future offline train:** labeled incident datasets only; never operational targeting data.
3. **Promotion gate:** true-positive / false-positive metrics must be measured on held-out fixtures and labeled as experimental until an ML lead signs the eval report.
4. **Inference budget (aspirational):** ONNX CPU path is a future option; do not claim `<50ms` until measured in an approved environment.

## False-positive controls

- Single-signal excursions do not raise `warning`.
- Partial-quality / null samples are preserved, not imputed into alerts.
- UI and API expose labeled fixture context and confidence intervals.

## Related artifacts

- `backend/app/fixtures/prophet-telemetry-v1.json`
- `backend/app/ai_adapter.py`
- `/api/v1/prophet/scores`, `/explain`, `/telemetry`
- Safety rules: PROPHET is schema-validated explanation only

## Deferred work

- GF-36 baseline LSTM training on real customer data
- GF-37 Kafka → Redis feature store
- External model registry and SHAP production pipeline
