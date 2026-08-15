import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  BrainCircuit,
  CircleOff,
  Clock3,
  Database,
  Download,
  HeartPulse,
  HelpCircle,
  KeyRound,
  Network,
  Pause,
  Play,
  RefreshCcw,
  Terminal,
  Wifi,
  WifiOff,
  Zap,
} from 'lucide-react'
import {
  apiCommand,
  apiGet,
  canMutate,
  confirmDestructive,
  fetchAnalysis,
  fetchAuditExport,
  fetchHealth,
  fetchSnapshot,
  loadSession,
  saveSession,
} from './api'
import { CitizenGridPanel } from './components/CitizenGridPanel'
import { DemoPhaseBanner } from './components/DemoPhaseBanner'
import { FirstRunGuide } from './components/FirstRunGuide'
import { MirrorPanel } from './components/MirrorPanel'
import { PanelHeader, StatusPill } from './components/PanelChrome'
import { PhoenixPanel } from './components/PhoenixPanel'
import { ProphetPanel } from './components/ProphetPanel'
import { fixtureSnapshot } from './fixtureSnapshot'
import type { AnalysisSummary, EventSeverity, FabricEvent, HealthStatus, SessionState, Snapshot } from './types'

const TacticalMap = lazy(() => import('./TacticalMap'))

function formatMissionTime(milliseconds: number) {
  const totalSeconds = Math.floor(milliseconds / 1000)
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0')
  const seconds = (totalSeconds % 60).toString().padStart(2, '0')
  return `T+${minutes}:${seconds}`
}

function humanizeEvent(value: string) {
  return value.replaceAll('.', ' / ').replaceAll('_', ' ').toUpperCase()
}

