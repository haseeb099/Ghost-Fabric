package controlplane

import (
	"fmt"
	"strings"
	"sync"
	"time"
)

// MetricsCollector exposes Prometheus-compatible process telemetry for the
// in-process control plane. It never replaces AuditEventSink.
type MetricsCollector struct {
	mu sync.Mutex

	commitsTotal     float64
	rejectionsTotal  float64
	operationSeconds []float64
	degradationLevel float64
	offlineNodeCount float64
	criticalHealth   float64
}

func NewMetricsCollector() *MetricsCollector {
	return &MetricsCollector{}
}

func (m *MetricsCollector) ObserveCommit(duration time.Duration, rejected bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if rejected {
		m.rejectionsTotal++
	} else {
		m.commitsTotal++
	}
	m.operationSeconds = append(m.operationSeconds, duration.Seconds())
}

func (m *MetricsCollector) SetControlPlaneState(degradationLevel int, offlineNodes int, criticalReports int) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.degradationLevel = float64(degradationLevel)
	m.offlineNodeCount = float64(offlineNodes)
	m.criticalHealth = float64(criticalReports)
}

// SyncFromCluster copies non-authoritative control-plane gauges from cluster state.
func (m *MetricsCollector) SyncFromCluster(cluster *Cluster) {
	if cluster == nil {
		return
	}
	state := cluster.EvaluateDegradation()
	m.SetControlPlaneState(degradationOrdinal(state.Level), state.OfflineNodes, state.CriticalHealth)
}

func degradationOrdinal(level DegradationLevel) int {
	switch level {
	case DegradationNormal:
		return 0
	case DegradationShedLow:
		return 1
	case DegradationShedMedium:
		return 2
	case DegradationShedHigh:
		return 3
	case DegradationEssentialOnly:
		return 4
	default:
		return -1
	}
}

func (m *MetricsCollector) RenderPrometheus() string {
	m.mu.Lock()
	defer m.mu.Unlock()

	var b strings.Builder
	writeHelpType(&b, "chameleon_topology_commits_total", "counter", "Successful topology commits observed by the control-plane collector")
	fmt.Fprintf(&b, "chameleon_topology_commits_total{service=\"chameleon-control-plane\"} %g\n", m.commitsTotal)

	writeHelpType(&b, "chameleon_topology_rejections_total", "counter", "Rejected topology commits (including no-quorum)")
	fmt.Fprintf(&b, "chameleon_topology_rejections_total{service=\"chameleon-control-plane\"} %g\n", m.rejectionsTotal)

	writeHelpType(&b, "chameleon_control_operation_duration_seconds", "histogram", "Control-plane operation duration in seconds")
	writeHistogram(&b, "chameleon_control_operation_duration_seconds", m.operationSeconds)

	writeHelpType(&b, "chameleon_degradation_level", "gauge", "Current degradation level ordinal (pilot process state only)")
	fmt.Fprintf(&b, "chameleon_degradation_level{service=\"chameleon-control-plane\"} %g\n", m.degradationLevel)

	writeHelpType(&b, "chameleon_offline_nodes", "gauge", "Offline mesh nodes observed by the control plane")
	fmt.Fprintf(&b, "chameleon_offline_nodes{service=\"chameleon-control-plane\"} %g\n", m.offlineNodeCount)

	writeHelpType(&b, "chameleon_critical_health_reports", "gauge", "Nodes currently reporting critical health")
	fmt.Fprintf(&b, "chameleon_critical_health_reports{service=\"chameleon-control-plane\"} %g\n", m.criticalHealth)
	return b.String()
}

func writeHelpType(b *strings.Builder, name, metricType, help string) {
	fmt.Fprintf(b, "# HELP %s %s\n", name, help)
	fmt.Fprintf(b, "# TYPE %s %s\n", name, metricType)
}

func writeHistogram(b *strings.Builder, name string, values []float64) {
	buckets := []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1}
	counts := make([]int, len(buckets))
	var sum float64
	for _, value := range values {
		sum += value
		for i, bound := range buckets {
			if value <= bound {
				counts[i]++
			}
		}
	}
	for i, bound := range buckets {
		fmt.Fprintf(
			b,
			"%s_bucket{service=\"chameleon-control-plane\",le=\"%g\"} %d\n",
			name,
			bound,
			counts[i],
		)
	}
	fmt.Fprintf(b, "%s_bucket{service=\"chameleon-control-plane\",le=\"+Inf\"} %d\n", name, len(values))
	fmt.Fprintf(b, "%s_sum{service=\"chameleon-control-plane\"} %g\n", name, sum)
	fmt.Fprintf(b, "%s_count{service=\"chameleon-control-plane\"} %d\n", name, len(values))
}
