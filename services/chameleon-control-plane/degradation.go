package controlplane

import "sort"

// FeatureCriticality ranks mesh features for shedding under pressure.
type FeatureCriticality string

const (
	CriticalityCritical FeatureCriticality = "critical"
	CriticalityHigh     FeatureCriticality = "high"
	CriticalityMedium   FeatureCriticality = "medium"
	CriticalityLow      FeatureCriticality = "low"
)

// DegradationLevel is the declared mesh operating posture. It never authorizes
// recovery; it only records which non-critical features are shed.
type DegradationLevel string

const (
	DegradationNormal        DegradationLevel = "normal"
	DegradationShedLow       DegradationLevel = "shed_low"
	DegradationShedMedium    DegradationLevel = "shed_medium"
	DegradationShedHigh      DegradationLevel = "shed_high"
	DegradationEssentialOnly DegradationLevel = "essential_only"
)

// MeshFeature is a named capability that may be shed by criticality.
type MeshFeature struct {
	ID          string             `json:"id"`
	Criticality FeatureCriticality `json:"criticality"`
}

// DegradationState is the current feature-shed posture.
type DegradationState struct {
	Level          DegradationLevel `json:"level"`
	ActiveFeatures []string         `json:"active_features"`
	ShedFeatures   []string         `json:"shed_features"`
	AliveVoters    int              `json:"alive_voters"`
	Quorum         int              `json:"quorum"`
	OfflineNodes   int              `json:"offline_nodes"`
	CriticalHealth int              `json:"critical_health"`
}

var defaultMeshFeatures = []MeshFeature{
	{ID: "leader_election", Criticality: CriticalityCritical},
	{ID: "topology_replication", Criticality: CriticalityCritical},
	{ID: "route_recalculation", Criticality: CriticalityHigh},
	{ID: "health_broadcast", Criticality: CriticalityHigh},
	{ID: "observer_fanout", Criticality: CriticalityMedium},
	{ID: "benchmark_sampling", Criticality: CriticalityLow},
	{ID: "console_animation", Criticality: CriticalityLow},
}

func (c *Cluster) ensureFeatures() {
	if len(c.Features) == 0 {
		c.Features = append([]MeshFeature(nil), defaultMeshFeatures...)
	}
}

// EvaluateDegradation recomputes feature shedding from quorum, offline count,
// and critical health reports. Consensus still cannot approve recovery.
func (c *Cluster) EvaluateDegradation() DegradationState {
	c.refreshDegradation()
	return c.Degradation
}

func (c *Cluster) refreshDegradation() {
	c.ensureFeatures()

	offline := 0
	criticalHealth := 0
	for id, node := range c.Nodes {
		if !node.Alive {
			offline++
			continue
		}
		if report, ok := c.Health[id]; ok && report.Grade == HealthCritical {
			criticalHealth++
		}
	}

	aliveVoters := c.AliveVoters()
	quorum := c.Quorum()
	level := DegradationNormal
	switch {
	case aliveVoters < quorum:
		level = DegradationEssentialOnly
	case offline >= 3 || criticalHealth >= 2:
		level = DegradationShedHigh
	case offline >= 2 || criticalHealth >= 1:
		level = DegradationShedMedium
	case offline >= 1:
		level = DegradationShedLow
	}

	active := make([]string, 0, len(c.Features))
	shed := make([]string, 0)
	for _, feature := range c.Features {
		if shouldShed(level, feature.Criticality) {
			shed = append(shed, feature.ID)
			continue
		}
		active = append(active, feature.ID)
	}
	sort.Strings(active)
	sort.Strings(shed)

	c.Degradation = DegradationState{
		Level:          level,
		ActiveFeatures: active,
		ShedFeatures:   shed,
		AliveVoters:    aliveVoters,
		Quorum:         quorum,
		OfflineNodes:   offline,
		CriticalHealth: criticalHealth,
	}
}

func shouldShed(level DegradationLevel, criticality FeatureCriticality) bool {
	switch level {
	case DegradationNormal:
		return false
	case DegradationShedLow:
		return criticality == CriticalityLow
	case DegradationShedMedium:
		return criticality == CriticalityLow || criticality == CriticalityMedium
	case DegradationShedHigh:
		return criticality != CriticalityCritical
	case DegradationEssentialOnly:
		return criticality != CriticalityCritical
	default:
		return false
	}
}
