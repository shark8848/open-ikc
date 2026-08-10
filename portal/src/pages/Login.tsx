import { useState } from 'react'
import { setAdminToken } from '../api/client'

interface Props {
  onLoggedIn: () => void
}

export function Login({ onLoggedIn }: Props) {
  const [token, setToken] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit() {
    if (!token.trim()) {
      setError('请输入管理 token')
      return
    }
    setBusy(true)
    setError('')
    setAdminToken(token.trim())
    // 用 overview 接口校验 token 是否有效；后端未配置 admin token 时返回 503。
    const probeUrl = baseUrl.trim()
      ? `${baseUrl.replace(/\/$/, '')}/admin/overview`
      : '/admin/overview'
    try {
      const resp = await fetch(probeUrl, {
        headers: { Authorization: `Bearer ${token.trim()}` },
      })
      const body = await resp.json().catch(() => null)
      if (body?.errCode === '000000') {
        onLoggedIn()
        return
      }
      if (resp.status === 503 || body?.errCode === '503001') {
        setError('管理面未启用：请配置 OPEN_PLATFORM_ADMIN_TOKEN 环境变量')
      } else if (body?.errCode === '100401') {
        setError('管理 token 无效，请检查')
      } else {
        setError(body?.errMsg || `登录失败 (HTTP ${resp.status})`)
      }
      setAdminToken('')
    } catch {
      setError('无法连接平台服务，请确认 18000 端口已启动')
      setAdminToken('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <h1>Open IKC 管理 Portal</h1>
        <p>请输入管理 token（对应后端 OPEN_PLATFORM_ADMIN_TOKEN 环境变量）</p>
        {error ? <BannerInline msg={error} /> : null}
        <input
          type="password"
          placeholder="管理 token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          autoFocus
        />
        <input
          type="text"
          placeholder="平台地址（可选，默认同源，如 http://127.0.0.1:18000）"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
        />
        <button className="btn" disabled={busy} onClick={submit}>
          {busy ? '验证中…' : '进入管理台'}
        </button>
      </div>
    </div>
  )
}

function BannerInline({ msg }: { msg: string }) {
  return <div className="banner banner-err" style={{ marginBottom: 14 }}>{msg}</div>
}
