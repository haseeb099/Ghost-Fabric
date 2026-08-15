# Value prop — Telecom carriers (GF-24)

## Problem

Regional PoP or coordinator loss creates opaque handoffs. NOC tools show symptoms; they rarely give a shared, auditable story of topology change → decision → restore.

## Solution

Ghost Fabric gives operators a **live mesh view**, **route recomputation telemetry**, **role-gated recovery approval**, and **WebSocket resume** so a reconnect does not invent state.

## Why us (now)

- Connected-component and alternate-route metrics on failure.  
- Shared mission timeline + exportable audit.  
- Fixture mode if control plane or AI explanation path degrades.  
- Compose-ready local/pilot stack (API + Postgres + console).

## Pilot ask

Joint NOC tabletop: inject node loss on a fictional mesh mirroring their *roles* (not production inventory), measure operator time-to-approval and audit completeness.

## Claims discipline

Failover latency targets on the enterprise roadmap remain **engineering goals** until load-tested in the customer environment.
