package controlplane

import (
	"fmt"
	"sort"
)

// Isolate places the listed nodes into a separate live partition. Nodes remain
// Alive but cannot exchange votes or append acknowledgements across the cut.
// This is distinct from Crash, which removes a node entirely.
func (c *Cluster) Isolate(nodeIDs []string) error {
	if len(nodeIDs) == 0 {
		return fmt.Errorf("isolate requires at least one node")
	}
	if c.PartitionOf == nil {
		c.PartitionOf = make(map[string]string, len(c.Nodes))
	}
	for id := range c.Nodes {
		c.PartitionOf[id] = "majority"
	}
	for _, nodeID := range nodeIDs {
		if _, ok := c.Nodes[nodeID]; !ok {
			return fmt.Errorf("unknown node %q", nodeID)
		}
		c.PartitionOf[nodeID] = "isolated"
	}
	if c.LeaderID != "" && c.reachableVoters(c.LeaderID) < c.Quorum() {
		if leader := c.Nodes[c.LeaderID]; leader != nil {
			leader.Role = Follower
		}
		c.LeaderID = ""
		for id, node := range c.Nodes {
			if node.Voter && node.Alive && c.PartitionOf[id] == "majority" {
				node.ElectionDeadline = c.Now
			}
		}
	}
	c.refreshDegradation()
	return nil
}

// HealPartitions restores full connectivity and catches up alive followers.
func (c *Cluster) HealPartitions() error {
	c.PartitionOf = nil
	if c.LeaderID != "" && c.Nodes[c.LeaderID] != nil && c.Nodes[c.LeaderID].Alive {
		for _, node := range c.Nodes {
			if node.ID == c.LeaderID || !node.Alive {
				continue
			}
			c.catchUp(node)
		}
	}
	c.refreshDegradation()
	return nil
}

func (c *Cluster) canCommunicate(a, b string) bool {
	if a == b {
		return true
	}
	if c.PartitionOf == nil {
		return true
	}
	left := c.PartitionOf[a]
	right := c.PartitionOf[b]
	if left == "" {
		left = "majority"
	}
	if right == "" {
		right = "majority"
	}
	return left == right
}

func (c *Cluster) reachableVoters(from string) int {
	total := 0
	for id, node := range c.Nodes {
		if node.Voter && node.Alive && c.canCommunicate(from, id) {
			total++
		}
	}
	return total
}

func (c *Cluster) reachableNodeIDs(from string) []string {
	ids := make([]string, 0, len(c.Nodes))
	for id, node := range c.Nodes {
		if node.Alive && c.canCommunicate(from, id) {
			ids = append(ids, id)
		}
	}
	sort.Strings(ids)
	return ids
}
