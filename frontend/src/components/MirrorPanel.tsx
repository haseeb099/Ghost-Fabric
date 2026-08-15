import { BrainCircuit, Check, ShieldCheck } from 'lucide-react'
import type { Snapshot } from '../types'
import { PanelHeader } from './PanelChrome'

type Props = {
  snapshot: Snapshot
  busy: string | null
  operatorEnabled: boolean
  onSelectBranch: (branchId: string) => void
}

export function MirrorPanel({ snapshot, busy, operatorEnabled, onSelectBranch }: Props) {
  return (
    <section className="analysis-panel mirror" aria-labelledby="mirror-title">
      <PanelHeader
        index="03"
        title="MIRROR"
        subtitle="Course-of-action comparison"
        icon={<BrainCircuit size={17} />}
        status={snapshot.mirror.awaiting_choice ? 'awaiting' : 'recorded'}
      />
      <div className="branch-comparison-label">
        <span>{snapshot.mirror.scenario_name ?? 'Side-by-side fixture comparison'}</span>
        <span>{snapshot.mirror.awaiting_choice ? 'Human selection required' : 'Fixture outcome recorded'}</span>
      </div>
      {snapshot.mirror.condition && (
        <p className="mirror-condition">
          <strong>{snapshot.mirror.decision_point_id?.toUpperCase()}</strong>
          <span>{snapshot.mirror.condition}</span>
        </p>
      )}
      <div className="branch-list">
        {snapshot.mirror.branches.map((branch, index) => (
          <button
            className={snapshot.mirror.selected_branch === branch.id ? 'branch-row selected' : 'branch-row'}
            key={branch.id}
            disabled={busy !== null || !operatorEnabled || snapshot.mirror.completed === true}
            onClick={() => onSelectBranch(branch.id)}
            aria-pressed={snapshot.mirror.selected_branch === branch.id}
          >
            <span className="branch-index">{(index + 1).toString().padStart(2, '0')}</span>
            <span>
              <strong>{branch.label}</strong>
              <small>{branch.assumption}</small>
            </span>
            <span className="branch-state">
              {snapshot.mirror.selected_branch === branch.id ? (
                <>
                  <Check size={12} /> SELECTED
                </>
              ) : (
                'COMPARE'
              )}
            </span>
          </button>
        ))}
      </div>
      <p className="guardrail-note">
        <ShieldCheck size={14} />
        {snapshot.mirror.notice}
      </p>
    </section>
  )
}
