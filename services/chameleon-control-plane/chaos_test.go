package controlplane

import (
	"errors"
	"strings"
	"testing"
)

func TestChaosThreeVoterCrashAndRecovery(t *testing.T) {
	scenario := ChaosScenario{
		Name:          "three-voter-leader-crash-recovery",
		CorrelationID: "run_chaos_3v",
		ClusterID:     "chaos-3v",
		VoterIDs:      []string{"atlas", "echo", "northstar"},
		Steps: []ChaosStep{
			{Type: ChaosAdvance, AdvanceMs: 1500},
			{
				Type:          ChaosSubmitTopology,
				Actor:         "DEMO-OPERATOR",
				Payload:       []byte(`{"revision":"pre-crash"}`),
				AuditEventRef: "evt_chaos_3v_1",
			},
			{Type: ChaosCrash, NodeIDs: []string{"atlas"}},
			{Type: ChaosAdvance, AdvanceMs: 1800},
			{Type: ChaosRecover, NodeIDs: []string{"atlas"}},
			{
				Type:          ChaosSubmitTopology,
				Actor:         "DEMO-OPERATOR",
				Payload:       []byte(`{"revision":"post-recover"}`),
				AuditEventRef: "evt_chaos_3v_2",
			},
		},
	}

	cluster, result, err := RunChaosScenario(scenario)
	if err != nil {
		t.Fatal(err)
	}
	if result.CommittedTopologyCount != 2 {
		t.Fatalf("committed = %d, want 2", result.CommittedTopologyCount)
	}
	if result.RejectedWriteCount != 0 {
		t.Fatalf("rejected = %d, want 0", result.RejectedWriteCount)
	}
	if cluster.LeaderID == "" {
		t.Fatal("expected a leader after recovery path")
	}
	if got := cluster.Nodes["atlas"].CommitIndex; got != 2 {
		t.Fatalf("recovered atlas commit index = %d, want 2", got)
	}
	if result.VirtualTimeMs != 3300 {
		t.Fatalf("virtual_time = %d, want 3300", result.VirtualTimeMs)
	}
}

func TestChaosFiveVoterMinorityPartitionRejectsThenHeals(t *testing.T) {
	scenario := ChaosScenario{
		Name:          "five-voter-minority-partition",
		CorrelationID: "run_chaos_5v",
		ClusterID:     "chaos-5v",
		VoterIDs:      []string{"node-01", "node-02", "node-03", "node-04", "node-05"},
		ObserverIDs:   []string{"node-06"},
		Steps: []ChaosStep{
			{Type: ChaosAdvance, AdvanceMs: 1500},
			{
				Type:          ChaosSubmitTopology,
				Actor:         "DEMO-OPERATOR",
				Payload:       []byte(`{"revision":"before-partition"}`),
				AuditEventRef: "evt_chaos_5v_1",
			},
			{Type: ChaosPartition, NodeIDs: []string{"node-03", "node-04", "node-05"}},
			{Type: ChaosDelayMarker, AdvanceMs: 250},
			{
				Type:          ChaosSubmitTopology,
				Actor:         "DEMO-OPERATOR",
				Payload:       []byte(`{"revision":"must-reject"}`),
				AuditEventRef: "evt_chaos_5v_blocked",
			},
			{Type: ChaosHeal, NodeIDs: []string{"node-03", "node-04", "node-05"}},
			{Type: ChaosAdvance, AdvanceMs: 300},
			{
				Type:          ChaosSubmitTopology,
				Actor:         "DEMO-OPERATOR",
				Payload:       []byte(`{"revision":"after-heal"}`),
				AuditEventRef: "evt_chaos_5v_2",
			},
		},
	}

	cluster, result, err := RunChaosScenario(scenario)
	if err != nil {
		t.Fatal(err)
	}
	if result.CommittedTopologyCount != 2 {
		t.Fatalf("committed = %d, want 2", result.CommittedTopologyCount)
	}
	if result.RejectedWriteCount != 1 {
		t.Fatalf("rejected = %d, want 1", result.RejectedWriteCount)
	}
	if cluster.AliveVoters() != 5 {
		t.Fatalf("alive voters = %d, want 5", cluster.AliveVoters())
	}
	for _, nodeID := range []string{"node-03", "node-04", "node-05"} {
		if !cluster.Nodes[nodeID].Alive {
			t.Fatalf("%s should remain alive under isolate (not crash)", nodeID)
		}
	}
	if result.AppliedSteps[3].Type != ChaosDelayMarker {
		t.Fatalf("expected delay marker step, got %#v", result.AppliedSteps[3])
	}
}

