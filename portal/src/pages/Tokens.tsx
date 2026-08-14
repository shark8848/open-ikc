import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/client'
import type { CreateTokenResult, TokenRecord } from '../api/types'
import { useFeedback } from '../components/feedback'
import {
  CheckIcon,
  CopyIcon,
  PlusIcon,
  RefreshIcon,
  TrashIcon,
  CloseIcon,
} from '../components/icons'
import { Empty, Loading, StatusBadge } from '../components/ui'
import { formatTs, formatRelative } from '../utils/format'

/** 作用域预设：与开放平台四大能力对齐，可多选。 */
const SCOPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'kb:read', label: '知识库 · 读取' },
  { value: 'kb:write', label: '知识库 · 写入' },
  { value: 'doc:read', label: '文档 · 读取' },
  { value: 'doc:write', label: '文档 · 写入' },
  { value: 'parse:read', label: '解析 · 读取' },
  { value: 'parse:write', label: '解析 · 写入' },
  { value: 'search:query', label: '检索 · 查询' },
]

function todayLocal(): string {
  const d = new Date()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

export function Tokens() {
  const [tokens, setTokens] = useState<TokenRecord[]>([])
  const [includeRevoked, setIncludeRevoked] = useState(false)
  const [loading, setLoading] = useState(true)

  // 创建表单
  const [name, setName] = useState('')
  const [owner, setOwner] = useState('')
  const [scopes, setScopes] = useState<string[]>([])
  const [expiresAt, setExpiresAt] = useState('')
  const [neverExpires, setNeverExpires] = useState(true)
  const [creating, setCreating] = useState(false)
  const [created, setCreated] = useState<CreateTokenResult | null>(null)
  const { toast, confirm } = useFeedback()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setTokens(await adminApi.listTokens(includeRevoked))
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [includeRevoked, toast])

  useEffect(() => {
    load()
  }, [load])

  async function create() {
    if (!name.trim()) {
      toast.error('请填写 Token 名称')
      return
    }
    let expiresInSeconds: number | undefined
    if (!neverExpires && expiresAt) {
      const dayEnd = new Date(`${expiresAt}T23:59:59`).getTime()
      expiresInSeconds = Math.floor((dayEnd - Date.now()) / 1000)
      if (expiresInSeconds <= 0) {
        toast.error('有效期需晚于今天')
        return
      }
    }
    if (creating) {
      return
    }
    setCreating(true)
    try {
      const result = await adminApi.createToken({
        name: name.trim(),
        owner: owner.trim() || undefined,
        scopes: scopes.length ? scopes : undefined,
        expiresInSeconds,
      })
      setCreated(result)
      setTokens(await adminApi.listTokens(includeRevoked))
      setName('')
      setOwner('')
      setScopes([])
      setExpiresAt('')
      setNeverExpires(true)
      toast.success(`Token「${result.name}」创建成功`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e))
    } finally {
      setCreating(false)
    }
  }

  async function revoke(token: TokenRecord) {
    const ok = await confirm({
      title: `撤销 Token「${token.name}」？`,
      message: '撤销后使用此 token 的请求将立即返回 100401，且不可恢复。',
      confirmText: '确认撤销',
      cancelText: '取消',
      danger: true,
    })
    if (!ok) return
    try {
      await adminApi.revokeToken(token.id)
      await load()
      toast.success(`Token「${token.name}」已撤销`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e))
    }
  }

  async function copyToken(token: string) {
    try {
      await navigator.clipboard.writeText(token)
      toast.success('明文 token 已复制')
    } catch {
      toast.error('复制失败，请手动选择复制')
    }
  }

  function toggleScope(value: string) {
    setScopes((prev) => (prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]))
  }

  return (
    <>
      <h1 className="page-title">Token 管理</h1>
      <p className="page-desc">
        创建、撤销与查看平台接入 token。明文 token 仅在创建时返回一次，数据库仅存 sha256 哈希。
      </p>

      {/* 创建成功：一次性展示明文 */}
      {created ? (
        <div className="token-created">
          <div className="token-created-head">
            <span>创建成功 —— 明文 token 仅此一次显示，请立即保存：</span>
            <button
              type="button"
              className="icon-btn"
              title="关闭"
              aria-label="关闭"
              onClick={() => setCreated(null)}
            >
              <CloseIcon size={15} />
            </button>
          </div>
          <div className="token-created-body">
            <code className="token-plaintext">{created.token}</code>
            <button
              type="button"
              className="icon-btn"
              title="复制"
              aria-label="复制明文 token"
              onClick={() => copyToken(created.token)}
            >
              <CopyIcon size={15} />
            </button>
          </div>
          <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            名称：{created.name} · ID：{created.id}
          </div>
        </div>
      ) : null}

      {/* 创建表单 */}
      <div className="card">
        <div className="card-title">创建 Token</div>
        <div className="form-row">
          <div className="form-field">
            <label>名称 *</label>
            <input type="text" placeholder="如 ops-监控" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="form-field">
            <label>所有者</label>
            <input type="text" placeholder="可选，如 zhangsan" value={owner} onChange={(e) => setOwner(e.target.value)} />
          </div>
          <div className="form-field form-field-wide">
            <label>作用域（预留 · 暂未生效，可多选）</label>
            <div className="scope-chips">
              {SCOPE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`scope-chip${scopes.includes(opt.value) ? ' active' : ''}`}
                  onClick={() => toggleScope(opt.value)}
                >
                  <span className="scope-chip-box">
                    {scopes.includes(opt.value) ? <CheckIcon size={12} /> : null}
                  </span>
                  {opt.label}
                </button>
              ))}
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              当前仅作记录展示，运行时暂未按作用域限制接口调用。
            </div>
          </div>
          <div className="form-field">
            <label>有效期</label>
            <input
              type="date"
              value={expiresAt}
              min={todayLocal()}
              disabled={neverExpires}
              onChange={(e) => setExpiresAt(e.target.value)}
            />
            <label className="check-label">
              <input
                type="checkbox"
                checked={neverExpires}
                onChange={(e) => setNeverExpires(e.target.checked)}
                style={{ width: 'auto' }}
              />
              永不过期
            </label>
          </div>
          <button
            type="button"
            className="icon-btn icon-btn-primary"
            title={creating ? '创建中…' : '创建 Token'}
            aria-label="创建 Token"
            disabled={creating}
            onClick={create}
          >
            <PlusIcon size={18} />
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
          <button
            type="button"
            className="icon-btn"
            title="刷新"
            aria-label="刷新"
            onClick={load}
          >
            <RefreshIcon size={16} />
          </button>
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
                        <button
                          type="button"
                          className="icon-btn icon-btn-danger"
                          title="撤销"
                          aria-label={`撤销 ${t.name}`}
                          onClick={() => revoke(t)}
                        >
                          <TrashIcon size={16} />
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
