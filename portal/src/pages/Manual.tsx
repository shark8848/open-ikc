export function Manual() {
  return (
    <>
      <h1 className="page-title">开发手册</h1>
      <p className="page-desc">完整接口定义、鉴权、SDK / MCP / CLI 接入与常见错误排查（服务端离线渲染）。</p>
      <iframe className="manual-frame" src="/api-manual" title="API 开发手册" />
    </>
  )
}