func TestIsolateKeepsNodesAliveAndBlocksMinoritySideWrites(t *testing.T) {
	cluster, err := NewCluster("partition-live", []string{"node-01", "node-02", "node-03", "node-04", "node-05"})
	if err != nil {
		t.Fatal(err)
	}
	cluster.Advance(1500)
	if _, err := cluster.SubmitTopologyRevision(
		"run_partition_live",
		"DEMO-OPERATOR",
		[]byte(`{"revision":"seed"}`),
		"evt_partition_seed",
	); err != nil {
		t.Fatal(err)
	}
	// Isolate a true minority so majority can still commit.
	if err := cluster.Isolate([]string{"node-04", "node-05"}); err != nil {
		t.Fatal(err)
	}
	for _, nodeID := range []string{"node-04", "node-05"} {
		if !cluster.Nodes[nodeID].Alive {
			t.Fatalf("%s should stay alive while isolated", nodeID)
		}
	}
	if _, err := cluster.SubmitTopologyRevision(
		"run_partition_live",
		"DEMO-OPERATOR",
		[]byte(`{"revision":"majority-commit"}`),
		"evt_partition_majority",
	); err != nil {
		t.Fatal(err)
	}
	if got := cluster.Nodes["node-04"].CommitIndex; got != 1 {
		t.Fatalf("isolated node should not receive majority commit yet, commit=%d", got)
	}
	if err := cluster.HealPartitions(); err != nil {
		t.Fatal(err)
	}
	if got := cluster.Nodes["node-04"].CommitIndex; got != 2 {
		t.Fatalf("healed node commit index = %d, want 2", got)
	}
}

func TestChaosObserverOutageDoesNotChangeQuorum(t *testing.T) {
	scenario := ChaosScenario{
		Name:          "observer-outage",
		CorrelationID: "run_chaos_obs",
		ClusterID:     "chaos-obs",
		VoterIDs:      []string{"node-01", "node-02", "node-03"},
		ObserverIDs:   []string{"node-06", "node-07"},
		Steps: []ChaosStep{
			{Type: ChaosAdvance, AdvanceMs: 1500},
			{Type: ChaosCrash, NodeIDs: []string{"node-06"}},
			{
				Type:          ChaosSubmitTopology,
				Actor:         "DEMO-OPERATOR",
				Payload:       []byte(`{"revision":"observer-outage"}`),
				AuditEventRef: "evt_chaos_obs_1",
			},
			{Type: ChaosRecover, NodeIDs: []string{"node-06"}},
		},
	}

	cluster, result, err := RunChaosScenario(scenario)
	if err != nil {
		t.Fatal(err)
	}
	if result.CommittedTopologyCount != 1 {
		t.Fatalf("committed = %d, want 1", result.CommittedTopologyCount)
	}
	if cluster.Quorum() != 2 {
		t.Fatalf("quorum = %d, want 2", cluster.Quorum())
	}
	if got := cluster.Nodes["node-06"].CommitIndex; got != 1 {
		t.Fatalf("observer catch-up commit = %d, want 1", got)
	}
}

