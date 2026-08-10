// 统一响应壳（对齐后端 errCode/errMsg/data/traceId 协议）
export interface Envelope<T> {
  errCode: string
  errMsg: string
  data: T
  traceId: string
}

// ---------- Overview ----------
export interface OverviewData {
  concurrency: number
  totalRequests: number
  errorCount: number
  errorRate: number
  activeEndpoints: number
  activeTokens: number
  detailWindowSeconds: number
}

// ---------- Endpoints ----------
export interface EndpointStat {
  path: string
  method: string
  total: number
  success: number
  error: number
  errorRate: number
  avgMs: number
  minMs: number
  maxMs: number
}

// ---------- Token ----------
export type TokenStatus = 'active' | 'revoked'

export interface TokenRecord {
  id: number
  name: string
  owner: string
  scopes: string[] | null
  status: TokenStatus
  createdAt: number
  expiresAt: number | null
  lastUsedAt: number | null
  expired: boolean
}

export interface CreateTokenPayload {
  name: string
  owner?: string
  scopes?: string[]
  expiresInSeconds?: number
}

export interface CreateTokenResult extends TokenRecord {
  token: string
  notice: string
}

// ---------- 最近请求 ----------
export interface RecentRequest {
  ts: number
  path: string
  method: string
  statusCode: number
  errCode: string
  durationMs: number
  clientIp: string
}

// ---------- Token 维度统计 ----------
export interface TokenStat {
  tokenId: number
  tokenName: string
  total: number
  success: number
  error: number
  errorRate: number
}

// ---------- MCP/CLI 测试 ----------
export interface TestWhitelist {
  cli: string[]
  mcpTools: string[]
}

export interface TestResultData {
  ok: boolean
  command: string
  exitCode: number | null
  stdout: string
  stderr: string
  durationMs: number
  detail: Record<string, unknown>
}

export interface McpTestPayload {
  tool?: string
  token?: string
  baseUrl?: string
}

export interface CliTestPayload {
  command: string
  args?: string[]
  token?: string
  baseUrl?: string
  identity?: Record<string, string> | null
}