function App() {
  const [snapshot, setSnapshot] = useState<Snapshot>(fixtureSnapshot)
  const [connection, setConnection] = useState<'connecting' | 'live' | 'fixture'>('connecting')
  const [busy, setBusy] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [notice, setNotice] = useState('Deterministic fixture ready.')
  const [replaySequence, setReplaySequence] = useState<number | null>(null)
  const [timelineSource, setTimelineSource] = useState<'all' | FabricEvent['source']>('all')
  const [timelineSeverity, setTimelineSeverity] = useState<'all' | EventSeverity>('all')
  const [session, setSession] = useState<SessionState>(() => loadSession())
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [analysisMode, setAnalysisMode] = useState<'fixture' | 'provider' | 'unknown'>('unknown')
  const [guideOpen, setGuideOpen] = useState(false)
  const latestScenario = useRef(snapshot.scenario)
  const replaySequenceRef = useRef<number | null>(null)
  const sessionRef = useRef(session)
  const operatorEnabled = connection === 'live' && canMutate(session.role) && replaySequence === null

  useEffect(() => {
    latestScenario.current = snapshot.scenario
  }, [snapshot.scenario])

  useEffect(() => {
    replaySequenceRef.current = replaySequence
  }, [replaySequence])

  useEffect(() => {
    sessionRef.current = session
    saveSession(session)
  }, [session])

  const refreshMeta = useCallback(async (token: string) => {
    try {
      const [nextHealth, analysis] = await Promise.all([
        fetchHealth(token),
        fetchAnalysis(token).catch(() => null as AnalysisSummary | null),
      ])
      setHealth(nextHealth)
      if (analysis) setAnalysisMode(analysis.mode)
    } catch {
      setHealth(null)
    }
  }, [])

  const loadSnapshot = useCallback(async () => {
    try {
      const next = await fetchSnapshot(sessionRef.current.token)
      setSnapshot(next)
      setConnection('live')
      setNotice('Simulation API synchronized.')
      await refreshMeta(sessionRef.current.token)
    } catch {
      setSnapshot(fixtureSnapshot)
      setConnection('fixture')
      setNotice('Backend offline — local fixture mode active.')
    }
  }, [refreshMeta])

  useEffect(() => {
    void loadSnapshot()
    let socket: WebSocket | undefined
    let reconnectTimer: number | undefined
    let disposed = false

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const { correlation_id: correlationId, sequence } = latestScenario.current
      const params = new URLSearchParams({
        correlation_id: correlationId,
        after_sequence: String(sequence),
      })
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/events?${params}`)
      socket.onopen = () => setConnection('live')
      socket.onmessage = (message) => {
        const data = JSON.parse(message.data) as {
          kind?: 'snapshot' | 'resume' | 'event'
          from_sequence?: number
          events?: FabricEvent[]
          snapshot?: Snapshot
        }
        if (data.snapshot && replaySequenceRef.current === null) {
          setSnapshot(data.snapshot)
          if (data.kind === 'resume' && data.events) {
            setNotice(`Live stream resumed: #${data.from_sequence ?? 0} → #${data.snapshot.scenario.sequence}.`)
          }
        }
      }
      socket.onerror = () => setConnection('fixture')
      socket.onclose = () => {
        if (!disposed) {
          setConnection('connecting')
          reconnectTimer = window.setTimeout(connect, 1000)
        }
      }
    }
    connect()

    return () => {
      disposed = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [loadSnapshot])

  const command = useCallback(async (label: string, path: string, options?: RequestInit) => {
    if (!canMutate(sessionRef.current.role)) {
      setNotice('Viewer role cannot mutate the scenario. Switch to an operator token.')
      return null
    }
    setBusy(label)
    try {
      const next = await apiCommand<Snapshot>(path, sessionRef.current.token, options)
      setSnapshot(next)
      setNotice(`${label} completed and audited as ${sessionRef.current.subject}.`)
      await refreshMeta(sessionRef.current.token)
      return next
    } catch {
      setNotice(`${label} requires the simulation API. Start the backend to enable controls.`)
      setConnection('fixture')
      return null
    } finally {
      setBusy(null)
    }
  }, [refreshMeta])

  const runApprovedRecovery = useCallback(async (optionId: string, optionName: string) => {
    if (!confirmDestructive(`Approve recovery option ${optionName}? Human confirmation is required before simulated execution.`)) {
      return
    }
    const approved = await command('Recovery approval', '/phoenix/approve', {
      method: 'POST',
      body: JSON.stringify({ option_id: optionId }),
    })
    if (!approved) return
    const executed = await command('Simulated execution', '/phoenix/execute', { method: 'POST' })
    if (!executed) return
    await command('Simulation verification', '/phoenix/verify', {
      method: 'POST',
      body: JSON.stringify({ succeeded: true }),
    })
  }, [command])

  const replayEvent = useCallback(async (sequence: number) => {
    setBusy(`Replay #${sequence}`)
    try {
      const next = await apiGet<Snapshot>(`/scenario/replay/${sequence}`, sessionRef.current.token)
      setPlaying(false)
      setSnapshot(next)
      setReplaySequence(sequence)
      setNotice(`Historical checkpoint #${sequence} loaded. Live updates are paused.`)
    } catch {
      setNotice('Replay checkpoint unavailable. The active run may have been reset.')
    } finally {
      setBusy(null)
    }
  }, [])

  const returnToLive = useCallback(async () => {
    setBusy('Return live')
    try {
      const next = await fetchSnapshot(sessionRef.current.token)
      setReplaySequence(null)
      setSnapshot(next)
      setNotice('Returned to the current live scenario state.')
    } catch {
      setNotice('Live scenario is unavailable. Fixture state remains visible.')
    } finally {
      setBusy(null)
    }
  }, [])

  useEffect(() => {
    if (!playing || connection !== 'live' || replaySequence !== null || !canMutate(session.role)) return
    const interval = window.setInterval(() => {
      void command('Advance scenario', '/scenario/advance', {
        method: 'POST',
        body: JSON.stringify({ seconds: 5 }),
      })
    }, 1800)
    return () => window.clearInterval(interval)
  }, [command, connection, playing, replaySequence, session.role])

  const coordinator = snapshot.network.nodes.find((node) => node.is_coordinator)
  const visibleEvents = useMemo(
    () =>
      snapshot.events
        .slice()
        .reverse()
        .filter(
          (event) =>
            (timelineSource === 'all' || event.source === timelineSource) &&
            (timelineSeverity === 'all' || event.severity === timelineSeverity),
        ),
    [snapshot.events, timelineSeverity, timelineSource],
  )
  const activeRecovery =
    snapshot.phoenix.options.find((option) => option.status === 'approved') ??
    snapshot.phoenix.options.find((option) => option.status === 'recommended') ??
    snapshot.phoenix.options[0]
  const availableNodes = snapshot.network.nodes.filter((node) => node.status !== 'offline').length
  const telemetrySample = snapshot.prophet.telemetry.current_sample
  const responsePriority =
    snapshot.network.availability < 100
      ? `Reconnect priority: review ${activeRecovery?.name ?? 'restore options'}; no route switch without operator approval.`
      : snapshot.prophet.state === 'warning'
        ? 'Link degradation confirmed by three signals — convene a human review before any restore.'
        : snapshot.prophet.state === 'watch'
          ? 'Link degradation developing; increase reporting cadence. No automatic action is authorized.'
          : 'Mesh nominal — maintain watch and validate the next labeled sample.'

  const exportAudit = useCallback(async () => {
    setBusy('Export audit')
    try {
      const audit = await fetchAuditExport(sessionRef.current.token)
      const blob = new Blob([JSON.stringify(audit, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `ghost-fabric-audit-${String(audit.correlation_id)}.json`
      link.click()
      URL.revokeObjectURL(url)
      setNotice(`Append-only audit exported: ${String(audit.event_count)} records.`)
    } catch {
      setNotice('Audit export requires the simulation API.')
    } finally {
      setBusy(null)
    }
  }, [])

  const applySessionPreset = useCallback(
    (preset: 'optional' | 'operator' | 'viewer') => {
      const next =
        preset === 'optional'
          ? { token: '', role: 'operator' as const, subject: 'DEMO-OPERATOR' }
          : preset === 'operator'
            ? { token: 'operator-token', role: 'operator' as const, subject: 'DEMO-OPERATOR' }
            : { token: 'viewer-token', role: 'viewer' as const, subject: 'DEMO-VIEWER' }
      setSession(next)
      setNotice(`Session set to ${next.subject} (${next.role}).`)
      window.setTimeout(() => {
        void loadSnapshot()
      }, 0)
    },
    [loadSnapshot],
  )

  return (
    <div className="console">
      <FirstRunGuide forceOpen={guideOpen} onClose={() => setGuideOpen(false)} />
      <a className="skip-link" href="#main-console">
        Skip to simulation controls
      </a>
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <p className="eyebrow">EDGE C2 CONTINUUM · CONTESTED COMMS</p>
            <h1>
              GHOST <b>FABRIC</b>
            </h1>
          </div>
        </div>

        <div className="mission-ident">
          <span>SIMULATION</span>
          <strong>{snapshot.scenario.name}</strong>
          <code>{snapshot.scenario.correlation_id}</code>
        </div>

        <div className="system-strip">
          <StatusPill
            icon={connection === 'live' ? <Wifi size={14} /> : <WifiOff size={14} />}
            label={
              replaySequence !== null
                ? `REPLAY #${replaySequence}`
                : connection === 'live'
                  ? 'API LIVE'
                  : connection === 'connecting'
                    ? 'CONNECTING'
                    : 'FIXTURE MODE'
            }
            tone={connection === 'live' ? 'ok' : 'warn'}
          />
          <StatusPill
            icon={<Network size={14} />}
            label={`${snapshot.network.availability}% MESH`}
            tone={snapshot.network.availability === 100 ? 'ok' : 'warn'}
          />
          <StatusPill
            icon={<KeyRound size={14} />}
            label={`${session.role.toUpperCase()} · ${session.subject}`}
            tone={canMutate(session.role) ? 'ok' : 'warn'}
          />
          <StatusPill
            icon={<Database size={14} />}
            label={
              health
                ? `${(health.persistence.backend ?? 'memory').toUpperCase()} · ${health.status.toUpperCase()}`
                : 'HEALTH UNKNOWN'
            }
            tone={health?.status === 'healthy' ? 'ok' : 'warn'}
          />
          <StatusPill
            icon={<BrainCircuit size={14} />}
            label={`AI ${analysisMode.toUpperCase()}`}
            tone={analysisMode === 'fixture' || analysisMode === 'provider' ? 'ok' : 'warn'}
          />
          <div className="mission-clock" aria-label={`Mission time ${formatMissionTime(snapshot.scenario.time_ms)}`}>
            <Clock3 size={15} />
            <strong>{formatMissionTime(snapshot.scenario.time_ms)}</strong>
          </div>
        </div>
      </header>

      <div className="session-bar" aria-label="Operator session controls">
        <span>
          <KeyRound size={13} /> SESSION
        </span>
        <button type="button" className={!session.token ? 'active' : ''} onClick={() => applySessionPreset('optional')}>
          LOCAL OPTIONAL
        </button>
        <button
          type="button"
          className={session.token === 'operator-token' ? 'active' : ''}
          onClick={() => applySessionPreset('operator')}
        >
          OPERATOR TOKEN
        </button>
        <button
          type="button"
          className={session.token === 'viewer-token' ? 'active' : ''}
          onClick={() => applySessionPreset('viewer')}
        >
          VIEWER TOKEN
        </button>
        <button type="button" className="guide-trigger" onClick={() => setGuideOpen(true)}>
          <HelpCircle size={13} /> WHAT IS THIS?
        </button>
        <small>{canMutate(session.role) ? 'Mutations enabled' : 'Read-only viewer'}</small>
      </div>

      <div className="safety-ribbon">
        <span>FICTIONAL TRAINING ENVIRONMENT</span>
        <p>
          Synthetic data · human approval required · friendly-network continuity only · no targeting, geolocation, or
          weapons
        </p>
        <span>SCHEMA V1</span>
      </div>

      <DemoPhaseBanner phase={snapshot.scenario.demo_phase} />

      <section className="situation-brief" aria-label="Simulation situation brief">
        <div className="brief-lead">
          <span>
            <HeartPulse size={14} /> SAFE NEXT STEP
          </span>
          <strong>{responsePriority}</strong>
          <small>Decision support only · confirm through an independent channel</small>
        </div>
        <div>
          <span>C2 CONTINUITY</span>
          <strong>
            {availableNodes}/{snapshot.network.nodes.length} NODES REACHABLE
          </strong>
          <small>
            {snapshot.network.metrics.connected_components === 1
              ? 'Single connected mesh'
              : `${snapshot.network.metrics.connected_components} partitions — unit is split`}{' '}
            · {snapshot.network.metrics.active_links} active links
          </small>
        </div>
        <div>
          <span>LINK DEGRADATION EVIDENCE</span>
          <strong>
            {snapshot.prophet.confidence}% · {snapshot.prophet.evidence.confidence_interval[0]}–
            {snapshot.prophet.evidence.confidence_interval[1]}% RANGE
          </strong>
          <small>
            {snapshot.prophet.evidence.confirming_signal_count}/3 confirming signals ·{' '}
            {snapshot.prophet.evidence.data_quality} quality
          </small>
        </div>
        <div className="brief-provenance">
          <span>
            <Database size={13} /> TEST DATA PROVENANCE
          </span>
          <strong>
            {telemetrySample
              ? `T${telemetrySample.minute} MIN · ${telemetrySample.label.replaceAll('_', ' ').toUpperCase()}`
              : 'LABELED FIXTURE'}
          </strong>
          <small>
            {snapshot.prophet.telemetry.fixture_id} v{snapshot.prophet.telemetry.fixture_version} · seed{' '}
            {snapshot.scenario.seed}
          </small>
        </div>
      </section>

      <main className="workspace" id="main-console" tabIndex={-1}>
        <section className="map-section" aria-labelledby="chameleon-title">
          <PanelHeader
            index="01"
            title="CHAMELEON"
            subtitle="Tactical mesh · coordinator handoff"
            icon={<Network size={17} />}
            status={coordinator ? `${coordinator.callsign} coordinating` : 'No coordinator'}
          />

          <div className="map-stage">
            <Suspense
              fallback={
                <div className="map-loading">
                  <Activity className="spin" size={18} /> LOADING PUBLIC BASEMAP
                </div>
              }
            >
              <TacticalMap nodes={snapshot.network.nodes} routes={snapshot.network.metrics.routes} />
            </Suspense>
          </div>

          <div className="route-telemetry" aria-label="Mesh routing telemetry">
            <div>
              <span>PARTITIONS</span>
              <strong>
                {snapshot.network.metrics.connected_components === 1
                  ? 'NONE'
                  : `${snapshot.network.metrics.connected_components} SPLIT`}
              </strong>
            </div>
            <div>
              <span>ACTIVE LINKS</span>
              <strong>{snapshot.network.metrics.active_links}</strong>
            </div>
            <div>
              <span>COORDINATOR REACH</span>
              <strong>
                {snapshot.network.metrics.coordinator_reachable_nodes}/
                {snapshot.network.nodes.filter((node) => node.status !== 'offline').length}
              </strong>
            </div>
            <div>
              <span>ALTERNATE ROUTES</span>
              <strong>{snapshot.network.metrics.alternate_routes}</strong>
            </div>
            <div>
              <span>SOLVE TIME</span>
              <strong>{snapshot.network.metrics.calculation_ms.toFixed(3)} MS</strong>
            </div>
          </div>

          <div className="module-action">
            <div>
              <p>COORDINATING NODE</p>
              <strong>{coordinator?.callsign ?? 'NO COORDINATOR — UNIT UNCOORDINATED'}</strong>
              <span>{coordinator?.role ?? 'Manual recovery required'}</span>
            </div>
            <button
              className="danger-action"
              disabled={
                busy !== null ||
                !operatorEnabled ||
                snapshot.network.nodes.find((node) => node.id === 'northstar')?.status === 'offline'
              }
              onClick={() => {
                if (!confirmDestructive('Simulate loss of the NORTHSTAR coordination relay (jamming or attrition)?'))
                  return
                void command('Relay loss injection', '/network/fail/northstar', { method: 'POST' })
              }}
            >
              <Zap size={15} />
              SIMULATE RELAY LOSS
            </button>
          </div>
        </section>

        <aside className="analysis-column">
          <ProphetPanel
            snapshot={snapshot}
            busy={busy}
            operatorEnabled={operatorEnabled}
            onAdvance={() =>
              void command('Advance forecast', '/scenario/advance', {
                method: 'POST',
                body: JSON.stringify({ seconds: 15 }),
              })
            }
          />
          <MirrorPanel
            snapshot={snapshot}
            busy={busy}
            operatorEnabled={operatorEnabled}
            onSelectBranch={(branchId) =>
              void command('Tabletop branch review', '/tabletop/select', {
                method: 'POST',
                body: JSON.stringify({
                  branch_id: branchId,
                  decision_point_id: snapshot.mirror.decision_point_id,
                }),
              })
            }
          />
          <PhoenixPanel
            snapshot={snapshot}
            busy={busy}
            operatorEnabled={operatorEnabled}
            onApprove={() => {
              if (!activeRecovery) return
              void runApprovedRecovery(activeRecovery.id, activeRecovery.name)
            }}
          />
          <CitizenGridPanel
            snapshot={snapshot}
            busy={busy}
            operatorEnabled={operatorEnabled}
            onDetect={() => void command('District detection', '/citizen/detect', { method: 'POST' })}
            onAttrition={() => {
              if (!confirmDestructive('Take 30% of fictional community sensors offline?')) return
              void command('Sensor attrition', '/citizen/attrition', {
                method: 'POST',
                body: JSON.stringify({ percent: 30 }),
              })
            }}
            onJam={() => {
              if (!confirmDestructive('Simulate jamming of the active advisory channel?')) return
              void command('Channel jamming', '/citizen/jam', { method: 'POST' })
            }}
            onWarn={() => {
              if (
                !confirmDestructive(
                  'Approve a simulated civilian advisory for the corroborating districts? Nothing is transmitted.',
                )
              )
                return
              void command('Civilian advisory approval', '/citizen/warn', { method: 'POST' })
            }}
          />
        </aside>
      </main>

      <section className="timeline-section" aria-labelledby="timeline-title">
        <div className="timeline-heading">
          <div>
            <Terminal size={15} />
            <span id="timeline-title">AUDIT STREAM</span>
            <b>{visibleEvents.length.toString().padStart(2, '0')} EVENTS</b>
          </div>
          <div className="timeline-status">
            <div className="timeline-filters" aria-label="Audit timeline filters">
              <select
                aria-label="Filter audit events by module"
                value={timelineSource}
                onChange={(event) => setTimelineSource(event.target.value as typeof timelineSource)}
              >
                <option value="all">ALL MODULES</option>
                {Array.from(new Set(snapshot.events.map((event) => event.source)))
                  .sort()
                  .map((source) => (
                    <option key={source} value={source}>
                      {source.toUpperCase()}
                    </option>
                  ))}
              </select>
              <select
                aria-label="Filter audit events by severity"
                value={timelineSeverity}
                onChange={(event) => setTimelineSeverity(event.target.value as typeof timelineSeverity)}
              >
                <option value="all">ALL LEVELS</option>
                {(['info', 'success', 'warning', 'critical'] as const).map((severity) => (
                  <option key={severity} value={severity}>
                    {severity.toUpperCase()}
                  </option>
                ))}
              </select>
              <button
                className="audit-export-button"
                disabled={busy !== null || connection !== 'live'}
                onClick={() => void exportAudit()}
              >
                <Download size={12} />
                EXPORT
              </button>
            </div>
            <p aria-live="polite">{notice}</p>
            {replaySequence !== null && (
              <button className="live-view-button" disabled={busy !== null} onClick={() => void returnToLive()}>
                <RefreshCcw size={12} />
                RETURN LIVE
              </button>
            )}
          </div>
        </div>
        <div className="event-stream">
          {visibleEvents.map((event) => (
            <button
              className={`event-item ${event.severity} ${replaySequence === event.sequence ? 'selected' : ''}`}
              disabled={busy !== null || connection === 'fixture'}
              key={event.event_id}
              onClick={() => void replayEvent(event.sequence)}
              title={`Replay state at event #${event.sequence}`}
            >
              <time>{formatMissionTime(event.scenario_time_ms)}</time>
              <span className="event-sequence">#{event.sequence.toString().padStart(3, '0')}</span>
              <i aria-hidden="true" />
              <div>
                <strong>{humanizeEvent(event.type)}</strong>
                <small>
                  {event.source.toUpperCase()} · HASH {event.event_hash.slice(0, 12)}
                </small>
              </div>
            </button>
          ))}
        </div>
      </section>

      <footer className="control-dock">
        <div className="control-group">
          <button
            className="icon-button"
            aria-label="Reset scenario"
            title="Reset scenario"
            disabled={busy !== null || !operatorEnabled}
            onClick={() => {
              if (!confirmDestructive('Reset the fictional scenario and clear the current run?')) return
              setPlaying(false)
              void command('Scenario reset', '/scenario/reset', { method: 'POST' })
            }}
          >
            <RefreshCcw size={16} />
          </button>
          <button
            className={playing ? 'run-button active' : 'run-button'}
            disabled={!operatorEnabled}
            onClick={() => setPlaying((current) => !current)}
          >
            {playing ? <Pause size={16} /> : <Play size={16} />}
            {playing ? 'PAUSE SCENARIO' : 'RUN SCENARIO'}
          </button>
          <div className="speed-selector" aria-label="Scenario playback speed">
            {([1, 2, 4] as const).map((speed) => (
              <button
                aria-label={`Set scenario speed to ${speed} times`}
                aria-pressed={snapshot.scenario.speed === speed}
                className={snapshot.scenario.speed === speed ? 'active' : ''}
                disabled={busy !== null || !operatorEnabled}
                key={speed}
                onClick={() =>
                  void command(`Set ${speed}× speed`, '/scenario/speed', {
                    method: 'POST',
                    body: JSON.stringify({ multiplier: speed }),
                  })
                }
              >
                {speed}×
              </button>
            ))}
          </div>
        </div>
        <div className="dock-status">
          {busy ? (
            <>
              <Activity className="spin" size={14} /> {busy.toUpperCase()}
            </>
          ) : (
            <>
              <CircleOff size={13} /> AUTONOMOUS ACTION DISABLED
            </>
          )}
        </div>
        <div className="sequence-readout">
          <span>EVENT SEQ</span>
          <strong>{snapshot.scenario.sequence.toString().padStart(4, '0')}</strong>
        </div>
      </footer>
    </div>
  )
}

export default App
