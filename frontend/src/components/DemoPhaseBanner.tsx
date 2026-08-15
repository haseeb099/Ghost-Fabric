import { Clapperboard } from 'lucide-react'
import type { DemoPhase } from '../types'

export function DemoPhaseBanner({ phase }: { phase?: DemoPhase }) {
  if (!phase) return null
  return (
    <section className="demo-phase-banner" aria-label="Guided fictional exercise phase">
      <div className="demo-phase-index">
        <Clapperboard size={14} />
        <span>
          PHASE {phase.index}/{phase.total}
        </span>
      </div>
      <div className="demo-phase-copy">
        <strong>{phase.title}</strong>
        <p>{phase.cue}</p>
        <small>{phase.operator_hint}</small>
      </div>
      <span className="demo-phase-tag">{phase.label.replaceAll('-', ' ').toUpperCase()}</span>
    </section>
  )
}
