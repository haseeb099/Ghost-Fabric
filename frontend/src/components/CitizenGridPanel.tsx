import { BellRing, ChevronRight, Lock, Smartphone, WifiOff, Zap } from 'lucide-react'
import type { Snapshot } from '../types'
import { PanelHeader } from './PanelChrome'

type Props = {
  snapshot: Snapshot
  busy: string | null
  operatorEnabled: boolean
  onDetect: () => void
  onAttrition: () => void
  onJam: () => void
  onWarn: () => void
}

export function CitizenGridPanel({
  snapshot,
  busy,
  operatorEnabled,
  onDetect,
  onAttrition,
  onJam,
  onWarn,
}: Props) {
  const grid = snapshot.citizen
  if (!grid) return null

  const leadMinutes = Math.round(grid.synthetic_lead_seconds / 60)

  return (
    <section className="analysis-panel citizen" aria-labelledby="citizen-title">
      <PanelHeader
        index="05"
        title="CITIZEN"
        subtitle="Community sensor corroboration grid"
        icon={<Smartphone size={17} />}
        status={grid.warning_dispatched ? 'advisory sent' : grid.state}
      />

      <div className="citizen-core">
        <div className={`confidence-ring ${grid.state === 'confirmed' ? 'warning' : grid.state === 'corroborating' ? 'watch' : ''}`}>
          <span>{grid.confidence}</span>
          <small>%</small>
        </div>
        <div className="forecast-copy">
          <p>DISTRICT CORROBORATION</p>
          <strong>
            {grid.confirming_districts}/{grid.min_confirming_districts} DISTRICTS
          </strong>
          <span>
            {grid.sensors_online.toLocaleString()} of {grid.sensors_total.toLocaleString()} consenting sensors ·{' '}
            {grid.grid_survival_percent}% grid
          </span>
        </div>
      </div>

      <div className="citizen-metrics" aria-label="Citizen grid advisory readiness">
        <span>
          <small>STATE</small>
          <strong>{grid.state.toUpperCase()}</strong>
        </span>
        <span>
          <small>SYNTHETIC LEAD</small>
          <strong>{leadMinutes} MIN</strong>
        </span>
        <span>
          <small>ADVISORY</small>
          <strong>{grid.warning_dispatched ? 'RECORDED' : 'PENDING'}</strong>
        </span>
      </div>

      <div className="channel-ladder" aria-label="Advisory channel fallback ladder">
        {grid.channels.map((channel) => (
          <div className={`channel-row ${channel.status}${channel.active ? ' active' : ''}`} key={channel.id}>
            <i aria-hidden="true" />
            <div>
              <strong>{channel.label}</strong>
              <small>
                {channel.status.toUpperCase()} · {channel.reach_percent}% simulated reach
              </small>
            </div>
            {channel.active && <span>IN USE</span>}
          </div>
        ))}
      </div>

      <p className="citizen-privacy">
        <Lock size={12} />
        {grid.privacy}
      </p>

      <div className="citizen-actions">
        <button disabled={busy !== null || !operatorEnabled} onClick={onDetect}>
          <Zap size={13} /> ADD DISTRICT DETECTION
        </button>
        <button disabled={busy !== null || !operatorEnabled} onClick={onAttrition}>
          <Smartphone size={13} /> LOSE 30% SENSORS
        </button>
        <button disabled={busy !== null || !operatorEnabled} onClick={onJam}>
          <WifiOff size={13} /> JAM ACTIVE CHANNEL
        </button>
      </div>

      <button
        className={grid.warning_dispatched ? 'panel-command approved' : 'panel-command'}
        disabled={busy !== null || !operatorEnabled || !grid.ready_for_warning || grid.warning_dispatched}
        onClick={onWarn}
      >
        <BellRing size={15} />
        {grid.warning_dispatched ? 'ADVISORY RECORDED' : 'APPROVE CIVILIAN ADVISORY'}
        <ChevronRight size={14} />
      </button>

      <small className="citizen-guardrail">{grid.guardrail}</small>
    </section>
  )
}
