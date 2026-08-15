package controlplane

import (
	"encoding/json"
	"errors"
	"fmt"
	"sort"
)

var (
	ErrUnknownEdge = errors.New("unknown mesh edge")
	ErrNoRoutePath = errors.New("no alternate route available")
	ErrUnknownNode = errors.New("unknown mesh node")
)

// MeshEdge is an undirected adjacency between two mesh nodes.
type MeshEdge struct {
	A string `json:"a"`
	B string `json:"b"`
}

// RoutePlan is a deterministic recalculation result after node loss. Timing
// fields, when present, are fixture-labeled in-process observations only.
type RoutePlan struct {
	SchemaVersion string     `json:"schema_version"`
	CorrelationID string     `json:"correlation_id"`
	LostNode      string     `json:"lost_node"`
	ActiveNodes   []string   `json:"active_nodes"`
	Paths         [][]string `json:"paths"`
	Revision      string     `json:"revision"`
}

// SetMeshEdges replaces the undirected adjacency used for route recalculation.
func (c *Cluster) SetMeshEdges(edges []MeshEdge) error {
	normalized := make([]MeshEdge, 0, len(edges))
	seen := make(map[string]struct{}, len(edges))
	for _, edge := range edges {
		if edge.A == "" || edge.B == "" || edge.A == edge.B {
			return fmt.Errorf("%w: %v", ErrUnknownEdge, edge)
		}
		if _, ok := c.Nodes[edge.A]; !ok {
			return fmt.Errorf("%w: %s", ErrUnknownNode, edge.A)
		}
		if _, ok := c.Nodes[edge.B]; !ok {
			return fmt.Errorf("%w: %s", ErrUnknownNode, edge.B)
		}
		a, b := edge.A, edge.B
		if b < a {
			a, b = b, a
		}
		key := a + "|" + b
		if _, exists := seen[key]; exists {
			continue
		}
		seen[key] = struct{}{}
		normalized = append(normalized, MeshEdge{A: a, B: b})
	}
	sort.Slice(normalized, func(i, j int) bool {
		if normalized[i].A == normalized[j].A {
			return normalized[i].B < normalized[j].B
		}
		return normalized[i].A < normalized[j].A
	})
	c.Edges = normalized
	return nil
}

// RecalculateRoutes builds shortest paths between all alive node pairs after
// excluding a lost node. This is control-plane topology state only; it does
// not authorize recovery or external action.
func (c *Cluster) RecalculateRoutes(correlationID string, lostNode string) (RoutePlan, error) {
	if lostNode != "" {
		if _, ok := c.Nodes[lostNode]; !ok {
			return RoutePlan{}, fmt.Errorf("%w: %s", ErrUnknownNode, lostNode)
		}
	}

	active := make([]string, 0, len(c.Nodes))
	for id, node := range c.Nodes {
		if node.Alive && id != lostNode {
			active = append(active, id)
		}
	}
	sort.Strings(active)

	adjacency := c.aliveAdjacency(lostNode)
	paths := make([][]string, 0)
	for i := 0; i < len(active); i++ {
		for j := i + 1; j < len(active); j++ {
			path := shortestPath(adjacency, active[i], active[j])
			if path == nil {
				continue
			}
			paths = append(paths, path)
		}
	}

	payload, err := json.Marshal(struct {
		LostNode    string     `json:"lost_node"`
		ActiveNodes []string   `json:"active_nodes"`
		Paths       [][]string `json:"paths"`
	}{
		LostNode:    lostNode,
		ActiveNodes: active,
		Paths:       paths,
	})
	if err != nil {
		return RoutePlan{}, err
	}

	plan := RoutePlan{
		SchemaVersion: "1",
		CorrelationID: correlationID,
		LostNode:      lostNode,
		ActiveNodes:   active,
		Paths:         paths,
		Revision:      hash(payload),
	}
	c.RouteRevision = plan.Revision
	c.LastRoutePlan = plan
	c.refreshDegradation()
	return plan, nil
}

func (c *Cluster) aliveAdjacency(exclude string) map[string][]string {
	adj := make(map[string][]string)
	for _, edge := range c.Edges {
		if edge.A == exclude || edge.B == exclude {
			continue
		}
		aAlive := c.Nodes[edge.A] != nil && c.Nodes[edge.A].Alive
		bAlive := c.Nodes[edge.B] != nil && c.Nodes[edge.B].Alive
		if !aAlive || !bAlive {
			continue
		}
		adj[edge.A] = append(adj[edge.A], edge.B)
		adj[edge.B] = append(adj[edge.B], edge.A)
	}
	for id := range adj {
		sort.Strings(adj[id])
	}
	return adj
}

func shortestPath(adjacency map[string][]string, start, goal string) []string {
	if start == goal {
		return []string{start}
	}
	type frame struct {
		node string
		path []string
	}
	queue := []frame{{node: start, path: []string{start}}}
	visited := map[string]struct{}{start: {}}
	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		for _, next := range adjacency[current.node] {
			if _, seen := visited[next]; seen {
				continue
			}
			nextPath := append(append([]string{}, current.path...), next)
			if next == goal {
				return nextPath
			}
			visited[next] = struct{}{}
			queue = append(queue, frame{node: next, path: nextPath})
		}
	}
	return nil
}
