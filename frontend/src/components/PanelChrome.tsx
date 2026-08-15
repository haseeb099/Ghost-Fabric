import type { ReactNode } from 'react'

export function StatusPill({
  icon,
  label,
  tone,
}: {
  icon: ReactNode
  label: string
  tone: 'ok' | 'warn'
}) {
  return (
    <div className={`status-pill ${tone}`}>
      {icon}
      <span>{label}</span>
    </div>
  )
}

export function PanelHeader({
  index,
  title,
  subtitle,
  icon,
  status,
}: {
  index: string
  title: string
  subtitle: string
  icon: ReactNode
  status: string
}) {
  return (
    <header className="panel-header">
      <span className="panel-index">{index}</span>
      <span className="panel-icon">{icon}</span>
      <div>
        <h2 id={`${title.toLowerCase()}-title`}>{title}</h2>
        <p>{subtitle}</p>
      </div>
      <span className={`panel-state ${status.toLowerCase().replaceAll(' ', '-')}`}>
        <i />
        {status.toUpperCase()}
      </span>
    </header>
  )
}
