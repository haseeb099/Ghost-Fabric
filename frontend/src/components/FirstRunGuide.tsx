import { BookOpen, Check, ChevronRight, Network, ShieldCheck, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { hasSeenOnboarding, markOnboardingSeen } from '../api'

type Props = {
  forceOpen: boolean
  onClose: () => void
}

const layers = [
  {
    index: '01',
    name: 'CHAMELEON',
    purpose: 'Who is still reachable, who coordinates the mesh, and whether the unit is split into partitions.',
  },
  {
    index: '02',
    name: 'PROPHET',
    purpose: 'Labeled link-degradation evidence with uncertainty, so one noisy signal never becomes an order.',
  },
  {
    index: '03',
    name: 'MIRROR',
    purpose: 'Compare declared courses of action side by side. A human chooses; the software does not act.',
  },
  {
    index: '04',
    name: 'PHOENIX',
    purpose: 'Approve, execute, and verify a reversible simulated link restore with a complete audit record.',
  },
] as const

const runSteps = [
  'Choose LOCAL OPTIONAL or OPERATOR TOKEN so simulation controls are enabled.',
  'Advance the synthetic feed and review the PROPHET degradation evidence.',
  'Simulate the coordination relay loss and watch CHAMELEON hand off and reroute.',
  'Compare the MIRROR courses of action, then select one as the human decision.',
  'Approve the PHOENIX restore, verify it, then export the audit record.',
] as const

export function FirstRunGuide({ forceOpen, onClose }: Props) {
  const [firstVisit, setFirstVisit] = useState(() => !hasSeenOnboarding())
  const closeButtonRef = useRef<HTMLButtonElement | null>(null)
  const open = firstVisit || forceOpen

  const dismiss = useCallback(() => {
    markOnboardingSeen()
    setFirstVisit(false)
    onClose()
  }, [onClose])

  useEffect(() => {
    if (!open) return
    closeButtonRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') dismiss()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [dismiss, open])

  if (!open) return null

  return (
    <div className="guide-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) dismiss()
    }}>
      <section
        className="first-run-guide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="guide-title"
        aria-describedby="guide-summary"
      >
        <header className="guide-header">
          <div>
            <span className="guide-kicker"><BookOpen size={13} /> OPERATOR ORIENTATION</span>
            <h2 id="guide-title">What Ghost Fabric actually does</h2>
            <p id="guide-summary">
              Rehearse how a frontline unit keeps command and control coherent when its relays are jammed or
              destroyed—without touching a real system.
            </p>
          </div>
          <button ref={closeButtonRef} type="button" className="guide-close" onClick={dismiss} aria-label="Close operator guide">
            <X size={17} />
          </button>
        </header>

        <div className="guide-context">
          <div className="guide-context-icon"><Network size={21} /></div>
          <div>
            <span>ACTIVE EXERCISE</span>
            <strong>EASTERN EUROPE EDGE C2 CONTINUITY</strong>
            <p>
              Synthetic communications-disruption patterns informed by public reporting from the Russia–Ukraine war.
              Locations, nodes, timings, and measurements are invented and deliberately generalized.
            </p>
          </div>
          <div className="guide-boundary">
            <ShieldCheck size={16} />
            <span>FRIENDLY NETWORK ONLY</span>
            <small>
              Keeps our own mesh coherent. No threat tracking, geolocation, targeting, weapons, or autonomous action.
            </small>
          </div>
        </div>

        <div className="guide-grid">
          <section>
            <h3>THE FOUR-LAYER WORKFLOW</h3>
            <div className="guide-layers">
              {layers.map((layer) => (
                <article key={layer.name}>
                  <span>{layer.index}</span>
                  <div>
                    <strong>{layer.name}</strong>
                    <p>{layer.purpose}</p>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section>
            <h3>RUN THE GOLDEN PATH</h3>
            <ol className="guide-steps">
              {runSteps.map((step, index) => (
                <li key={step}>
                  <span>{index + 1}</span>
                  <p>{step}</p>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <footer className="guide-footer">
          <p><Check size={13} /> Every mutation is fictional, human-gated, and written to the audit stream.</p>
          <button type="button" className="guide-start" onClick={dismiss}>
            ENTER SIMULATION <ChevronRight size={15} />
          </button>
        </footer>
      </section>
    </div>
  )
}
