# CHAMELEON structured logging

Process logs use Go `log/slog` JSON via `NewStructuredLogger`. They are for
operator observability only.

Required conventions:

- Include `service`, `correlation_id`, and `action` on control-plane events.
- Hash actor identity with `HashIdentity`; never log raw credentials.
- Persist durable history only through `AuditEventSink` / the FastAPI bridge.
- Do not invent latency, failover, or operational outcome claims in log text.

Stdout JSON is compatible with CloudWatch, Datadog, or Splunk collectors once
those sinks are configured by operations. Until then, local stdout is the
pilot sink.
