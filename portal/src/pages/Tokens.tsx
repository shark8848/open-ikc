import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/client'
import type { CreateTokenResult, TokenRecord } from '../api/types'
import { Banner, Empty, ErrorBox, Loading, StatusBadge } from '../components/ui'
import { formatTs, formatRelative } from '../utils/format'

export function Tokens() {
  const [tokens, setTokens] = useState<TokenRecord[]>([])
  const [includeRevoked, setIncludeRevoked] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // 创建表单
  const [name, setName] = useState('')
  const [owner, setOwner] = useState('')
  const [scopes, setScopes] = useState('')
  const [expiresIn, setExpiresIn] = useState('')
  const [creating, setCreating] = useState(false)
  const [created, setCreated] = useState<CreateTokenResult | null>(null)
  const [formError, setFormError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setTokens(await adminApi.listTokens(includeRevoked))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [includeRevoked])

  useEffect(() => {
    load()
  }, [load])

  async function create() {
    setFormError('')
    if (!name.trim()) {
      setFormError('名称必填')
      return
    }
    setCreating(true)
    try {
      const result = await adminApi.createToken({
        name: name.trim(),
        owner: owner.trim() || undefined,
        scopes: scopes.trim() ? scopes.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
        expiresInSeconds: expiresIn.trim() ? Number(expiresIn.trim()) : undefined,
      })
      setCreated(result)
      setTokens(await adminApi.listTokens(includeRevoked))
      setName('')
      setOwner('')
      setScopes('')
      setExpiresIn('')
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e))
    } finally {
      setCreating(false)
    }
  }

  async function revoke(id: number) {
    if (!window.confirm('确认撤销该 token？撤销后使用此 token 的请求将立即返回 100401。')) return
    try {
      await adminApi.revokeToken(id)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <>
      <h1 className="page-title">Token 管理</h1>
      <p className="page-desc">
        创建、撤销与查看平台接入 token。明文 token 仅在创建时返回一次，数据库仅存 sha256 哈希。
      </p>

      {error ? <ErrorBox message={error} /> : null}

      {/* 创建成功：一次性展示明文 */}
      {created ? (
        <Banner kind="ok">
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            创建成功 —— 明文 token 仅此一次显示，请立即保存：
          </div>
          <div className="mono" style={{ background: '#0a0e13', padding: '10px 12px', borderRadius: 8, wordBreak: 'break-all' }}>
            {created.token}
          </div>
          <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            名称：{created.name} · ID：{created.id}
          </div>
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }} onClick={() => setCreated(null)}>
            我已保存，关闭
          </button>
        </Banner>
      ) : null}

      {/* 创建表单 */}
      <div className="card">
        <div className="card-title">创建 Token</div>
        {formError ? <Banner kind="err">{formError}</Banner> : null}
        <div className="form-row">
          <div className="form-field">
            <label>名称 *</label>
            <input type="text" placeholder="如 ops-监控" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="form-field">
            <label>所有者</label>
            <input type="text" placeholder="可选，如 zhangsan" value={owner} onChange={(e) => setOwner(e.target.value)} />
          </div>
          <div className="form-field">
            <label>作用域（逗号分隔）</label>
            <input type="text" placeholder="可选，如 kb:read" value={scopes} onChange={(e) => setScopes(e.target.value)} />
          </div>
          <div className="form-field">
            <label>有效期（秒，留空=永不过期）</label>
            <input type="number" placeholder="如 86400" value={expiresIn} onChange={(e) => setExpiresIn(e.target.value)} min="1" />
          </div>
          <button className="btn" disabled={creating} onClick={create}>
            {creating ? '创建中…' : '创建'}
          </button>
        </div>
      </div>

      {/* Token 列表 */}
      <div className="card">
        <div className="toolbar">
          <div className="card-title" style={{ margin: 0 }}>Token 列表</div>
          <div className="spacer" />
          <label className="muted" style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <input
              type="checkbox"
              checked={includeRevoked}
              onChange={(e) => setIncludeRevoked(e.target.checked)}
              style={{ width: 'auto' }}
            />
            显示已撤销
          </label>
          <button className="btn btn-ghost btn-sm" onClick={load}>刷新</button>
        </div>

        {loading ? (
          <Loading />
        ) : tokens.length === 0 ? (
          <Empty text="暂无 token，先创建一个" />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>名称</th>
                  <th>所有者</th>
                  <th>作用域</th>
                  <th>状态</th>
                  <th>创建时间</th>
                  <th>过期时间</th>
                  <th>最近使用</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((t) => (
                  <tr key={t.id}>
                    <td className="mono muted">{t.id}</td>
                    <td>{t.name}</td>
                    <td>{t.owner || <span className="muted">-</span>}</td>
                    <td className="mono">{t.scopes?.length ? t.scopes.join(', ') : '-'}</td>
                    <td>
                      <StatusBadge status={t.status} />
                      {t.status === 'active' && t.expired ? <span className="badge badge-warn" style={{ marginLeft: 6 }}>已过期</span> : null}
                    </td>
                    <td className="nowrap">{formatTs(t.createdAt)}</td>
                    <td className="nowrap">{t.expiresAt ? formatTs(t.expiresAt) : '永不过期'}</td>
                    <td className="nowrap muted">{formatRelative(t.lastUsedAt)}</td>
                    <td>
                      {t.status === 'active' ? (
                        <button className="btn btn-danger btn-sm" onClick={() => revoke(t.id)}>
                          撤销
                        </button>
                      ) : (
                        <span className="muted">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
