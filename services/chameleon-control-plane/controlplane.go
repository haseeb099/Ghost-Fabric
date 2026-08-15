// Package controlplane is an in-process Raft control-plane prototype.
//
// It is intentionally transport-free and does not authorize recovery actions.
// Production membership, TLS, and cross-region replication require the review
// gates recorded in docs/architecture/CHAMELEON_CONSENSUS_DECISION.md.
package controlplane

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
)

type Role string

const (
	Follower  Role = "follower"
	Candidate Role = "candidate"
	Leader    Role = "leader"
)

var (
	ErrNoLeader       = errors.New("no elected leader")
	ErrNoQuorum       = errors.New("control-plane write rejected: quorum unavailable")
	ErrRecoveryAction = errors.New("recovery approval cannot be committed by chameleon consensus")
)

// ControlEntry is a versioned topology/control state reference. It deliberately
// carries a hash and audit reference instead of executable recovery instructions.
type ControlEntry struct {
	SchemaVersion string `json:"schema_version"`
	ClusterID     string `json:"cluster_id"`
	Term          uint64 `json:"term"`
	Index         uint64 `json:"index"`
	CorrelationID string `json:"correlation_id"`
	EntryType     string `json:"entry_type"`
	Actor         string `json:"actor"`
	PayloadHash   string `json:"payload_hash"`
	AuditEventRef string `json:"audit_event_ref"`
}

type Node struct {
	ID               string
	Voter            bool
	Role             Role
	Alive            bool
	CurrentTerm      uint64
	VotedFor         string
	Log              []ControlEntry
	CommitIndex      uint64
	LastApplied      uint64
	ElectionDeadline uint64
}

type Snapshot struct {
	SchemaVersion     string `json:"schema_version"`
	ClusterID         string `json:"cluster_id"`
	LastIncludedIndex uint64 `json:"last_included_index"`
	LastIncludedTerm  uint64 `json:"last_included_term"`
	StateHash         string `json:"state_hash"`
	AuditChainHead    string `json:"audit_chain_head"`
}

// Cluster models an odd-voter, crash-fault-only regional control plane.
type Cluster struct {
	ID                string
	Nodes             map[string]*Node
	Now               uint64
	HeartbeatInterval uint64
	ElectionTimeouts  map[string]uint64
	LeaderID          string
	TopologyRevision  string
	AuditChainHead    string
	Health            map[string]HealthReport
	Edges             []MeshEdge
	RouteRevision     string
	LastRoutePlan     RoutePlan
	Features          []MeshFeature
	Degradation       DegradationState
	// PartitionOf maps node ID → partition label. Empty/nil means fully connected.
	// Same-label nodes can communicate; cross-label traffic is omitted.
	PartitionOf map[string]string
}

func NewCluster(id string, voterIDs []string) (*Cluster, error) {
	return NewClusterWithObservers(id, voterIDs, nil)
}

// NewClusterWithObservers creates an odd Raft voter set plus any number of
// non-voting observers. Observers receive committed topology state but never
// elect a leader or contribute to quorum.
func NewClusterWithObservers(id string, voterIDs []string, observerIDs []string) (*Cluster, error) {
	if len(voterIDs) < 3 || len(voterIDs)%2 == 0 {
		return nil, errors.New("cluster requires an odd voter count of at least three")
	}
	nodes := make(map[string]*Node, len(voterIDs)+len(observerIDs))
	timeouts := make(map[string]uint64, len(voterIDs))
	sorted := append([]string(nil), voterIDs...)
	sort.Strings(sorted)
	for index, nodeID := range sorted {
		if _, exists := nodes[nodeID]; exists {
			return nil, fmt.Errorf("duplicate node %q", nodeID)
		}
		nodes[nodeID] = &Node{
			ID:               nodeID,
			Voter:            true,
			Role:             Follower,
			Alive:            true,
			ElectionDeadline: uint64(1500 + index*300),
		}
		timeouts[nodeID] = uint64(1500 + index*300)
	}
	for _, nodeID := range observerIDs {
		if _, exists := nodes[nodeID]; exists {
			return nil, fmt.Errorf("duplicate node %q", nodeID)
		}
		nodes[nodeID] = &Node{
			ID:    nodeID,
			Voter: false,
			Role:  Follower,
			Alive: true,
		}
	}
	cluster := &Cluster{
		ID:                id,
		Nodes:             nodes,
		HeartbeatInterval: 250,
		ElectionTimeouts:  timeouts,
		Health:            make(map[string]HealthReport),
	}
	cluster.ensureFeatures()
	cluster.refreshDegradation()
	return cluster, nil
}

