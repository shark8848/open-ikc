import type { ReactNode } from 'react'
import { clearAdminToken } from '../api/client'

export type PageKey = 'dashboard' | 'tokens' | 'endpoints' | 'testlab'

const NAV: { key: PageKey; label: string; icon: string }[] = [
  { key: 'dashboard', label: '总览', icon: '◧' },
  { key: 'endpoints', label: '端点监控', icon: '⇄' },
  { key: 'tokens', label: 'Token 管理', icon: '🔑' },
  { key: 'testlab', label: '在线测试', icon: '▸' },
]

interface Props {
  page: PageKey
  onNavigate: (key: PageKey) => void
  children: ReactNode
}

export function Layout({ page, onNavigate, children }: Props) {
  return (
    <div className="layout">
      <aside className="layout-sidebar">
        <div className="brand">
          <div className="brand-logo">IKC</div>
          <div>
            <div className="brand-name">Open IKC</div>
            <div className="brand-sub">管理 Portal</div>
          </div>
        </div>
        {NAV.map((item) => (
          <div
            key={item.key}
            className={`nav-item${page === item.key ? ' active' : ''}`}
            onClick={() => onNavigate(item.key)}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </div>
        ))}
        <div className="sidebar-footer">
          <div style={{ marginBottom: 8 }}>v1.0.0 · 管理面</div>
          <button className="btn btn-ghost btn-sm" onClick={() => clearAdminToken()}>
            退出登录（清除 token）
          </button>
        </div>
      </aside>
      <main className="layout-main">{children}</main>
    </div>
  )
}
