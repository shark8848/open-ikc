import {
  useEffect,
  useState,
  type ComponentType,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { clearAdminToken } from '../api/client'
import {
  BookOpenIcon,
  BookMarkedIcon,
  ContrastIcon,
  FileTextIcon,
  FlaskIcon,
  GridIcon,
  KeyIcon,
  LeafIcon,
  LogOutIcon,
  MoonIcon,
  PulseIcon,
  SunIcon,
  type IconProps,
} from './icons'

export type ThemeKey = 'dark' | 'light' | 'high-contrast' | 'green'

export const THEMES: { key: ThemeKey; label: string }[] = [
  { key: 'dark', label: '深色' },
  { key: 'light', label: '浅色' },
  { key: 'high-contrast', label: '高对比' },
  { key: 'green', label: '护眼绿' },
]

const THEME_STORAGE_KEY = 'open-ikc-theme'

function applyTheme(theme: ThemeKey): void {
  const root = document.documentElement
  if (theme === 'dark') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', theme)
}

export type PageKey = 'dashboard' | 'endpoints' | 'tokens' | 'testlab'

interface NavItem {
  key: PageKey
  label: string
  icon: ComponentType<IconProps>
}

const NAV_ITEMS: NavItem[] = [
  { key: 'dashboard', label: '总览', icon: GridIcon },
  { key: 'endpoints', label: '端点监控', icon: PulseIcon },
  { key: 'tokens', label: 'Token 管理', icon: KeyIcon },
  { key: 'testlab', label: '在线测试', icon: FlaskIcon },
]

interface NavLink {
  href: string
  label: string
  icon: ComponentType<IconProps>
}

/** 文档类外部链接（打开 Swagger UI / ReDoc）。 */
const NAV_LINKS: NavLink[] = [
  { href: '/docs', label: 'Swagger UI', icon: BookOpenIcon },
  { href: '/redoc', label: 'ReDoc', icon: FileTextIcon },
  { href: '/api-manual', label: '开发手册', icon: BookMarkedIcon },
]

const THEME_ICONS: Record<ThemeKey, ComponentType<IconProps>> = {
  dark: MoonIcon,
  light: SunIcon,
  'high-contrast': ContrastIcon,
  green: LeafIcon,
}

interface Props {
  page: PageKey
  onNavigate: (key: PageKey) => void
  onLogout: () => void
  children: ReactNode
}

export function Layout({ page, onNavigate, onLogout, children }: Props) {
  const [theme, setTheme] = useState<ThemeKey>(() => {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    return (saved as ThemeKey) || 'dark'
  })

  useEffect(() => {
    applyTheme(theme)
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  const handleLogout = () => {
    clearAdminToken()
    onLogout()
  }

  const handleNavKey = (key: PageKey) => (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onNavigate(key)
    }
  }

  return (
    <div className="layout">
      <aside className="layout-sidebar">
        <div className="brand">
          <div className="brand-logo">IKC</div>
          <div className="brand-text">
            <div className="brand-name">Open IKC</div>
            <div className="brand-sub">管理平台</div>
          </div>
        </div>

        <nav className="nav-section" aria-label="工作台">
          <div className="nav-section-label">工作台</div>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <div
                key={item.key}
                className={`nav-item${page === item.key ? ' active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => onNavigate(item.key)}
                onKeyDown={handleNavKey(item.key)}
              >
                <span className="nav-icon">
                  <Icon size={17} />
                </span>
                <span className="nav-label">{item.label}</span>
              </div>
            )
          })}
        </nav>

        <nav className="nav-section" aria-label="文档">
          <div className="nav-section-label">文档</div>
          {NAV_LINKS.map((link) => {
            const Icon = link.icon
            return (
              <a
                key={link.href}
                className="nav-item"
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="nav-icon">
                  <Icon size={17} />
                </span>
                <span className="nav-label">{link.label}</span>
              </a>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="theme-menu">
            <span className="theme-menu-label">显示样式</span>
            <div className="theme-options">
              {THEMES.map((t) => {
                const ThemeIcon = THEME_ICONS[t.key]
                return (
                  <button
                    key={t.key}
                    type="button"
                    title={t.label}
                    aria-label={t.label}
                    className={`theme-option${theme === t.key ? ' active' : ''}`}
                    onClick={() => setTheme(t.key)}
                  >
                    <ThemeIcon size={15} />
                  </button>
                )
              })}
            </div>
          </div>
          <div className="sidebar-meta">
            <span>v1.0.0</span>
            <span className="sidebar-status">
              <span className="sidebar-status-dot" />
              在线
            </span>
          </div>
          <button type="button" className="logout-btn" onClick={handleLogout}>
            <LogOutIcon size={15} />
            <span>退出登录</span>
          </button>
        </div>
      </aside>
      <main className="layout-main">{children}</main>
    </div>
  )
}
