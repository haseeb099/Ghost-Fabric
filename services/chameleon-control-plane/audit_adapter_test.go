package controlplane

import (
	"errors"
	"testing"
)

func newAuditedCluster(t *testing.T) (*Cluster, *TopologyAuditAdapter, *MemoryAuditEventSink) {
	t.Helper()
	cluster := newElectedCluster(t)
	sink := &MemoryAuditEventSink{}
	adapter, err := NewTopologyAuditAdapter(cluster, sink)
	if err != nil {
		t.Fatal(err)
	}
	return cluster, adapter, sink
}

func TestTopologyAdapterPersistsCanonicalEventsAroundQuorumCommit(t *testing.T) {
	_, adapter, sink := newAuditedCluster(t)
	entry, err := adapter.CommitTopology(TopologyCommitRequest{
		CorrelationID:  "run-audit-contract",
		Actor:          "DEMO-OPERATOR",
		Role:           "operator",
		ScenarioTimeMs: 5000,
		Payload:        []byte(`{"revision":"audit-contract"}`),
	})
	if err != nil {
		t.Fatal(err)
	}

	events := sink.Events()
	if len(events) != 2 {
		t.Fatalf("event count = %d, want 2", len(events))
	}
	if events[0].Type != "chameleon.topology_revision_requested" {
		t.Fatalf("first event = %q", events[0].Type)
	}
	if events[1].Type != "chameleon.topology_revision_committed" {
		t.Fatalf("second event = %q", events[1].Type)
	}
	if entry.AuditEventRef != events[0].EventID {
		t.Fatalf("entry audit reference = %q, want %q", entry.AuditEventRef, events[0].EventID)
	}
	if events[1].Payload["audit_event_ref"] != events[0].EventID {
		t.Fatalf("committed payload = %#v", events[1].Payload)
	}
	if events[1].PreviousHash != events[0].EventHash {
		t.Fatal("canonical audit chain is discontinuous")
	}
	if events[0].Actor != "DEMO-OPERATOR" || events[0].Role != "operator" {
		t.Fatalf("actor/role missing: %#v", events[0])
	}
}

func TestTopologyAdapterRecordsRejectedNoQuorumWrite(t *testing.T) {
	cluster, adapter, sink := newAuditedCluster(t)
	if err := cluster.Crash("echo"); err != nil {
		t.Fatal(err)
	}
	if err := cluster.Crash("northstar"); err != nil {
		t.Fatal(err)
	}

	_, err := adapter.CommitTopology(TopologyCommitRequest{
		CorrelationID: "run-no-quorum",
		Actor:         "DEMO-OPERATOR",
		Role:          "operator",
		Payload:       []byte(`{"revision":"rejected"}`),
	})
	if !errors.Is(err, ErrNoQuorum) {
		t.Fatalf("error = %v, want ErrNoQuorum", err)
	}
	events := sink.Events()
	if len(events) != 2 || events[1].Type != "chameleon.topology_revision_rejected" {
		t.Fatalf("expected requested/rejected audit events, got %#v", events)
	}
	if events[1].Severity != "warning" {
		t.Fatalf("rejection severity = %q", events[1].Severity)
	}
}

func TestTopologyAdapterRequiresOperatorAndRejectsRecovery(t *testing.T) {
	_, adapter, sink := newAuditedCluster(t)
	_, err := adapter.CommitTopology(TopologyCommitRequest{
		CorrelationID: "run-viewer",
		Actor:         "DEMO-VIEWER",
		Role:          "viewer",
		Payload:       []byte(`{"revision":"blocked"}`),
	})
	if !errors.Is(err, ErrOperatorRoleRequired) {
		t.Fatalf("error = %v, want operator role error", err)
	}
	if got := len(sink.Events()); got != 0 {
		t.Fatalf("unauthorized attempt wrote audit event count %d", got)
	}
	if err := adapter.CommitRecoveryAction(); !errors.Is(err, ErrRecoveryEntryType) {
		t.Fatalf("recovery error = %v", err)
	}
}
