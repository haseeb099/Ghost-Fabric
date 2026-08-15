package controlplane

import (
	"strings"
	"testing"
	"time"
)

func meshReadyCluster(t *testing.T) *Cluster {
	t.Helper()
	cluster := tenNodeHarness(t)
	edges := []MeshEdge{
		{A: "node-01", B: "node-02"},
		{A: "node-02", B: "node-03"},
		{A: "node-03", B: "node-04"},
		{A: "node-04", B: "node-05"},
		{A: "node-05", B: "node-06"},
		{A: "node-06", B: "node-07"},
		{A: "node-07", B: "node-08"},
		{A: "node-08", B: "node-09"},
		{A: "node-09", B: "node-10"},
		{A: "node-01", B: "node-06"},
		{A: "node-03", B: "node-08"},
	}
	if err := cluster.SetMeshEdges(edges); err != nil {
		t.Fatal(err)
	}
	return cluster
}

func TestScoreHealthGradesSyntheticSignals(t *testing.T) {
	healthy := ScoreHealth("n1", true, HealthSignals{CPUPercent: 10, MemoryPercent: 20, LatencyMs: 5})
	if healthy.Grade != HealthHealthy || healthy.Score < 70 {
		t.Fatalf("healthy report = %#v", healthy)
	}
	degraded := ScoreHealth("n2", true, HealthSignals{CPUPercent: 70, MemoryPercent: 65, LatencyMs: 80})
	if degraded.Grade != HealthDegraded {
		t.Fatalf("degraded grade = %q", degraded.Grade)
	}
	critical := ScoreHealth("n3", true, HealthSignals{CPUPercent: 95, MemoryPercent: 90, LatencyMs: 180})
	if critical.Grade != HealthCritical {
		t.Fatalf("critical grade = %q", critical.Grade)
	}
	offline := ScoreHealth("n4", false, HealthSignals{CPUPercent: 0, MemoryPercent: 0, LatencyMs: 0})
	if offline.Grade != HealthOffline || offline.Score != 0 {
		t.Fatalf("offline report = %#v", offline)
	}
}

func TestReportHealthUpdatesClusterAndDegradation(t *testing.T) {
	cluster := meshReadyCluster(t)
	report, err := cluster.ReportHealth("node-03", HealthSignals{
		CPUPercent:    92,
		MemoryPercent: 88,
		LatencyMs:     160,
	})
	if err != nil {
		t.Fatal(err)
	}
	if report.Grade != HealthCritical {
		t.Fatalf("grade = %q, want critical", report.Grade)
	}
	state := cluster.EvaluateDegradation()
	if state.Level != DegradationShedMedium {
		t.Fatalf("degradation = %q, want shed_medium", state.Level)
	}
	if !contains(state.ShedFeatures, "console_animation") {
		t.Fatalf("expected low features shed: %#v", state.ShedFeatures)
	}
}

func TestRouteRecalculationExcludesLostNode(t *testing.T) {
	cluster := meshReadyCluster(t)
	before, err := cluster.RecalculateRoutes("run_routes", "")
	if err != nil {
		t.Fatal(err)
	}
	if len(before.Paths) == 0 {
		t.Fatal("expected baseline paths")
	}
	if err := cluster.Crash("node-05"); err != nil {
		t.Fatal(err)
	}
	plan := cluster.LastRoutePlan
	if plan.LostNode != "node-05" {
		t.Fatalf("lost node = %q", plan.LostNode)
	}
	for _, path := range plan.Paths {
		for _, hop := range path {
			if hop == "node-05" {
				t.Fatalf("lost node still present in path %#v", path)
			}
		}
	}
	if plan.Revision == "" || plan.Revision == before.Revision {
		t.Fatalf("expected new route revision, before=%q after=%q", before.Revision, plan.Revision)
	}
	// Fixture-labeled observation only; not a product latency claim.
	started := time.Now()
	if _, err := cluster.RecalculateRoutes("run_routes_timed", "node-05"); err != nil {
		t.Fatal(err)
	}
	elapsed := time.Since(started)
	t.Logf("fixture_labeled_route_recalc_duration_ns=%d", elapsed.Nanoseconds())
}

func TestGracefulDegradationShedsByCriticality(t *testing.T) {
	cluster := meshReadyCluster(t)
	if err := cluster.Crash("node-08"); err != nil {
		t.Fatal(err)
	}
	low := cluster.EvaluateDegradation()
	if low.Level != DegradationShedLow {
		t.Fatalf("level after one loss = %q, want shed_low", low.Level)
	}
	if err := cluster.Crash("node-09"); err != nil {
		t.Fatal(err)
	}
	medium := cluster.EvaluateDegradation()
	if medium.Level != DegradationShedMedium {
		t.Fatalf("level after two losses = %q, want shed_medium", medium.Level)
	}
	if contains(medium.ActiveFeatures, "observer_fanout") {
		t.Fatalf("medium criticality should be shed: %#v", medium.ActiveFeatures)
	}
	if !contains(medium.ActiveFeatures, "leader_election") {
		t.Fatalf("critical features must remain active: %#v", medium.ActiveFeatures)
	}
	if err := cluster.Crash("node-02"); err != nil {
		t.Fatal(err)
	}
	if err := cluster.Crash("node-03"); err != nil {
		t.Fatal(err)
	}
	// Four offline observers/voters may still keep quorum with 5 voters if only
	// some are voters. Force quorum loss by crashing remaining voters.
	if err := cluster.Crash("node-04"); err != nil {
		t.Fatal(err)
	}
	if err := cluster.Crash("node-05"); err != nil {
		t.Fatal(err)
	}
	essential := cluster.EvaluateDegradation()
	if essential.Level != DegradationEssentialOnly {
		t.Fatalf("level without quorum = %q, want essential_only", essential.Level)
	}
	for _, feature := range essential.ActiveFeatures {
		if !strings.Contains(feature, "leader") && !strings.Contains(feature, "topology") {
			t.Fatalf("non-critical feature still active under essential_only: %s", feature)
		}
	}
}

func contains(values []string, want string) bool {
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}
