package controlplane

import (
	"errors"
	"fmt"
	"sort"
	"strings"
)

// Chaos fault types are fixture-only and crash/omission scoped. Byzantine
// tolerance and wall-clock recovery claims are intentionally unsupported.
const (
	ChaosAdvance              = "advance"
	ChaosCrash                = "crash"
	ChaosRecover              = "recover"
	ChaosPartition            = "partition"
	ChaosHeal                 = "heal"
	ChaosDelayMarker          = "delay_marker"
	ChaosSubmitTopology       = "submit_topology"
	ChaosRejectInvalidMessage = "reject_invalid_message"
)

var allowedChaosFaults = map[string]struct{}{
	ChaosAdvance:              {},
	ChaosCrash:                {},
	ChaosRecover:              {},
	ChaosPartition:            {},
	ChaosHeal:                 {},
	ChaosDelayMarker:          {},
	ChaosSubmitTopology:       {},
	ChaosRejectInvalidMessage: {},
}

// ChaosStep is one deterministic virtual-time action in a chaos fixture.
type ChaosStep struct {
	Type          string   `json:"type"`
	NodeIDs       []string `json:"node_ids,omitempty"`
	AdvanceMs     uint64   `json:"advance_ms,omitempty"`
	Actor         string   `json:"actor,omitempty"`
	Payload       []byte   `json:"payload,omitempty"`
	AuditEventRef string   `json:"audit_event_ref,omitempty"`
}

// ChaosScenario declares a fixture-only in-process fault sequence.
type ChaosScenario struct {
	Name          string      `json:"name"`
	CorrelationID string      `json:"correlation_id"`
	ClusterID     string      `json:"cluster_id"`
	VoterIDs      []string    `json:"voter_ids"`
	ObserverIDs   []string    `json:"observer_ids,omitempty"`
	Steps         []ChaosStep `json:"steps"`
}

// ChaosAppliedStep records what the harness executed for evidence.
type ChaosAppliedStep struct {
	Index     int    `json:"index"`
	Type      string `json:"type"`
	AdvanceMs uint64 `json:"advance_ms,omitempty"`
	Detail    string `json:"detail,omitempty"`
	Outcome   string `json:"outcome"`
}

// ChaosResult is deterministic developer test evidence, not an ops report.
type ChaosResult struct {
	CorrelationID          string             `json:"correlation_id"`
	ScenarioName           string             `json:"scenario_name"`
	AppliedSteps           []ChaosAppliedStep `json:"applied_steps"`
	VirtualTimeMs          uint64             `json:"virtual_time_ms"`
	CommittedTopologyCount int                `json:"committed_topology_count"`
	RejectedWriteCount     int                `json:"rejected_write_count"`
	AliveVoters            int                `json:"alive_voters"`
	Quorum                 int                `json:"quorum"`
	LeaderID               string             `json:"leader_id"`
	TopologyRevision       string             `json:"topology_revision"`
	DegradationLevel       string             `json:"degradation_level"`
	SafetyNotice           string             `json:"safety_notice"`
}

// RunChaosScenario executes a validated fixture against an in-process cluster.
func RunChaosScenario(scenario ChaosScenario) (*Cluster, ChaosResult, error) {
	if err := validateChaosScenario(scenario); err != nil {
		return nil, ChaosResult{}, err
	}
	cluster, err := NewClusterWithObservers(scenario.ClusterID, scenario.VoterIDs, scenario.ObserverIDs)
	if err != nil {
		return nil, ChaosResult{}, err
	}

	result := ChaosResult{
		CorrelationID: scenario.CorrelationID,
		ScenarioName:  scenario.Name,
		SafetyNotice:  "Fixture-only crash/omission chaos; not Byzantine-tolerant and not a recovery-time claim.",
	}

	for index, step := range scenario.Steps {
		applied, err := applyChaosStep(cluster, scenario, step, index)
		if err != nil {
			return cluster, result, err
		}
		if applied.Outcome == "rejected" {
			result.RejectedWriteCount++
		}
		if applied.Outcome == "committed" {
			result.CommittedTopologyCount++
		}
		result.AppliedSteps = append(result.AppliedSteps, applied)
	}

	result.VirtualTimeMs = cluster.Now
	result.AliveVoters = cluster.AliveVoters()
	result.Quorum = cluster.Quorum()
	result.LeaderID = cluster.LeaderID
	result.TopologyRevision = cluster.TopologyRevision
	result.DegradationLevel = string(cluster.Degradation.Level)
	return cluster, result, nil
}