func (c *Cluster) Quorum() int {
	voters := 0
	for _, node := range c.Nodes {
		if node.Voter {
			voters++
		}
	}
	return voters/2 + 1
}

func (c *Cluster) AliveVoters() int {
	total := 0
	for _, node := range c.Nodes {
		if node.Voter && node.Alive {
			total++
		}
	}
	return total
}

// Advance deterministically drives election timeouts. The first eligible
// candidate wins when it receives a majority of currently available voters.
func (c *Cluster) Advance(milliseconds uint64) {
	c.Now += milliseconds
	if c.LeaderID != "" && c.Nodes[c.LeaderID].Alive {
		if c.reachableVoters(c.LeaderID) >= c.Quorum() {
			return
		}
		c.Nodes[c.LeaderID].Role = Follower
		c.LeaderID = ""
	}
	c.LeaderID = ""
	if c.AliveVoters() < c.Quorum() {
		return
	}

	candidates := make([]string, 0, len(c.Nodes))
	for id, node := range c.Nodes {
		if node.Voter && node.Alive && c.Now >= node.ElectionDeadline {
			candidates = append(candidates, id)
		}
	}
	sort.Strings(candidates)
	if len(candidates) == 0 {
		return
	}
	// Prefer a candidate that can already reach quorum in its partition.
	for _, candidateID := range candidates {
		if c.reachableVoters(candidateID) >= c.Quorum() {
			c.elect(candidateID)
			return
		}
	}
}

func (c *Cluster) elect(candidateID string) {
	candidate := c.Nodes[candidateID]
	candidate.Role = Candidate
	candidate.CurrentTerm++
	candidate.VotedFor = candidateID
	votes := 1

	for id, node := range c.Nodes {
		if id == candidateID || !node.Voter || !node.Alive || !c.canCommunicate(candidateID, id) {
			continue
		}
		if node.CurrentTerm <= candidate.CurrentTerm {
			node.CurrentTerm = candidate.CurrentTerm
			node.VotedFor = candidateID
			votes++
		}
	}
	if votes < c.Quorum() {
		candidate.Role = Follower
		return
	}
	for _, node := range c.Nodes {
		if !c.canCommunicate(candidateID, node.ID) {
			continue
		}
		if node.ID == candidateID {
			node.Role = Leader
		} else {
			node.Role = Follower
		}
		if node.Voter {
			node.ElectionDeadline = c.Now + c.ElectionTimeouts[node.ID]
		}
	}
	c.LeaderID = candidateID
}

func (c *Cluster) Crash(nodeID string) error {
	node, ok := c.Nodes[nodeID]
	if !ok {
		return fmt.Errorf("unknown node %q", nodeID)
	}
	node.Alive = false
	node.Role = Follower
	if c.LeaderID == nodeID {
		c.LeaderID = ""
	}
	if c.Health == nil {
		c.Health = make(map[string]HealthReport)
	}
	c.Health[nodeID] = ScoreHealth(nodeID, false, HealthSignals{})
	if len(c.Edges) > 0 {
		if _, err := c.RecalculateRoutes("mesh-loss", nodeID); err != nil {
			return err
		}
	} else {
		c.refreshDegradation()
	}
	return nil
}

