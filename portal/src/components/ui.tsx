import type { ReactNode } from 'react'
import type { TokenStatus } from '../api/types'

export function StatCard(props: {
  label: string
  value: ReactNode
  tone?: 'ok' | 'warn' | 'err' | ''
  sub?: ReactNode
}) {
  const toneClass = props.tone ? ` ${props.tone}` : ''
  return (
    <div className="stat-card">
      <div className="stat-label">{props.label}</div>
      <div className={`stat-value${toneClass}`}>{props.value}</div>
      {props.sub ? <div className="stat-sub">{props.sub}</div> : null}
    </div>
  )
}

export function StatusBadge({ status }: { status: TokenStatus }) {
  return status === 'active' ? (
    <span className="badge badge-ok">active</span>
  ) : (
    <span className="badge badge-err">revoked</span>
  )
}

export function MethodChip({ method }: { method: string }) {
  const cls = method.toLowerCase() === 'get' ? 'method-chip get' : 'method-chip post'
  return <span className={cls}>{method}</span>
}

export function ErrCodeBadge({ errCode }: { errCode: string }) {
  if (errCode === '000000') return <span className="badge badge-ok">000000</span>
  if (errCode === '') return <span className="badge badge-dim">-</span>
  return <span className="badge badge-warn">{errCode}</span>
}

export function Banner({
  kind,
  children,
}: {
  kind: 'ok' | 'err' | 'warn' | 'info'
  children: ReactNode
}) {
  return <div className={`banner banner-${kind}`}>{children}</div>
}

export function Loading({ text = '加载中…' }: { text?: string }) {
  return <div className="muted" style={{ padding: '12px 0' }}>{text}</div>
}

export function Empty({ text = '暂无数据' }: { text?: string }) {
  return (
    <div className="muted" style={{ padding: '24px 0', textAlign: 'center' }}>
      {text}
    </div>
  )
}

export function ErrorBox({ message }: { message: string }) {
  return <Banner kind="err">{message}</Banner>
}
