package controlplane

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"log/slog"
)

// NewStructuredLogger returns a JSON slog logger for process observability.
// It never replaces AuditEventSink / canonical EventEnvelope persistence.
func NewStructuredLogger(w io.Writer, service string) *slog.Logger {
	handler := slog.NewJSONHandler(w, &slog.HandlerOptions{Level: slog.LevelInfo})
	return slog.New(handler).With("service", service)
}

// HashIdentity returns a short non-reversible handle for log fields.
// Callers must never pass recovery commands or raw credentials into logs.
func HashIdentity(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])[:16]
}
