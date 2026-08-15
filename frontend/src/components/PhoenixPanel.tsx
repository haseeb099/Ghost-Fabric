import { Check, ChevronRight, Route, ShieldCheck } from 'lucide-react'
import type { PhoenixWorkflowState, Snapshot } from '../types'
import { PanelHeader } from './PanelChrome'

const STEPS: PhoenixWorkflowState[] = ['alert', 'approval', 'execution', 'verify', 'restored']

type Props = {
  snapshot: Snapshot
  busy: string | null
  operatorEnabled: boolean
  onApprove: () => void
}

function stepTone(current: PhoenixWorkflowState, step: PhoenixWorkflowState): string {
  if (current === 'failed' || current === 'rollback') {
    return step === 'restored' ? 'failed' : STEPS.indexOf(step) <= STEPS.indexOf('verify') ? 'done' : 'pending'
  }
  const currentIndex = STEPS.indexOf(current === 'approval' ? 'approval' : current)
  const stepIndex = STEPS.indexOf(step)
  if (current === 'restored' && step === 'restored') return 'done'
  if (stepIndex < currentIndex) return 'done'
  if (stepIndex === currentIndex) return 'active'
  return 'pending'
}

export function PhoenixPanel({ snapshot, busy, operatorEnabled, onApprove }: Props) {
  const activeRecovery =
    snapshot.phoenix.options.find((option) => option.status === 'approved') ??
    snapshot.phoenix.options.find((option) => option.status === 'recommended') ??
    snapshot.phoenix.options[0] ?? {
      id: 'no-valid-route',
      name: 'No valid route',
      route: ['MANUAL REVIEW'],
      availability: 0,
      reliability: 0,
      latency_seconds: 0,
      reversibility: 'high' as const,
      rationale: 'No complete simulated workflow route remains available.',
      status: 'available' as const,
    }
  const workflowState = snapshot.phoenix.workflow?.state ?? 'alert'
  const restored = snapshot.phoenix.workflow_status === 'restored'
  const failed = snapshot.phoenix.workflow_status === 'failed'

  return (
    <section className="analysis-panel phoenix" aria-labelledby="phoenix-title">
      <PanelHeader
        index="04"
        title="PHOENIX"
        subtitle="Human-approved link restore"
        icon={<Route size={17} />}
        status={snapshot.phoenix.workflow_status}
      />
      <ol className="workflow-stepper" aria-label="PHOENIX simulation workflow stages">
        {STEPS.map((step) => (
          <li key={step} className={stepTone(workflowState, step)}>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      <div className="recovery-status">
        <div className="route-chain" aria-label="Recovery route">
          {activeRecovery.route.map((stop, index) => (
            <span key={stop}>
              <i>{index + 1}</i>
              <b>{stop}</b>
              {index < activeRecovery.route.length - 1 && <ChevronRight size={12} />}
            </span>
          ))}
        </div>
        <div className="recovery-metrics">
          <span>
            <small>AVAILABLE</small>
            <strong>{activeRecovery.availability}%</strong>
          </span>
          <span>
            <small>RELIABILITY</small>
            <strong>{activeRecovery.reliability}%</strong>
          </span>
          <span>
            <small>RESTORE ETA</small>
            <strong>{activeRecovery.latency_seconds}s</strong>
          </span>
          <span>
            <small>REVERSIBLE</small>
            <strong>{activeRecovery.reversibility.toUpperCase()}</strong>
          </span>
        </div>
        <p className="recovery-rationale">{activeRecovery.rationale}</p>
        {snapshot.phoenix.workflow?.transitions?.length ? (
          <div className="workflow-transitions" aria-label="Recorded workflow transitions">
            {snapshot.phoenix.workflow.transitions.slice(-3).map((transition) => (
              <small key={transition.sequence}>
                #{transition.sequence} {transition.from_state} → {transition.to_state} · {transition.actor}
              </small>
            ))}
          </div>
        ) : null}
      </div>
      <button
        className={restored ? 'panel-command approved' : failed ? 'panel-command danger' : 'panel-command'}
        disabled={
          busy !== null ||
          !operatorEnabled ||
          restored ||
          failed ||
          snapshot.phoenix.planner.available_options === 0 ||
          workflowState === 'execution' ||
          workflowState === 'verify'
        }
        onClick={onApprove}
      >
        {restored ? <Check size={15} /> : <ShieldCheck size={15} />}
        {restored
          ? 'WORKFLOW RESTORED'
          : failed
            ? 'SIMULATION ROLLED BACK'
            : snapshot.phoenix.planner.available_options === 0
              ? 'NO VALID ROUTE — MANUAL REVIEW'
              : 'HUMAN APPROVAL REQUIRED'}
        <ChevronRight size={14} />
      </button>
    </section>
  )
}
