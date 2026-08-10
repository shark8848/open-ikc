// Admin API 客户端：统一处理 /admin/* 请求、admin token 注入与统一响应壳解包。
import type {
  CliTestPayload,
  CreateTokenPayload,
  CreateTokenResult,
  EndpointStat,
  Envelope,
  McpTestPayload,
  OverviewData,
  RecentRequest,
  TestResultData,
  TestWhitelist,
  TokenRecord,
  TokenStat,
} from './types'

const TOKEN_STORAGE_KEY = 'open-ikc-admin-token'
const DEFAULT_BASE = '' // 同源部署（FastAPI 挂载 /portal），开发时由 vite proxy 转发

export function getAdminToken(): string {
  return sessionStorage.getItem(TOKEN_STORAGE_KEY) ?? ''
}

export function setAdminToken(token: string): void {
  sessionStorage.setItem(TOKEN_STORAGE_KEY, token)
}

export function clearAdminToken(): void {
  sessionStorage.removeItem(TOKEN_STORAGE_KEY)
}

export function hasAdminToken(): boolean {
  return getAdminToken().length > 0
}

class ApiError extends Error {
  errCode: string
  constructor(errCode: string, errMsg: string) {
    super(`${errMsg} (${errCode})`)
    this.errCode = errCode
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAdminToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(init?.headers as Record<string, string> | undefined),
  }
  const resp = await fetch(`${DEFAULT_BASE}${path}`, { ...init, headers })
  // 后端将业务错误统一以 HTTP 200 承载（errCode 区分），此处解析统一壳。
  let body: Envelope<T>
  try {
    body = (await resp.json()) as Envelope<T>
  } catch {
    throw new ApiError('999999', `非 JSON 响应 (HTTP ${resp.status})`)
  }
  if (body.errCode !== '000000') {
    throw new ApiError(body.errCode, body.errMsg || '请求失败')
  }
  return body.data
}

export const adminApi = {
  getAdminToken,
  setAdminToken,
  clearAdminToken,
  hasAdminToken,

  // 总览
  overview(): Promise<OverviewData> {
    return request<OverviewData>('/admin/overview')
  },

  // 端点维度
  endpoints(windowMinutes?: number): Promise<EndpointStat[]> {
    const q = windowMinutes ? `?window_minutes=${windowMinutes}` : ''
    return request<EndpointStat[]>(`/admin/endpoints${q}`)
  },

  // 最近请求
  recentRequests(limit = 50): Promise<RecentRequest[]> {
    return request<RecentRequest[]>(`/admin/requests?limit=${limit}`)
  },

  // Token 维度统计
  tokenStats(windowMinutes?: number): Promise<TokenStat[]> {
    const q = windowMinutes ? `?window_minutes=${windowMinutes}` : ''
    return request<TokenStat[]>(`/admin/stats/token${q}`)
  },

  // Token 管理
  listTokens(includeRevoked = false): Promise<TokenRecord[]> {
    return request<TokenRecord[]>(`/admin/tokens?include_revoked=${includeRevoked}`)
  },
  createToken(payload: CreateTokenPayload): Promise<CreateTokenResult> {
    return request<CreateTokenResult>('/admin/tokens', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  revokeToken(tokenId: number): Promise<{ revoked: boolean }> {
    return request<{ revoked: boolean }>(`/admin/tokens/${tokenId}/revoke`, { method: 'POST' })
  },

  // MCP / CLI 在线测试
  testWhitelist(): Promise<TestWhitelist> {
    return request<TestWhitelist>('/admin/test/whitelist')
  },
  testMcp(payload: McpTestPayload): Promise<TestResultData> {
    return request<TestResultData>('/admin/test/mcp', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  testCli(payload: CliTestPayload): Promise<TestResultData> {
    return request<TestResultData>('/admin/test/cli', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
