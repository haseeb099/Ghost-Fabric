package controlplane

import (
	"strings"
	"testing"
	"time"
)

func TestMetricsCollectorRendersPrometheusText(t *testing.T) {
	collector := NewMetricsCollector()
	collector.ObserveCommit(12*time.Millisecond, false)
	collector.ObserveCommit(30*time.Millisecond, true)
	collector.SetControlPlaneState(2, 1, 1)

	text := collector.RenderPrometheus()
	for _, needle := range []string{
		"chameleon_topology_commits_total",
		"chameleon_topology_rejections_total",
		"chameleon_control_operation_duration_seconds_bucket",
		"chameleon_degradation_level",
		"chameleon_offline_nodes",
		"chameleon_critical_health_reports",
		`service="chameleon-control-plane"`,
	} {
		if !strings.Contains(text, needle) {
			t.Fatalf("prometheus text missing %q:\n%s", needle, text)
		}
	}
	if !strings.Contains(text, "chameleon_topology_commits_total{service=\"chameleon-control-plane\"} 1") {
		t.Fatalf("unexpected commit count:\n%s", text)
	}
	if !strings.Contains(text, "chameleon_topology_rejections_total{service=\"chameleon-control-plane\"} 1") {
		t.Fatalf("unexpected rejection count:\n%s", text)
	}
}

func TestMetricsCollectorDoesNotReplaceAuditSink(t *testing.T) {
	collector := NewMetricsCollector()
	_, adapter, sink := newAuditedCluster(t)
	started := time.Now()
	_, err := adapter.CommitTopology(TopologyCommitRequest{
		CorrelationID: "run-metrics",
		Actor:         "DEMO-OPERATOR",
		Role:          "operator",
		Payload:       []byte(`{"topology":"metrics"}`),
	})
	if err != nil {
		t.Fatal(err)
	}
	collector.ObserveCommit(time.Since(started), false)
	if len(sink.Events()) < 2 {
		t.Fatalf("expected canonical audit events, got %d", len(sink.Events()))
	}
	if !strings.Contains(collector.RenderPrometheus(), "chameleon_topology_commits_total") {
		t.Fatal("expected process metrics independent of audit sink")
	}
}