func validateChaosScenario(scenario ChaosScenario) error {
	if strings.TrimSpace(scenario.Name) == "" {
		return errors.New("chaos scenario name is required")
	}
	if strings.TrimSpace(scenario.CorrelationID) == "" {
		return errors.New("chaos scenario correlation_id is required")
	}
	if strings.TrimSpace(scenario.ClusterID) == "" {
		return errors.New("chaos scenario cluster_id is required")
	}
	if len(scenario.Steps) == 0 {
		return errors.New("chaos scenario requires at least one step")
	}
	known := make(map[string]struct{}, len(scenario.VoterIDs)+len(scenario.ObserverIDs))
	for _, id := range append(append([]string(nil), scenario.VoterIDs...), scenario.ObserverIDs...) {
		known[id] = struct{}{}
	}
	for index, step := range scenario.Steps {
		if _, ok := allowedChaosFaults[step.Type]; !ok {
			return fmt.Errorf("step %d: unsupported chaos fault type %q", index, step.Type)
		}
		switch step.Type {
		case ChaosAdvance, ChaosDelayMarker:
			if step.AdvanceMs == 0 {
				return fmt.Errorf("step %d: %s requires a positive advance_ms", index, step.Type)
			}
		case ChaosCrash, ChaosRecover:
			if len(step.NodeIDs) != 1 {
				return fmt.Errorf("step %d: %s requires exactly one node_id", index, step.Type)
			}
			if _, ok := known[step.NodeIDs[0]]; !ok {
				return fmt.Errorf("step %d: unknown node %q", index, step.NodeIDs[0])
			}
		case ChaosPartition, ChaosHeal:
			if len(step.NodeIDs) == 0 {
				return fmt.Errorf("step %d: %s requires node_ids", index, step.Type)
			}
			for _, nodeID := range step.NodeIDs {
				if _, ok := known[nodeID]; !ok {
					return fmt.Errorf("step %d: unknown node %q", index, nodeID)
				}
			}
		case ChaosSubmitTopology:
			if len(step.Payload) == 0 || strings.TrimSpace(step.Actor) == "" || strings.TrimSpace(step.AuditEventRef) == "" {
				return fmt.Errorf("step %d: submit_topology requires actor, payload, and audit_event_ref", index)
			}
		case ChaosRejectInvalidMessage:
			if len(step.Payload) == 0 {
				return fmt.Errorf("step %d: reject_invalid_message requires a payload fixture", index)
			}
			if strings.TrimSpace(step.Actor) == "" {
				step.Actor = "DEMO-OPERATOR"
			}
		}
	}
	return nil
}

func applyChaosStep(cluster *Cluster, scenario ChaosScenario, step ChaosStep, index int) (ChaosAppliedStep, error) {
	applied := ChaosAppliedStep{Index: index, Type: step.Type, AdvanceMs: step.AdvanceMs}
	switch step.Type {
	case ChaosAdvance, ChaosDelayMarker:
		cluster.Advance(step.AdvanceMs)
		applied.Detail = fmt.Sprintf("virtual_time=%d", cluster.Now)
		applied.Outcome = "applied"
		return applied, nil
	case ChaosCrash:
		if err := cluster.Crash(step.NodeIDs[0]); err != nil {
			return applied, err
		}
		applied.Detail = step.NodeIDs[0]
		applied.Outcome = "applied"
		return applied, nil
	case ChaosRecover:
		if err := cluster.Recover(step.NodeIDs[0]); err != nil {
			return applied, err
		}
		applied.Detail = step.NodeIDs[0]
		applied.Outcome = "applied"
		return applied, nil
	case ChaosPartition:
		nodes := append([]string(nil), step.NodeIDs...)
		sort.Strings(nodes)
		if err := cluster.Isolate(nodes); err != nil {
			return applied, err
		}
		applied.Detail = strings.Join(nodes, ",")
		applied.Outcome = "applied"
		return applied, nil
	case ChaosHeal:
		if err := cluster.HealPartitions(); err != nil {
			return applied, err
		}
		applied.Detail = "healed"
		applied.Outcome = "applied"
		return applied, nil
	case ChaosSubmitTopology:
		actor := step.Actor
		if actor == "" {
			actor = "DEMO-OPERATOR"
		}
		_, err := cluster.SubmitTopologyRevision(scenario.CorrelationID, actor, step.Payload, step.AuditEventRef)
		if err != nil {
			applied.Detail = err.Error()
			applied.Outcome = "rejected"
			return applied, nil
		}
		applied.Detail = step.AuditEventRef
		applied.Outcome = "committed"
		return applied, nil
	case ChaosRejectInvalidMessage:
		actor := step.Actor
		if actor == "" {
			actor = "DEMO-OPERATOR"
		}
		ref := step.AuditEventRef
		if ref == "" {
			ref = fmt.Sprintf("evt_invalid_%d", index)
		}
		_, err := cluster.SubmitTopologyRevision(scenario.CorrelationID, actor, step.Payload, ref)
		if err == nil {
			return applied, errors.New("expected invalid payload to be rejected")
		}
		if !errors.Is(err, ErrInvalidTopologyPayload) && !errors.Is(err, ErrNoQuorum) && !errors.Is(err, ErrNoLeader) {
			// Still record rejection, but prefer validation boundary errors.
			applied.Detail = err.Error()
			applied.Outcome = "rejected"
			return applied, nil
		}
		applied.Detail = err.Error()
		applied.Outcome = "rejected"
		return applied, nil
	default:
		return applied, fmt.Errorf("unsupported chaos step %q", step.Type)
	}
}
