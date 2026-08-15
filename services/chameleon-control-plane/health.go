package controlplane

import (
	"fmt"
	"math"
	"sort"
)

// HealthGrade is a discrete mesh-node readiness class derived from synthetic
// or fixture-supplied signals. It is not an operational SLA assertion.
type HealthGrade string

const (
	HealthHealthy  HealthGrade = "healthy"
	HealthDegraded HealthGrade = "degraded"
	HealthCritical HealthGrade = "critical"
	HealthOffline  HealthGrade = "offline"
)

// HealthSignals are unitless fixture or synthetic observations. LatencyMs is a
// measured or injected observation for scoring, not a product claim.
type HealthSignals struct {
	CPUPercent    float64 `json:"cpu_percent"`
	MemoryPercent float64 `json:"memory_percent"`
	LatencyMs     float64 `json:"latency_ms"`
}

// HealthReport is the scored view of a single node.
type HealthReport struct {
	NodeID  string        `json:"node_id"`
	Score   float64       `json:"score"`
	Grade   HealthGrade   `json:"grade"`
	Signals HealthSignals `json:"signals"`
}

// ScoreHealth converts CPU, memory, and latency signals into a 0–100 score.
// Weights: CPU 35%, memory 35%, latency 30%. Offline nodes always score 0.
func ScoreHealth(nodeID string, alive bool, signals HealthSignals) HealthReport {
	if !alive {
		return HealthReport{
			NodeID:  nodeID,
			Score:   0,
			Grade:   HealthOffline,
			Signals: signals,
		}
	}

	cpuPenalty := clamp01(signals.CPUPercent / 100)
	memPenalty := clamp01(signals.MemoryPercent / 100)
	// 200ms synthetic latency maps to a full latency penalty for scoring only.
	latPenalty := clamp01(signals.LatencyMs / 200)

	score := 100 * (1 - (0.35*cpuPenalty + 0.35*memPenalty + 0.30*latPenalty))
	score = math.Round(score*10) / 10

	grade := HealthHealthy
	switch {
	case score < 40:
		grade = HealthCritical
	case score < 70:
		grade = HealthDegraded
	}

	return HealthReport{
		NodeID:  nodeID,
		Score:   score,
		Grade:   grade,
		Signals: signals,
	}
}

func (c *Cluster) ReportHealth(nodeID string, signals HealthSignals) (HealthReport, error) {
	node, ok := c.Nodes[nodeID]
	if !ok {
		return HealthReport{}, fmt.Errorf("unknown node %q", nodeID)
	}
	if c.Health == nil {
		c.Health = make(map[string]HealthReport)
	}
	report := ScoreHealth(nodeID, node.Alive, signals)
	c.Health[nodeID] = report
	c.refreshDegradation()
	return report, nil
}

func (c *Cluster) HealthSnapshot() []HealthReport {
	ids := make([]string, 0, len(c.Nodes))
	for id := range c.Nodes {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	out := make([]HealthReport, 0, len(ids))
	for _, id := range ids {
		if report, ok := c.Health[id]; ok {
			out = append(out, report)
			continue
		}
		out = append(out, ScoreHealth(id, c.Nodes[id].Alive, HealthSignals{}))
	}
	return out
}

func clamp01(value float64) float64 {
	if value < 0 {
		return 0
	}
	if value > 1 {
		return 1
	}
	return value
}