func TestChaosInvalidMessageRejectedWithoutStateChange(t *testing.T) {
	scenario := ChaosScenario{
		Name:          "invalid-message-rejection",
		CorrelationID: "run_chaos_invalid",
		ClusterID:     "chaos-invalid",
		VoterIDs:      []string{"atlas", "echo", "northstar"},
		Steps: []ChaosStep{
			{Type: ChaosAdvance, AdvanceMs: 1500},
			{
				Type:          ChaosSubmitTopology,
				Actor:         "DEMO-OPERATOR",
				Payload:       []byte(`{"revision":"good"}`),
				AuditEventRef: "evt_chaos_good",
			},
			{
				Type:    ChaosRejectInvalidMessage,
				Actor:   "DEMO-OPERATOR",
				Payload: []byte(`{"recovery_command":"approve-route"}`),
			},
			{
				Type:    ChaosRejectInvalidMessage,
				Actor:   "DEMO-OPERATOR",
				Payload: []byte(`not-json`),
			},
		},
	}

	cluster, result, err := RunChaosScenario(scenario)
	if err != nil {
		t.Fatal(err)
	}
	if result.CommittedTopologyCount != 1 {
		t.Fatalf("committed = %d, want 1", result.CommittedTopologyCount)
	}
	if result.RejectedWriteCount != 2 {
		t.Fatalf("rejected = %d, want 2", result.RejectedWriteCount)
	}
	leader := cluster.Nodes[cluster.LeaderID]
	if len(leader.Log) != 1 || leader.CommitIndex != 1 {
		t.Fatalf("invalid messages altered committed log: %#v", leader)
	}
	if cluster.TopologyRevision == "" {
		t.Fatal("expected original topology revision retained")
	}
}

func TestChaosScenarioRejectsUnsupportedFaultTypes(t *testing.T) {
	_, _, err := RunChaosScenario(ChaosScenario{
		Name:          "bad",
		CorrelationID: "run_bad",
		ClusterID:     "bad",
		VoterIDs:      []string{"a", "b", "c"},
		Steps:         []ChaosStep{{Type: "byzantine_equivocation", AdvanceMs: 1}},
	})
	if err == nil || !strings.Contains(err.Error(), "unsupported chaos fault type") {
		t.Fatalf("error = %v, want unsupported fault type", err)
	}
}

func TestChaosWithAuditAdapterPreservesCorrelationAndHashChain(t *testing.T) {
	cluster, err := NewCluster("chaos-audit", []string{"atlas", "echo", "northstar"})
	if err != nil {
		t.Fatal(err)
	}
	cluster.Advance(1500)
	sink := &MemoryAuditEventSink{}
	adapter, err := NewTopologyAuditAdapter(cluster, sink)
	if err != nil {
		t.Fatal(err)
	}

	if err := cluster.Crash("echo"); err != nil {
		t.Fatal(err)
	}
	if err := cluster.Crash("northstar"); err != nil {
		t.Fatal(err)
	}
	_, err = adapter.CommitTopology(TopologyCommitRequest{
		CorrelationID: "run_chaos_audit",
		Actor:         "DEMO-OPERATOR",
		Role:          "operator",
		Payload:       []byte(`{"revision":"partitioned"}`),
	})
	if !errors.Is(err, ErrNoQuorum) {
		t.Fatalf("error = %v, want ErrNoQuorum", err)
	}

	events := sink.Events()
	if len(events) != 2 {
		t.Fatalf("event count = %d, want 2", len(events))
	}
	if events[0].CorrelationID != "run_chaos_audit" || events[1].CorrelationID != "run_chaos_audit" {
		t.Fatalf("correlation mismatch: %#v", events)
	}
	if events[0].Type != "chameleon.topology_revision_requested" {
		t.Fatalf("first event = %q", events[0].Type)
	}
	if events[1].Type != "chameleon.topology_revision_rejected" {
		t.Fatalf("second event = %q", events[1].Type)
	}
	if events[1].PreviousHash != events[0].EventHash {
		t.Fatal("audit hash chain broken under chaos rejection")
	}
}

func TestValidateTopologyPayloadRejectsRecoveryShapedInput(t *testing.T) {
	if err := ValidateTopologyPayload([]byte(`{"revision":"ok"}`)); err != nil {
		t.Fatal(err)
	}
	if err := ValidateTopologyPayload([]byte(`{"recovery_command":"x"}`)); !errors.Is(err, ErrInvalidTopologyPayload) {
		t.Fatalf("error = %v", err)
	}
	if err := ValidateTopologyPayload([]byte(`{`)); !errors.Is(err, ErrInvalidTopologyPayload) {
		t.Fatalf("error = %v", err)
	}
}
