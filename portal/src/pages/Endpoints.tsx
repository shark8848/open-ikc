import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/client'
import type { EndpointStat, TokenStat } from '../api/types'
import { Empty, ErrorBox, Loading, MethodChip } from '../components/ui'
import { formatMs, formatNumber, formatPercent } from '../utils/format'

const WINDOWS = [
  { label: '最近 30 分钟', value: 30 },
  { label: '最近 1 小时', value: 60 },
  { label: '最近 2 小时', value: 120 },
]

export function Endpoints() {
  const [windowMinutes, setWindowMinutes] = useState<number>(120)
  const [endpoints, setEndpoints] = useState<EndpointStat[]>([])
  const [tokenStats, setTokenStats] = useState<TokenStat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [eps, toks] = await Promise.all([
        adminApi.endpoints(windowMinutes),
        adminApi.tokenStats(windowMinutes),
      ])
      setEndpoints(eps)
      setTokenStats(toks)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [windowMinutes])

  useEffect(() => {
    load()
  }, [load])

  const rateTone = (r: number) => {
    if (r === 0) return 'ok'
    if (r < 0.05) return 'warn'
    return 'err'
  }

  return (
    <>
      <h1 className="page-title">端点监控</h1>
      <p className="page-desc">按端点与 token 维度的请求统计（每分钟聚合窗口）。</p>

      <div className="toolbar">
        {WINDOWS.map((w) => (
          <button
            key={w.value}
            className={`btn btn-sm ${windowMinutes === w.value ? '' : 'btn-ghost'}`}
            onClick={() => setWindowMinutes(w.value)}
          >
            {w.label}
          </button>
        ))}
        <div className="spacer" />
        <button className="btn btn-ghost btn-sm" onClick={load}>刷新</button>
      </div>

      {error ? <ErrorBox message={error} /> : null}

      <div className="card">
        <div className="card-title">端点维度</div>
        {loading ? (
          <Loading />
        ) : endpoints.length === 0 ? (
          <Empty text="当前窗口内暂无端点统计（发送过业务请求后这里会出现）" />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>路径</th>
                  <th>方法</th>
                  <th>总请求</th>
                  <th>成功</th>
                  <th>错误</th>
                  <th>错误率</th>
                  <th>平均耗时</th>
                  <th>最慢</th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map((e, i) => (
                  <tr key={i}>
                    <td className="mono">{e.path}</td>
                    <td><MethodChip method={e.method} /></td>
                    <td>{formatNumber(e.total)}</td>
                    <td style={{ color: 'var(--ok)' }}>{formatNumber(e.success)}</td>
                    <td style={{ color: e.error > 0 ? 'var(--err)' : 'var(--text-dim)' }}>
                      {formatNumber(e.error)}
                    </td>
                    <td>
                      <span className={`badge badge-${rateTone(e.errorRate)}`}>{formatPercent(e.errorRate)}</span>
                    </td>
                    <td>{formatMs(e.avgMs)}</td>
                    <td className="muted">{formatMs(e.maxMs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Token 维度</div>
        {loading ? (
          <Loading />
        ) : tokenStats.length === 0 ? (
          <Empty text="当前窗口内暂无 token 维度统计" />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Token</th>
                  <th>总请求</th>
                  <th>成功</th>
                  <th>错误</th>
                  <th>错误率</th>
                </tr>
              </thead>
              <tbody>
                {tokenStats.map((t, i) => (
                  <tr key={i}>
                    <td>{t.tokenName}</td>
                    <td>{formatNumber(t.total)}</td>
                    <td style={{ color: 'var(--ok)' }}>{formatNumber(t.success)}</td>
                    <td style={{ color: t.error > 0 ? 'var(--err)' : 'var(--text-dim)' }}>
                      {formatNumber(t.error)}
                    </td>
                    <td>
                      <span className={`badge badge-${rateTone(t.errorRate)}`}>{formatPercent(t.errorRate)}</span>
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
