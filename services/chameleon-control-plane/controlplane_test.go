package controlplane

import (
	"errors"
	"fmt"
	"testing"
)

func newElectedCluster(t *testing.T) *Cluster {
	t.Helper()
	cluster, err := NewCluster("regional-pilot-a", []string{"atlas", "echo", "northstar"})
	if err != nil {
		t.Fatal(err)
	}
	cluster.Advance(1500)
	if cluster.LeaderID != "atlas" {
		t.Fatalf("expected deterministic atlas leader, got %q", cluster.LeaderID)
	}
	return cluster
}

func TestElectsLeaderWithThreeVoters(t *testing.T) {
	cluster := newElectedCluster(t)
	if cluster.Nodes["atlas"].Role != Leader {
		t.Fatalf("atlas role = %q, want leader", cluster.Nodes["atlas"].Role)
	}
	if cluster.Nodes["echo"].CurrentTerm != 1 {
		t.Fatalf("follower term = %d, want 1", cluster.Nodes["echo"].CurrentTerm)
	}
}

func TestReplicatesTopologyRevisionWithQuorum(t *testing.T) {
	cluster := newElectedCluster(t)
	entry, err := cluster.SubmitTopologyRevision(
		"run_fixture",
		"DEMO-OPERATOR",
		[]byte(`{"nodes":["atlas","echo"]}`),
		"evt_topology_001",
	)
	if err != nil {
		t.Fatal(err)
	}
	if entry.Index != 1 || entry.EntryType != "topology.revision" {
		t.Fatalf("unexpected entry: %#v", entry)
	}
	for _, node := range cluster.Nodes {
		if len(node.Log) != 1 || node.CommitIndex != 1 || node.LastApplied != 1 {
			t.Fatalf("%s did not commit entry: %#v", node.ID, node)
		}
	}
	if cluster.AuditChainHead != "evt_topology_001" {
		t.Fatalf("audit reference not retained: %q", cluster.AuditChainHead)
	}
}

func TestLeaderCrashElectsReplacementAndRecoversFollower(t *testing.T) {
	cluster := newElectedCluster(t)
	if _, err := cluster.SubmitTopologyRevision(
		"run_fixture",
		"DEMO-OPERATOR",
		[]byte(`{"revision":1}`),
		"evt_1",
	); err != nil {
		t.Fatal(err)
	}
	if err := cluster.Crash("atlas"); err != nil {
		t.Fatal(err)
	}
	cluster.Advance(1800)
	if cluster.LeaderID != "echo" {
		t.Fatalf("expected echo replacement leader, got %q", cluster.LeaderID)
	}
	if err := cluster.Recover("atlas"); err != nil {
		t.Fatal(err)
	}
	if got := cluster.Nodes["atlas"].CommitIndex; got != 1 {
		t.Fatalf("recovered node commit index = %d, want 1", got)
	}
	if len(cluster.Nodes["atlas"].Log) != 1 {
		t.Fatalf("recovered node did not catch up")
	}
}

func TestNoQuorumRejectsTopologyWrite(t *testing.T) {
	cluster := newElectedCluster(t)
	if err := cluster.Crash("echo"); err != nil {
		t.Fatal(err)
	}
	if err := cluster.Crash("northstar"); err != nil {
		t.Fatal(err)
	}
	_, err := cluster.SubmitTopologyRevision(
		"run_fixture",
		"DEMO-OPERATOR",
		[]byte(`{"revision":2}`),
		"evt_2",
	)
	if !errors.Is(err, ErrNoQuorum) {
		t.Fatalf("error = %v, want ErrNoQuorum", err)
	}
}

func TestRecoveryApprovalIsNeverAConsensusCommand(t *testing.T) {
	cluster := newElectedCluster(t)
	if err := cluster.SubmitRecoveryApproval(); !errors.Is(err, ErrRecoveryAction) {
		t.Fatalf("error = %v, want ErrRecoveryAction", err)
	}
}

func TestSnapshotIncludesAuditReferenceAndStateHash(t *testing.T) {
	cluster := newElectedCluster(t)
	if _, err := cluster.SubmitTopologyRevision(
		"run_fixture",
		"DEMO-OPERATOR",
		[]byte(`{"revision":3}`),
		"evt_3",
	); err != nil {
		t.Fatal(err)
	}
	snapshot, err := cluster.Snapshot()
	if err != nil {
		t.Fatal(err)
	}
	if snapshot.LastIncludedIndex != 1 || snapshot.AuditChainHead != "evt_3" {
		t.Fatalf("unexpected snapshot: %#v", snapshot)
	}
	if len(snapshot.StateHash) != 64 {
		t.Fatalf("state hash length = %d, want 64", len(snapshot.StateHash))
	}
}

