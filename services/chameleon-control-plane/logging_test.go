package controlplane

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

func TestStructuredLoggerEmitsCorrelationFields(t *testing.T) {
	var buf bytes.Buffer
	logger := NewStructuredLogger(&buf, "chameleon-control-plane")
	logger.Info("topology_commit",
		"correlation_id", "run_fixture",
		"action", "SubmitTopologyRevision",
		"actor_hash", HashIdentity("DEMO-OPERATOR"),
	)

	line := strings.TrimSpace(buf.String())
	var payload map[string]any
	if err := json.Unmarshal([]byte(line), &payload); err != nil {
		t.Fatalf("expected JSON log line, got %q: %v", line, err)
	}
	if payload["service"] != "chameleon-control-plane" {
		t.Fatalf("unexpected service: %v", payload["service"])
	}
	if payload["correlation_id"] != "run_fixture" {
		t.Fatalf("unexpected correlation_id: %v", payload["correlation_id"])
	}
	if payload["action"] != "SubmitTopologyRevision" {
		t.Fatalf("unexpected action: %v", payload["action"])
	}
	if payload["msg"] != "topology_commit" {
		t.Fatalf("unexpected msg: %v", payload["msg"])
	}
	actorHash, _ := payload["actor_hash"].(string)
	if actorHash == "" || strings.Contains(actorHash, "DEMO-OPERATOR") {
		t.Fatalf("actor_hash must be a non-empty digest, got %q", actorHash)
	}
}

func TestStructuredLoggerDoesNotReplaceAuditSink(t *testing.T) {
	var buf bytes.Buffer
	logger := NewStructuredLogger(&buf, "chameleon-control-plane")
	_, adapter, sink := newAuditedCluster(t)

	logger.Info("pre_commit", "correlation_id", "run_log", "action", "CommitTopology")
	_, err := adapter.CommitTopology(TopologyCommitRequest{
		CorrelationID: "run_log",
		Actor:         "DEMO-OPERATOR",
		Role:          "operator",
		Payload:       []byte(`{"topology":"fixture"}`),
	})
	if err != nil {
		t.Fatalf("commit: %v", err)
	}
	if len(sink.Events()) < 2 {
		t.Fatalf("expected canonical audit events, got %d", len(sink.Events()))
	}
	if !strings.Contains(buf.String(), `"msg":"pre_commit"`) {
		t.Fatalf("expected process log without consuming audit sink: %s", buf.String())
	}
}
