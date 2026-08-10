import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/client'
import type { TestResultData, TestWhitelist } from '../api/types'
import { ErrorBox } from '../components/ui'
import { formatMs } from '../utils/format'

export function TestLab() {
  const [whitelist, setWhitelist] = useState<TestWhitelist | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  // 公共参数：token / baseUrl
  const [token, setToken] = useState('')
  const [baseUrl, setBaseUrl] = useState('http://127.0.0.1:18000')

  // MCP 冒烟
  const [mcpTool, setMcpTool] = useState('sys_catalog')
  const [mcpRunning, setMcpRunning] = useState(false)
  const [mcpResult, setMcpResult] = useState<TestResultData | null>(null)

  // CLI
  const [cliCommand, setCliCommand] = useState('sys-catalog')
  const [cliArgs, setCliArgs] = useState('')
  const [cliRunning, setCliRunning] = useState(false)
  const [cliResult, setCliResult] = useState<TestResultData | null>(null)

  const loadWhitelist = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setWhitelist(await adminApi.testWhitelist())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadWhitelist()
  }, [loadWhitelist])

  async function runMcp() {
    setMcpRunning(true)
    setMcpResult(null)
    try {
      setMcpResult(
        await adminApi.testMcp({
          tool: mcpTool,
          token: token || undefined,
          baseUrl: baseUrl || undefined,
        }),
      )
    } catch (e) {
      setMcpResult({
        ok: false,
        command: `mcp smoke (tool=${mcpTool})`,
        exitCode: null,
        stdout: '',
        stderr: e instanceof Error ? e.message : String(e),
        durationMs: 0,
        detail: {},
      })
    } finally {
      setMcpRunning(false)
    }
  }

  async function runCli() {
    setCliRunning(true)
    setCliResult(null)
    const args = cliArgs
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((a) => a.replace(/^"(.*)"$/, '$1'))
    try {
      setCliResult(
        await adminApi.testCli({
          command: cliCommand,
          args,
          token: token || undefined,
          baseUrl: baseUrl || undefined,
        }),
      )
    } catch (e) {
      setCliResult({
        ok: false,
        command: cliCommand,
        exitCode: null,
        stdout: '',
        stderr: e instanceof Error ? e.message : String(e),
        durationMs: 0,
        detail: {},
      })
    } finally {
      setCliRunning(false)
    }
  }

  function renderResult(result: TestResultData | null, title: string) {
    if (!result) return null
    return (
      <div style={{ marginTop: 14 }}>
        <div className="toolbar" style={{ marginBottom: 8 }}>
          <span className={`badge ${result.ok ? 'badge-ok' : 'badge-err'}`}>
            {result.ok ? '通过' : '未通过'}
          </span>
          <span className="muted mono">{result.command}</span>
          {result.exitCode !== null && result.exitCode !== undefined ? (
            <span className="muted">退出码 {result.exitCode}</span>
          ) : null}
          <span className="muted">{formatMs(result.durationMs)}</span>
        </div>
        {result.stdout ? (
          <>
            <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>stdout</div>
            <div className="output-box">{result.stdout}</div>
          </>
        ) : null}
        {result.stderr ? (
          <>
            <div className="muted" style={{ fontSize: 12, margin: '10px 0 4px' }}>stderr</div>
            <div className="output-box" style={{ color: 'var(--err)' }}>{result.stderr}</div>
          </>
        ) : null}
        {Object.keys(result.detail).length > 0 ? (
          <>
            <div className="muted" style={{ fontSize: 12, margin: '10px 0 4px' }}>detail</div>
            <div className="output-box">{JSON.stringify(result.detail, null, 2)}</div>
          </>
        ) : null}
        <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
          {title}
        </p>
      </div>
    )
  }

  return (
    <>
      <h1 className="page-title">在线测试</h1>
      <p className="page-desc">
        通过后端 subprocess 真实执行 SDK 的 MCP / CLI 命令，验证接入链路。
        命令受白名单限制，仅允许只读操作。
      </p>

      {error ? <ErrorBox message={error} /> : null}

      {/* 公共参数 */}
      <div className="card">
        <div className="card-title">公共参数</div>
        <div className="form-row">
          <div className="form-field" style={{ flex: 1, minWidth: 200 }}>
            <label>接入 token（可选，业务 token）</label>
            <input type="password" placeholder="留空则使用平台环境变量 token" value={token} onChange={(e) => setToken(e.target.value)} />
          </div>
          <div className="form-field" style={{ flex: 1, minWidth: 200 }}>
            <label>平台地址</label>
            <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </div>
        </div>
      </div>

      {/* MCP 冒烟 */}
      <div className="card">
        <div className="card-title">MCP 冒烟测试</div>
        <p className="muted" style={{ margin: '0 0 12px', fontSize: 12 }}>
          执行 initialize → list_tools → call_tool 全链路，验证 stdio MCP Server 与平台连通。
        </p>
        <div className="form-row">
          <div className="form-field">
            <label>工具</label>
            <select value={mcpTool} onChange={(e) => setMcpTool(e.target.value)}>
              {loading ? <option>加载白名单…</option> : null}
              {whitelist?.mcpTools.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <button className="btn" disabled={mcpRunning} onClick={runMcp}>
            {mcpRunning ? '执行中…' : '运行 MCP 冒烟'}
          </button>
        </div>
        {renderResult(mcpResult, 'MCP 冒烟为真实 subprocess 执行（.venv/bin/python -m open_ikc_sdk.mcp），耗时约数秒。')}
      </div>

      {/* CLI 命令 */}
      <div className="card">
        <div className="card-title">CLI 命令执行</div>
        <p className="muted" style={{ margin: '0 0 12px', fontSize: 12 }}>
          执行白名单内的 SDK CLI 命令（只读）。参数以空格分隔，如 <span className="mono">--page 1 --page-size 10</span>。
        </p>
        <div className="form-row">
          <div className="form-field">
            <label>命令</label>
            <select value={cliCommand} onChange={(e) => setCliCommand(e.target.value)}>
              {loading ? <option>加载白名单…</option> : null}
              {whitelist?.cli.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="form-field" style={{ flex: 1, minWidth: 240 }}>
            <label>参数</label>
            <input type="text" placeholder="如 --page 1 --page-size 10" value={cliArgs} onChange={(e) => setCliArgs(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && runCli()} />
          </div>
          <button className="btn" disabled={cliRunning} onClick={runCli}>
            {cliRunning ? '执行中…' : '运行'}
          </button>
        </div>
        {renderResult(cliResult, 'CLI 经后端 subprocess 真实执行，超时 20 秒，非白名单命令将被拒绝。')}
      </div>
    </>
  )
}
