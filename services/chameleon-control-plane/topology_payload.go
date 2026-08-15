package controlplane

import (
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

// ErrInvalidTopologyPayload is returned when a fixture message fails the
// non-executable topology validation boundary. This is not Byzantine
// tolerance: invalid inputs are rejected before consensus.
var ErrInvalidTopologyPayload = errors.New("invalid topology payload rejected at validation boundary")

var prohibitedTopologyKeys = []string{
	"recovery",
	"recovery_command",
	"approve",
	"execute",
	"weapon",
	"target",
	"credential",
	"token",
	"secret",
}

// ValidateTopologyPayload enforces the fixture-only topology contract.
// Corrupt JSON, empty bodies, and recovery-shaped fields are rejected.
func ValidateTopologyPayload(payload []byte) error {
	if len(payload) == 0 {
		return fmt.Errorf("%w: payload is empty", ErrInvalidTopologyPayload)
	}
	var decoded map[string]any
	if err := json.Unmarshal(payload, &decoded); err != nil {
		return fmt.Errorf("%w: corrupt json: %v", ErrInvalidTopologyPayload, err)
	}
	if len(decoded) == 0 {
		return fmt.Errorf("%w: payload object is empty", ErrInvalidTopologyPayload)
	}
	for key := range decoded {
		normalized := strings.ToLower(strings.TrimSpace(key))
		for _, prohibited := range prohibitedTopologyKeys {
			if normalized == prohibited || strings.Contains(normalized, prohibited) {
				return fmt.Errorf("%w: prohibited field %q", ErrInvalidTopologyPayload, key)
			}
		}
	}
	if _, ok := decoded["revision"]; !ok {
		if _, ok := decoded["nodes"]; !ok {
			if _, ok := decoded["topology"]; !ok {
				return fmt.Errorf("%w: expected revision, nodes, or topology reference", ErrInvalidTopologyPayload)
			}
		}
	}
	return nil
}