func (c *Cluster) Recover(nodeID string) error {
	node, ok := c.Nodes[nodeID]
	if !ok {
		return fmt.Errorf("unknown node %q", nodeID)
	}
	node.Alive = true
	node.Role = Follower
	if node.Voter {
		node.ElectionDeadline = c.Now + c.ElectionTimeouts[nodeID]
	}
	if c.LeaderID != "" && c.Nodes[c.LeaderID].Alive {
		c.catchUp(node)
	}
	if c.Health == nil {
		c.Health = make(map[string]HealthReport)
	}
	c.Health[nodeID] = ScoreHealth(nodeID, true, HealthSignals{})
	if len(c.Edges) > 0 {
		if _, err := c.RecalculateRoutes("mesh-recover", ""); err != nil {
			return err
		}
	} else {
		c.refreshDegradation()
	}
	return nil
}

// SubmitTopologyRevision replicates a non-consequential topology reference.
// The write is committed only after an in-process majority acknowledgement.
func (c *Cluster) SubmitTopologyRevision(
	correlationID string,
	actor string,
	payload []byte,
	auditEventRef string,
) (ControlEntry, error) {
	if err := ValidateTopologyPayload(payload); err != nil {
		return ControlEntry{}, err
	}
	if c.LeaderID == "" || !c.Nodes[c.LeaderID].Alive {
		return ControlEntry{}, ErrNoLeader
	}
	if c.reachableVoters(c.LeaderID) < c.Quorum() {
		return ControlEntry{}, ErrNoQuorum
	}
	leader := c.Nodes[c.LeaderID]
	entry := ControlEntry{
		SchemaVersion: "1",
		ClusterID:     c.ID,
		Term:          leader.CurrentTerm,
		Index:         uint64(len(leader.Log) + 1),
		CorrelationID: correlationID,
		EntryType:     "topology.revision",
		Actor:         actor,
		PayloadHash:   hash(payload),
		AuditEventRef: auditEventRef,
	}

	acknowledgements := 0
	for _, nodeID := range c.reachableNodeIDs(c.LeaderID) {
		node := c.Nodes[nodeID]
		node.Log = append(node.Log, entry)
		if node.Voter {
			acknowledgements++
		}
	}
	if acknowledgements < c.Quorum() {
		return ControlEntry{}, ErrNoQuorum
	}
	for _, nodeID := range c.reachableNodeIDs(c.LeaderID) {
		node := c.Nodes[nodeID]
		node.CommitIndex = entry.Index
		node.LastApplied = entry.Index
	}
	c.TopologyRevision = entry.PayloadHash
	c.AuditChainHead = entry.AuditEventRef
	return entry, nil
}

// SubmitRecoveryApproval is intentionally prohibited: consensus cannot
// substitute for the existing authenticated human approval flow.
func (c *Cluster) SubmitRecoveryApproval() error {
	return ErrRecoveryAction
}

func (c *Cluster) Snapshot() (Snapshot, error) {
	if c.LeaderID == "" || !c.Nodes[c.LeaderID].Alive {
		return Snapshot{}, ErrNoLeader
	}
	leader := c.Nodes[c.LeaderID]
	serialized, err := json.Marshal(struct {
		TopologyRevision string `json:"topology_revision"`
		CommitIndex      uint64 `json:"commit_index"`
		AuditChainHead   string `json:"audit_chain_head"`
	}{
		TopologyRevision: c.TopologyRevision,
		CommitIndex:      leader.CommitIndex,
		AuditChainHead:   c.AuditChainHead,
	})
	if err != nil {
		return Snapshot{}, err
	}
	return Snapshot{
		SchemaVersion:     "1",
		ClusterID:         c.ID,
		LastIncludedIndex: leader.CommitIndex,
		LastIncludedTerm:  leader.CurrentTerm,
		StateHash:         hash(serialized),
		AuditChainHead:    c.AuditChainHead,
	}, nil
}

func (c *Cluster) catchUp(follower *Node) {
	leader := c.Nodes[c.LeaderID]
	follower.CurrentTerm = leader.CurrentTerm
	follower.Log = append([]ControlEntry(nil), leader.Log...)
	follower.CommitIndex = leader.CommitIndex
	follower.LastApplied = leader.LastApplied
}

func hash(value []byte) string {
	sum := sha256.Sum256(value)
	return hex.EncodeToString(sum[:])
}
