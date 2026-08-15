import { Activity, ChevronRight, Radio, ShieldCheck } from 'lucide-react'
import type { Snapshot } from '../types'
import { PanelHeader } from './PanelChrome'

type Props = {
  snapshot: Snapshot
  busy: string | null
  operatorEnabled: boolean
  onAdvance: () => void
}

export function ProphetPanel({ snapshot, busy, operatorEnabled, onAdvance }: Props) {
  const telemetrySample = snapshot.prophet.telemetry.current_sample
  const countdown = snapshot.prophet.countdown
  return (
    <section className="analysis-panel prophet" aria-labelledby="prophet-title">
      <PanelHeader
        index="02"
        title="PROPHET"
        subtitle="Link degradation review"
        icon={<Activity size={17} />}
        status={snapshot.prophet.state}
      />
      <div className="forecast-core">
        <div className={`confidence-ring ${snapshot.prophet.state}`}>
          <span>{snapshot.prophet.confidence}</span>
          <small>%</small>
        </div>
        <div className="forecast-copy">
          <p>DEGRADATION CONFIDENCE</p>
          <strong>
            {snapshot.prophet.state === 'warning'
              ? `${snapshot.prophet.warning_window_minutes} MIN SYNTHETIC WINDOW`
              : snapshot.prophet.state === 'watch'
                ? 'PATTERN DEVELOPING'
                : 'BASELINE NOMINAL'}
          </strong>
          <span>Calibrated against labeled fixture only</span>
        </div>
      </div>
      {countdown && (
        <div className="prophet-countdown" aria-label="Synthetic virtual-time countdown">
          <span>VIRTUAL CLOCK</span>
          <strong>T{countdown.simulation_minute} MIN</strong>
          <small>
            {countdown.minutes_to_synthetic_event} fixture minutes to labeled synthetic event · review-only
          </small>
        </div>
      )}
      <div className="signal-list">
        {snapshot.prophet.signals.map((signal) => (
          <div className="signal-row" key={signal.id}>
            <div>
              <span>{signal.label}</span>
              <small>{signal.trend.toUpperCase()}</small>
            </div>
            <div className="signal-bar" aria-label={`${signal.label} contribution ${signal.contribution}`}>
              <i style={{ width: `${Math.min(100, signal.contribution * 2.5)}%` }} />
            </div>
            <strong>
              {Math.round(signal.value)}
              {signal.unit === '%' ? '%' : ''}
            </strong>
          </div>
        ))}
      </div>
      <div className="forecast-evidence" aria-label="PROPHET calibration evidence">
        <div className="evidence-metrics">
          <span>
            INTERVAL <b>
              {snapshot.prophet.evidence.confidence_interval[0]}–{snapshot.prophet.evidence.confidence_interval[1]}%
            </b>
          </span>
          <span>
            CONFIRM <b>{snapshot.prophet.evidence.confirming_signal_count}/3</b>
          </span>
          <span>
            WATCH / WARN <b>
              {snapshot.prophet.evidence.thresholds.watch}/{snapshot.prophet.evidence.thresholds.warning}
            </b>
          </span>
        </div>
        <p>
          <ShieldCheck size={12} />
          FALSE-POSITIVE GUARDRAIL: single-signal excursion requires confirmation.
        </p>
        <small>
          ROW {telemetrySample ? `T${telemetrySample.minute} ${telemetrySample.label.replaceAll('_', ' ')}` : 'BASELINE'} ·{' '}
          {snapshot.prophet.telemetry.sample_count} LABELED SAMPLES · {snapshot.prophet.evidence.data_quality.toUpperCase()} QUALITY
        </small>
      </div>
      <button className="panel-command" disabled={busy !== null || !operatorEnabled} onClick={onAdvance}>
        <Radio size={15} />
        ADVANCE SYNTHETIC FEED +15s
        <ChevronRight size={14} />
      </button>
    </section>
  )
}
