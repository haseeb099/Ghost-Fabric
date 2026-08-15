package controlplane

import (
	"encoding/json"
	"errors"
	"fmt"
	"sync"
)

var (
	ErrOperatorRoleRequired = errors.New("operator role required for topology commit")
	ErrRecoveryEntryType    = errors.New("recovery actions cannot be committed by chameleon")
)

// CanonicalEvent mirrors the backend EventEnvelope wire contract. The adapter
// writes only references and hashes: it never puts executable recovery data in
// the control-plane or audit payload.
type CanonicalEvent struct {
	EventID        string         `json:"event_id"`
	CorrelationID  string         `json:"correlation_id"`
	Sequence       uint64         `json:"sequence"`
	ScenarioTimeMs uint64         `json:"scenario_time_ms"`
	Source         string         `json:"source"`
	Type           string         `json:"type"`
	Severity       string         `json:"severity"`
	SchemaVersion  int            `json:"schema_version"`
	Payload        map[string]any `json:"payload"`
	PreviousHash   string         `json:"previous_hash"`
	EventHash      string         `json:"event_hash"`
	Actor          string         `json:"actor"`
	Role           string         `json:"role"`
}

// AuditEventSink is the Go boundary for the backend's canonical AuditStore.
// A transport-specific implementation belongs to a reviewed future adapter;
// this prototype provides an in-memory implementation for contract tests.
type AuditEventSink interface {
	AppendCanonicalEvent(event CanonicalEvent) error
}

// TopologyCommitRequest supplies the metadata required for an authenticated,
// non-consequential topology-reference commit.
type TopologyCommitRequest struct {
	CorrelationID  string
	Actor          string
	Role           string
	ScenarioTimeMs uint64
	Payload        []byte
}

// TopologyAuditAdapter preserves the canonical audit order:
// requested -> quorum commit -> committed/rejected. It does not invoke
// PHOENIX or otherwise authorize an external action.
type TopologyAuditAdapter struct {
	cluster      *Cluster
	sink         AuditEventSink
	nextSequence map[string]uint64
	lastHash     map[string]string
}

func NewTopologyAuditAdapter(cluster *Cluster, sink AuditEventSink) (*TopologyAuditAdapter, error) {
	if cluster == nil {
		return nil, errors.New("cluster is required")
	}
	if sink == nil {
		return nil, errors.New("canonical audit sink is required")
	}
	return &TopologyAuditAdapter{
		cluster:      cluster,
		sink:         sink,
		nextSequence: make(map[string]uint64),
		lastHash:     make(map[string]string),
	}, nil
}

// CommitTopology records the intent before consensus and records the terminal
// outcome after it. The returned entry is a topology reference only.
func (a *TopologyAuditAdapter) CommitTopology(request TopologyCommitRequest) (ControlEntry, error) {
	if request.Role != "operator" {
		return ControlEntry{}, ErrOperatorRoleRequired
	}
	if request.Actor == "" || request.CorrelationID == "" {
		return ControlEntry{}, errors.New("actor and correlation ID are required")
	}

	payloadHash := hash(request.Payload)
	requested, err := a.append(request, "chameleon.topology_revision_requested", "info", map[string]any{
		"payload_hash": payloadHash,
	})
	if err != nil {
		return ControlEntry{}, err
	}

	entry, err := a.cluster.SubmitTopologyRevision(
		request.CorrelationID,
		request.Actor,
		request.Payload,
		requested.EventID,
	)
	if err != nil {
		if appendErr := a.appendTerminal(request, "chameleon.topology_revision_rejected", "warning", payloadHash, err); appendErr != nil {
			return ControlEntry{}, appendErr
		}
		return ControlEntry{}, err
	}

	if _, err := a.append(request, "chameleon.topology_revision_committed", "success", map[string]any{
		"raft_term":       entry.Term,
		"raft_index":      entry.Index,
		"payload_hash":    entry.PayloadHash,
		"audit_event_ref": entry.AuditEventRef,
	}); err != nil {
		return ControlEntry{}, err
	}
	return entry, nil
}

// CommitRecoveryAction always rejects the call before it reaches consensus.
func (a *TopologyAuditAdapter) CommitRecoveryAction() error {
	return ErrRecoveryEntryType
}

func (a *TopologyAuditAdapter) appendTerminal(
	request TopologyCommitRequest,
	eventType string,
	severity string,
	payloadHash string,
	commitErr error,
) error {
	_, err := a.append(request, eventType, severity, map[string]any{
		"payload_hash": payloadHash,
		"reason":       commitErr.Error(),
	})
	return err
}

func (a *TopologyAuditAdapter) append(
	request TopologyCommitRequest,
	eventType string,
	severity string,
	payload map[string]any,
) (CanonicalEvent, error) {
	sequence := a.nextSequence[request.CorrelationID] + 1
	event := CanonicalEvent{
		EventID:        fmt.Sprintf("evt_chameleon_%s", hash([]byte(fmt.Sprintf("%s:%d:%s", request.CorrelationID, sequence, eventType)))[:16]),
		CorrelationID:  request.CorrelationID,
		Sequence:       sequence,
		ScenarioTimeMs: request.ScenarioTimeMs,
		Source:         "chameleon-control-plane",
		Type:           eventType,
		Severity:       severity,
		SchemaVersion:  1,
		Payload:        payload,
		PreviousHash:   a.lastHash[request.CorrelationID],
		Actor:          request.Actor,
		Role:           request.Role,
	}
	serialized, err := json.Marshal(struct {
		EventID        string         `json:"event_id"`
		CorrelationID  string         `json:"correlation_id"`
		Sequence       uint64         `json:"sequence"`
		ScenarioTimeMs uint64         `json:"scenario_time_ms"`
		Source         string         `json:"source"`
		Type           string         `json:"type"`
		Severity       string         `json:"severity"`
		SchemaVersion  int            `json:"schema_version"`
		Payload        map[string]any `json:"payload"`
		PreviousHash   string         `json:"previous_hash"`
		Actor          string         `json:"actor"`
		Role           string         `json:"role"`
	}{
		EventID: event.EventID, CorrelationID: event.CorrelationID, Sequence: event.Sequence,
		ScenarioTimeMs: event.ScenarioTimeMs, Source: event.Source, Type: event.Type,
		Severity: event.Severity, SchemaVersion: event.SchemaVersion, Payload: event.Payload,
		PreviousHash: event.PreviousHash, Actor: event.Actor, Role: event.Role,
	})
	if err != nil {
		return CanonicalEvent{}, err
	}
	event.EventHash = hash(serialized)
	if err := a.sink.AppendCanonicalEvent(event); err != nil {
		return CanonicalEvent{}, err
	}
	a.nextSequence[request.CorrelationID] = sequence
	a.lastHash[request.CorrelationID] = event.EventHash
	return event, nil
}

// MemoryAuditEventSink is only a test/fixture implementation of the adapter
// boundary. Production integration must write through the backend AuditStore.
type MemoryAuditEventSink struct {
	mu     sync.Mutex
	events []CanonicalEvent
}

func (s *MemoryAuditEventSink) AppendCanonicalEvent(event CanonicalEvent) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, existing := range s.events {
		if existing.CorrelationID == event.CorrelationID && existing.Sequence == event.Sequence {
			return fmt.Errorf("duplicate sequence %d for %s", event.Sequence, event.CorrelationID)
		}
	}
	s.events = append(s.events, event)
	return nil
}

func (s *MemoryAuditEventSink) Events() []CanonicalEvent {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]CanonicalEvent(nil), s.events...)
}