func tenNodeHarness(t *testing.T) *Cluster {
	t.Helper()
	voters := []string{"node-01", "node-02", "node-03", "node-04", "node-05"}
	observers := []string{"node-06", "node-07", "node-08", "node-09", "node-10"}
	cluster, err := NewClusterWithObservers("ten-node-harness", voters, observers)
	if err != nil {
		t.Fatal(err)
	}
	cluster.Advance(1500)
	if cluster.LeaderID != "node-01" {
		t.Fatalf("expected node-01 leader, got %q", cluster.LeaderID)
	}
	return cluster
}

func TestTenNodeHarnessReplicatesToObserversWithoutChangingQuorum(t *testing.T) {
	cluster := tenNodeHarness(t)
	if got := cluster.Quorum(); got != 3 {
		t.Fatalf("quorum = %d, want 3 for five voters", got)
	}
	if got := cluster.AliveVoters(); got != 5 {
		t.Fatalf("alive voters = %d, want 5", got)
	}
	entry, err := cluster.SubmitTopologyRevision(
		"run_ten_node",
		"DEMO-OPERATOR",
		[]byte(`{"revision":"ten-node-observer-replication"}`),
		"evt_ten_1",
	)
	if err != nil {
		t.Fatal(err)
	}
	for _, node := range cluster.Nodes {
		if len(node.Log) != 1 || node.CommitIndex != entry.Index {
			t.Fatalf("%s did not receive committed topology state", node.ID)
		}
	}
	if cluster.Nodes["node-06"].Voter {
		t.Fatal("observer unexpectedly contributed to quorum")
	}
}

func TestTenNodeHarnessRejectsMinorityPartitionWrites(t *testing.T) {
	cluster := tenNodeHarness(t)
	for _, nodeID := range []string{"node-03", "node-04", "node-05"} {
		if err := cluster.Crash(nodeID); err != nil {
			t.Fatal(err)
		}
	}
	if got := cluster.AliveVoters(); got != 2 {
		t.Fatalf("alive voters = %d, want 2", got)
	}
	_, err := cluster.SubmitTopologyRevision(
		"run_ten_node",
		"DEMO-OPERATOR",
		[]byte(`{"revision":"must-not-commit"}`),
		"evt_ten_partition",
	)
	if !errors.Is(err, ErrNoQuorum) {
		t.Fatalf("error = %v, want ErrNoQuorum", err)
	}
	if cluster.TopologyRevision != "" {
		t.Fatalf("minority partition updated topology: %q", cluster.TopologyRevision)
	}
}

func TestTenNodeHarnessRecoversObserversAndVoters(t *testing.T) {
	cluster := tenNodeHarness(t)
	if err := cluster.Crash("node-06"); err != nil {
		t.Fatal(err)
	}
	if _, err := cluster.SubmitTopologyRevision(
		"run_ten_node",
		"DEMO-OPERATOR",
		[]byte(`{"revision":"catch-up"}`),
		"evt_ten_catchup",
	); err != nil {
		t.Fatal(err)
	}
	if err := cluster.Recover("node-06"); err != nil {
		t.Fatal(err)
	}
	if got := cluster.Nodes["node-06"].CommitIndex; got != 1 {
		t.Fatalf("observer commit index = %d, want 1", got)
	}
	if err := cluster.Crash("node-01"); err != nil {
		t.Fatal(err)
	}
	cluster.Advance(1800)
	if cluster.LeaderID != "node-02" {
		t.Fatalf("replacement leader = %q, want node-02", cluster.LeaderID)
	}
}

// BenchmarkTenNodeTopologyRevision is a reproducible in-process baseline only.
// It does not model network I/O, persistence, TLS, CPU contention, or regional
// failure domains and must not be used as a production latency/throughput claim.
func BenchmarkTenNodeTopologyRevision(b *testing.B) {
	voters := []string{"node-01", "node-02", "node-03", "node-04", "node-05"}
	observers := []string{"node-06", "node-07", "node-08", "node-09", "node-10"}
	cluster, err := NewClusterWithObservers("ten-node-benchmark", voters, observers)
	if err != nil {
		b.Fatal(err)
	}
	cluster.Advance(1500)
	payload := []byte(`{"revision":"benchmark-topology"}`)

	b.ResetTimer()
	for index := 0; index < b.N; index++ {
		if _, err := cluster.SubmitTopologyRevision(
			"run_benchmark",
			"BENCHMARK-OPERATOR",
			payload,
			fmt.Sprintf("evt_benchmark_%d", index),
		); err != nil {
			b.Fatal(err)
		}
	}
}
