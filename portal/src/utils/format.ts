// 格式化工具

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '-'
  return n.toLocaleString('zh-CN')
}

export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return '-'
  if (ms < 1000) return `${ms.toFixed(1)} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

export function formatPercent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || Number.isNaN(rate)) return '-'
  return `${(rate * 100).toFixed(2)}%`
}

// 毫秒时间戳 → 本地时间
export function formatTs(ms: number | null | undefined): string {
  if (!ms) return '-'
  const d = new Date(ms)
  const pad = (x: number) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 相对时间（多久前）
export function formatRelative(ms: number | null | undefined): string {
  if (!ms) return '-'
  const diff = Date.now() - ms
  if (diff < 60_000) return `${Math.floor(diff / 1000)} 秒前`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return `${Math.floor(diff / 86_400_000)} 天前`
}

// 秒 → 可读时长（用于 expiresInSeconds 展示）
export function formatSeconds(sec: number | null | undefined): string {
  if (sec === null || sec === undefined || sec === 0) return '永不过期'
  if (sec < 60) return `${sec} 秒`
  if (sec < 3600) return `${(sec / 60).toFixed(0)} 分钟`
  if (sec < 86_400) return `${(sec / 3600).toFixed(0)} 小时`
  return `${(sec / 86_400).toFixed(1)} 天`
}
