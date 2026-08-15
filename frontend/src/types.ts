export type NodeStatus = 'online' | 'degraded' | 'offline'
export type EventSeverity = 'info' | 'warning' | 'critical' | 'success'
export type Role = 'viewer' | 'operator'
export type DemoPhaseId =
  | 'baseline'
  | 'evidence_rising'
  | 'relay_interrupted'
  | 'tabletop_choice'
  | 'recovery_review'
  | 'workflow_restored'
  | 'complete'

export type FabricNode = {
  id: string
  callsign: string
  role: string
  capabilities?: string[]
  zone?: string
  x: number
  y: number
  latitude: number
  longitude: number
  status: NodeStatus
  is_coordinator: boolean
  latency_ms: number
  links: string[]
}

export type FabricEvent = {
  event_id: string
  correlation_id: string
  sequence: number
  scenario_time_ms: number
  wall_time: string
  source: string
  type: string
  severity: EventSeverity
  payload: Record<string, unknown>
  event_hash: string
}

export type DemoPhase = {
  id: DemoPhaseId
  index: number
  total: number
  title: string
  cue: string
  operator_hint: string
  label: string
  notice: string
}

export type PhoenixWorkflowState =
  | 'alert'
  | 'approval'
  | 'execution'
  | 'verify'
  | 'restored'
  | 'rollback'
  | 'failed'

export type Snapshot = {
  scenario: {
    id: string
    name: string
    classification: string
    correlation_id: string
    time_ms: number
    sequence: number
    speed: 1 | 2 | 4
    fixture_version?: string
    seed?: number
    event_chain_head?: string | null
    demo_phase?: DemoPhase
  }
  network: {
    nodes: FabricNode[]
    coordinator: string | null
    availability: number
    metrics: {
      connected_components: number
      components: string[][]
      active_links: number
      unavailable_links: string[][]
      coordinator_reachable_nodes: number
      alternate_routes: number
      routes: Record<string, string[]>
      calculation_ms: number
    }
  }
  prophet: {
    confidence: number
    state: 'nominal' | 'watch' | 'warning'
    signals: Array<{
      id: string
      label: string
      value: number
      unit: string
      trend: 'stable' | 'rising' | 'falling'
      contribution: number
    }>
    warning_window_minutes: number | null
    method: string
    telemetry: {
      fixture_id: string
      fixture_version: string
      sample_count: number
      pattern_onset_minute: number
      missing_data_samples: number
      false_positive_samples: number
      observed_events: number
      label_counts: Record<string, number>
      source?: string
      simulation_minute?: number
      current_sample?: {
        minute: number
        spectrum: number | null
        logistics: number | null
        network: number | null
        quality: 'complete' | 'partial'
        label: string
        event_observed: boolean
      }
      playback_note?: string
    }
    evidence: {
      thresholds: { watch: number; warning: number }
      confidence_interval: [number, number]
      uncertainty_points: number
      confirming_signal_count: number
      top_contributors: Array<{ id: string; label: string; contribution: number }>
      state: 'nominal' | 'watch' | 'warning'
      data_quality: 'complete' | 'partial'
      missing_data_policy: string
      false_positive_guardrail: string
      calibration: { fixture_id: string; fixture_version: string; method: string }
    }
    countdown?: {
      label: string
      pattern_onset_minute: number
      simulation_minute: number
      minutes_to_synthetic_event: number
      notice: string
    }
  }
  mirror: {
    scenario_id?: string
    scenario_name?: string
    classification?: string
    seed?: number
    decision_point_id?: string
    condition?: string
    awaiting_choice?: boolean
    completed?: boolean
    branches: Array<{
      id: string
      label: string
      outcome?: string
      assumption: string
      probability?: number
    }>
    selected_branch: string | null
    trace_events?: Array<{
      sequence: number
      virtual_time_ms: number
      event_type: string
      decision_point_id: string | null
      branch_id: string | null
      detail: string
      mode: string
    }>
    notice: string
  }
  citizen?: {
    schema_version: number
    label: string
    sensors_total: number
    sensors_online: number
    grid_survival_percent: number
    confirming_districts: number
    min_confirming_districts: number
    confidence: number
    state: 'listening' | 'corroborating' | 'confirmed'
    ready_for_warning: boolean
    warning_dispatched: boolean
    dispatch_channel: string | null
    synthetic_lead_seconds: number
    advisory_districts: string[]
    districts: Array<{ id: string; name: string; sensors_online: number; reporting: boolean }>
    channels: Array<{
      id: string
      label: string
      reach_percent: number
      status: 'available' | 'degraded' | 'jammed'
      active: boolean
    }>
    privacy: string
    notice: string
    guardrail: string
  }
  phoenix: {
    workflow_status: 'degraded' | 'restored' | 'failed' | 'in_progress'
    approved_option: string | null
    planner: {
      available_options: number
      ranking: string[]
      notice: string
    }
    workflow?: {
      workflow_id: string
      correlation_id: string
      state: PhoenixWorkflowState
      selected_option_id: string | null
      approval_actor: string | null
      transitions: Array<{
        sequence: number
        from_state: PhoenixWorkflowState
        to_state: PhoenixWorkflowState
        actor: string
        reason: string
      }>
    }
    options: Array<{
      id: string
      name: string
      route: string[]
      availability: number
      reliability: number
      latency_seconds: number
      reversibility: 'high' | 'medium' | 'low'
      rationale: string
      status: 'available' | 'recommended' | 'approved'
    }>
    approval_policy?: Record<string, number>
    pre_approved?: {
      schema_version: number
      label: string
      notice: string
      auto_execute: boolean
      templates: Array<{
        id: string
        severity_tier: string
        title: string
        when: string[]
        suggested_option_id: string | null
        bounded_effects: string[]
        requires_operator_confirm: boolean
        policy_id: string
      }>
    }
  }
  events: FabricEvent[]
}

export type HealthStatus = {
  status: string
  mode: string
  auth_mode: string
  api_version: string
  persistence: {
    backend?: string
    status?: string
    active_correlation_id?: string | null
  }
  components: Record<string, string>
}

export type AnalysisSummary = {
  mode: 'fixture' | 'provider'
  summary: string
  contributors: string[]
  uncertainty: string
  recommendation: string
}

export type SessionState = {
  token: string
  role: Role
  subject: string
}
