import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/client'
import type { OverviewData, RecentRequest } from '../api/types'
import { Empty, ErrCodeBadge, ErrorBox, Loading, MethodChip, StatCard } from '../components/ui'
import { formatMs, formatNumber, formatPercent, formatRelative } from '../utils/format'

export function Dashboard() {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [requests, setRequests] = useState<RecentRequest[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [ov, reqs] = await Promise.all([adminApi.overview(), adminApi.recentRequests(50)])
      setOverview(ov)
      setRequests(reqs)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    // 每 10 秒自动刷新
    const timer = setInterval(load, 10_000)
    return () => clearInterval(timer)
  }, [load])

  if (loading && !overview) return <Loading text="加载总览…" />
  if (error && !overview) return <ErrorBox message={error} />

  const errorRateTone = (r: number) => (r === 0 ? 'ok' : r < 0.05 ? 'warn' : 'err') as 'ok' | 'warn' | 'err'

  return (
    <>
      <h1 className="page-title">总览</h1>
      <p className="page-desc">
        平台运行状态与最近请求明细，每 10 秒自动刷新。
        {overview ? ` 明细窗口：${Math.round(overview.detailWindowSeconds / 60)} 分钟` : ''}
      </p>

      {error ? <ErrorBox message={error} /> : null}

      {overview ? (
        <>
          <div className="stat-grid">
            <StatCard
              label="当前并发"
              value={formatNumber(overview.concurrency)}
              tone={overview.concurrency > 0 ? 'ok' : ''}
            />
            <StatCard
              label="总请求（窗口内）"
              value={formatNumber(overview.totalRequests)}
            />
            <StatCard
              label="活跃端点"
              value={formatNumber(overview.activeEndpoints)}
            />
            <StatCard
              label="错误数"
              value={formatNumber(overview.errorCount)}
              tone={overview.errorCount > 0 ? 'err' : 'ok'}
            />
            <StatCard
              label="错误率"
              value={formatPercent(overview.errorRate)}
              tone={errorRateTone(overview.errorRate)}
            />
            <StatCard label="活跃 Token" value={formatNumber(overview.activeTokens)} />
          </div>

          <div className="card">
            <div className="card-title">最近请求</div>
            <div className="table-wrap">
              {requests.length === 0 ? (
                <Empty text="暂无请求记录（发送过业务请求后这里会出现）" />
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>方法</th>
                      <th>路径</th>
                      <th>状态</th>
                      <th>errCode</th>
                      <th>耗时</th>
                      <th>来源 IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map((r, i) => (
                      <tr key={i}>
                        <td className="nowrap muted">{formatRelative(r.ts)}</td>
                        <td><MethodChip method={r.method} /></td>
                        <td className="mono">{r.path}</td>
                        <td>
                          {r.statusCode >= 400 ? (
                            <span className="badge badge-err">{r.statusCode}</span>
                          ) : (
                            <span className="badge badge-ok">{r.statusCode}</span>
                          )}
                        </td>
                        <td><ErrCodeBadge errCode={r.errCode} /></td>
                        <td>{formatMs(r.durationMs)}</td>
                        <td className="mono muted">{r.clientIp}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </>
      ) : (
        <Loading />
      )}
    </>
  )
}
