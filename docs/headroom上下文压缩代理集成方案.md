# headroom 上下文压缩代理集成方案（systemd 托管，与 LiteLLM 同款）

> 状态：2026-08-05 已实施（user 级 systemd 运行中）；系统级迁移待 root 执行（命令已备，见 §3.4.3）
> 范围：Claude Code / Codex → headroom proxy → LiteLLM → deepseek-v4-flash 全链路配置、优化与运维手册。

## 1. 方案总览

headroom 是位于客户端与 LLM 网关之间的「上下文优化层」：拦截请求、压缩/去重工具结果与历史上下文，降低输入 token 成本。

### 1.1 目标与背景

此前代理以手动 `setsid` 进程方式运行，存在三个问题：

1. **进程无托管**：重启、崩溃无自愈，会话结束后易丢失。
2. **参数未生效**：`~/.headroom/settings.json` 只供 dashboard / CLI 启动时 `setdefault` 应用，手动/服务直启 `headroom proxy` 不保证读取，`target_ratio=0.3` 等优化值形同虚设。
3. **压缩率低**：37 个请求累计节省仅 4.68%，需要定位根因并给出可调参数。

### 1.2 当前状态清单

| 项 | 状态 | 说明 |
| --- | --- | --- |
| headroom-ai 0.32.1 安装 | ✅ | `/home/litellm/.venv`，含 onnxruntime/torch/transformers（Kompress ONNX 可用） |
| 客户端接入 | ✅ | `~/.claude/settings.json` → `ANTHROPIC_BASE_URL=http://localhost:8787` |
| 优化参数注入 | ✅ | `~/.headroom/headroom.env`，`/proc/<pid>/environ` 已核验 |
| user 级 systemd 服务 | ✅ | `headroom.service` active/enabled，PID 122444，`/health` 200 |
| 开机自启（linger） | ✅ | `loginctl enable-linger sharkyai`（Linger=yes） |
| 系统级服务（root 管理） | ⏳ | `/tmp/headroom.service` 已生成，待 root 执行安装命令（§3.4.3） |

## 2. 架构与请求链路

```text
Claude Code（~/.claude/settings.json: ANTHROPIC_BASE_URL=http://localhost:8787）
Codex（ANTHROPIC_BASE_URL 同左，经 headroom 透传）
        │  Anthropic Messages 协议
        ▼
headroom proxy 127.0.0.1:8787      ← systemd 托管（headroom.service）
  ├─ 内容路由：lossless 变换 + Kompress(ONNX) + tool_search_deferral
  ├─ 会话级压缩缓存：~/.headroom/ccr_store.db
  └─ 日志：~/.headroom/logs/proxy.log、/home/litellm/headroom-proxy.jsonl
        │  OpenAI 协议
        ▼
LiteLLM 127.0.0.1:4000（litellm.service，OPENAI_TARGET_API_URL / ANTHROPIC_TARGET_API_URL）
        ▼
deepseek-v4-flash
```

安全边界：代理只绑定 `127.0.0.1:8787`（loopback-only、无入站 token），不对外暴露。

## 3. 配置全过程

### 3.1 前置条件

- 系统：WSL2 Ubuntu-24.04，已验证 user systemd 可用（`systemctl is-system-running` = running）。
- Python：`>=3.12`（venv 为 3.12）。
- 上游：LiteLLM 已作为系统级服务运行在 `127.0.0.1:4000`（`litellm.service`）。

### 3.2 运行环境（venv）

已有环境（无需重建；重建/迁移参考命令如下）：

| 环境 | 用途 | 关键依赖 |
| --- | --- | --- |
| `/home/litellm/.venv` | 当前托管 headroom proxy | headroom-ai 0.32.1、onnxruntime 1.27、torch 2.13、transformers 5.14（Kompress ONNX 后端可用） |
| `/home/headroom-ai/.venv` | headroom 官方备用环境 | 另含 sentence-transformers / sentencepiece / rapidocr（PyTorch 完整后端） |

```bash
# 如重建（参考）：
python3.12 -m venv /home/litellm/.venv
/home/litellm/.venv/bin/pip install -U "headroom-ai"
# 如需 PyTorch 完整 Kompress 后端（可选，ONNX 已够用）：
/home/litellm/.venv/bin/pip install -U "headroom-ai[ml]"
```

### 3.3 客户端配置（Claude Code / Codex）

#### 3.3.1 Claude Code（已实施）

`~/.claude/settings.json` 的 `env` 节（`ANTHROPIC_AUTH_TOKEN` 已脱敏，不展示真实值）：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8787",
    "ANTHROPIC_AUTH_TOKEN": "<脱敏，占位即可>",
    "ANTHROPIC_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-v4-flash"
  },
  "model": "opus"
}
```

| 键 | 值 | 说明 |
| --- | --- | --- |
| `ANTHROPIC_BASE_URL` | `http://localhost:8787` | 指向 headroom 而非 LiteLLM；headroom 再转发到 `ANTHROPIC_TARGET_API_URL` |
| `ANTHROPIC_AUTH_TOKEN` | 任意非空 | headroom 为 loopback-only、无入站鉴权；上游认证由 headroom.env 的 `OPENAI_API_KEY` 注入 |
| `ANTHROPIC_MODEL` / `*_MODEL` | `deepseek-v4-flash` | 全部模型档位（含子代理）统一映射到 LiteLLM 的 deepseek 模型 |
| `model` | `opus` | Claude Code 默认档位，实际由 `ANTHROPIC_DEFAULT_*_MODEL` 覆盖 |

#### 3.3.2 Codex（已实施）

`~/.codex/config.toml`（原配置备份于 `~/.codex/config.toml.bak.20260805`）：

```toml
model = "deepseek-v4-flash"
model_provider = "headroom"
model_context_window = 1000000

[model_providers.litellm]
name = "LiteLLM"
base_url = "http://localhost:4000"
env_key = "LITELLM_TOKEN"
wire_api = "responses"

[model_providers.headroom]
name = "Headroom Proxy"
base_url = "http://127.0.0.1:8787"
env_key = "LITELLM_TOKEN"
wire_api = "responses"

[projects."/home/open-ikc"]
trust_level = "trusted"
```

| 键 | 值 | 说明 |
| --- | --- | --- |
| `model` | `deepseek-v4-flash` | Codex 请求的模型名，LiteLLM 需已配置该模型别名 |
| `model_provider` | `headroom` | 当前走 headroom；回切改回 `litellm` 即直连 `:4000` |
| `base_url` | `http://127.0.0.1:8787` | 与 litellm 同款不带 `/v1`（Codex 自动追加 `/v1/responses`） |
| `wire_api` | `responses` | 与直连 LiteLLM 时一致；headroom 提供 `/v1/responses`（HTTP+WebSocket）转发到 LiteLLM |
| `env_key` | `LITELLM_TOKEN` | 复用已导出的 token；headroom 为 loopback-only、无入站鉴权，仅需非空 |
| `model_context_window` | `1000000` | 上下文窗口上限，保持原值 |

#### 3.3.3 生效 / 验证 / 回切

- **生效**：两个客户端均在启动时读取配置；Claude Code 重启会话、Codex 退出后重新 `codex` 即生效（当前运行中的会话不受影响）。
- **验证**：`~/.headroom/logs/proxy.log` 的 PERF 行出现 `client=claude-code` / `client=codex`，或 `/home/litellm/headroom-proxy.jsonl` 的 `tags.client` 字段对应。
- **回切（Codex）**：`model_provider` 改回 `litellm`，或 `cp ~/.codex/config.toml.bak.20260805 ~/.codex/config.toml`。
- **回切（Claude Code）**：`ANTHROPIC_BASE_URL` 改回 `http://localhost:4000`（LiteLLM 直连）。

### 3.4 环境变量（headroom.env）

`~/.headroom/headroom.env`（权限 600，**不含真实上游 API key**）：

```bash
HEADROOM_MODE=token
HEADROOM_LOG_FILE=/home/litellm/headroom-proxy.jsonl
HEADROOM_COMPRESS_TOOL_TURNS=1
HEADROOM_TARGET_RATIO=0.3
HEADROOM_SAVINGS_PROFILE=coding
HEADROOM_LOSSLESS=0
OPENAI_TARGET_API_URL=http://127.0.0.1:4000
ANTHROPIC_TARGET_API_URL=http://127.0.0.1:4000
OPENAI_BASE_URL=http://0.0.0.0:4000
OPENAI_API_KEY=sk-litellm-master-key-2024
```

参数表与依据：

| 变量 | 当前值 | 作用 | 依据 |
| --- | --- | --- | --- |
| `HEADROOM_MODE` | `token` | 压缩优先模式（默认 cache 冻结前序轮次） | `cli/proxy.py` envvar |
| `HEADROOM_TARGET_RATIO` | `0.3` | Kompress keep-ratio：保留约 30% tokens，越低越激进；不设置则模型自决（保守） | `cli/proxy.py` envvar（`--target-ratio`） |
| `HEADROOM_SAVINGS_PROFILE` | `coding` | 编码场景节省 profile | `cli/proxy.py` 直读 env |
| `HEADROOM_LOSSLESS` | `0` | 允许有损 Kompress；`=1` 为无 CCR 无损模式 | `cli/proxy.py` envvar（`--lossless`） |
| `HEADROOM_COMPRESS_TOOL_TURNS` | `1` | 对工具轮次内容执行压缩 | 直读 env |
| `HEADROOM_LOG_FILE` | jsonl 路径 | 结构化请求日志（savings/transforms 明细） | 直读 env |

说明：`~/.headroom/settings.json` 中的 `target_ratio` 等值对直启的 proxy 不保证生效，统一以 EnvironmentFile 显式注入为准。

进阶可调参数（未启用，后续按观测启用）：

| 变量 | 默认 | 建议 | 说明 |
| --- | --- | --- | --- |
| `HEADROOM_MIN_TOKENS` | 500 | 400 → 300 梯度下调 | 直接对冲 `ratio_too_high`；注意小块压缩收益低且有 ~1.2s/块推理开销 |
| `HEADROOM_FORCE_KOMPRESS_ALL` | 关 | 需时开 `1` | 对全部可压缩块强制 Kompress，绕过路由收益判断 |
| `HEADROOM_MAX_ITEMS` | 50 | 保持 | crush 后最大条目数 |
| `HEADROOM_MODE=cache` | token | 长会话可切换 | 冻结前序轮次提升上游前缀缓存命中率，与压缩取舍 |

### 3.5 systemd 服务

#### 3.5.1 user 级（已实施，历史方案）

`~/.config/systemd/user/headroom.service`：

```ini
[Unit]
Description=Headroom context optimization proxy (Claude/Codex -> LiteLLM)
Documentation=https://headroom.sh
After=network.target
Wants=network.target

[Service]
Type=simple
WorkingDirectory=/home/litellm
EnvironmentFile=/home/sharkyai/.headroom/headroom.env
ExecStart=/home/litellm/.venv/bin/python /home/litellm/.venv/bin/headroom proxy --host 127.0.0.1 --port 8787 --backend anthropic
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

启用与自启（已执行）：

```bash
systemctl --user daemon-reload
systemctl --user enable --now headroom
loginctl enable-linger sharkyai     # 登录前自启（Linger=yes）
```

注意：`systemctl --user` 依赖 `XDG_RUNTIME_DIR=/run/user/1000`；root/新 shell 下需 `export XDG_RUNTIME_DIR=/run/user/1000`。

#### 3.5.2 系统级（目标方案，与 litellm 同款，root 可直接管理）

unit 预生成于 `/tmp/headroom.service`，与 `litellm.service` 结构完全一致：

```ini
[Unit]
Description=Headroom context optimization proxy (Claude/Codex -> LiteLLM)
After=network.target

[Service]
Type=simple
User=sharkyai
Group=sharkyai
WorkingDirectory=/home/litellm
EnvironmentFile=/home/sharkyai/.headroom/headroom.env
ExecStart=/home/litellm/.venv/bin/python /home/litellm/.venv/bin/headroom proxy --host 127.0.0.1 --port 8787 --backend anthropic
Restart=on-failure
RestartSec=5
StandardOutput=append:/home/litellm/headroom.log
StandardError=append:/home/litellm/headroom.log

[Install]
WantedBy=default.target
```

root 下执行安装（先停 user 级实例释放 8787）：

```bash
sudo -u sharkyai XDG_RUNTIME_DIR=/run/user/1000 systemctl --user disable --now headroom
sudo cp /tmp/headroom.service /etc/systemd/system/headroom.service
sudo systemctl daemon-reload
sudo systemctl enable --now headroom
systemctl status headroom --no-pager | head -8   # root 或任意用户均可，无需 --user
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/
```

迁移后效果：

- root（或任意用户）直接 `systemctl status headroom`，无需 `--user`。
- 开机自动启动走系统 `default.target`，不依赖登录会话；`loginctl enable-linger` 可保留亦可撤销。
- 管理命令与 litellm 完全同款：`sudo systemctl restart/stop/disable --now headroom`、`journalctl -u headroom -n 100`。
- 日志：stdout/stderr append 到 `/home/litellm/headroom.log`；业务日志仍在 `~/.headroom/logs/proxy.log` 与 `/home/litellm/headroom-proxy.jsonl`。

#### 3.5.3 日志文件清单

| 文件 | 内容 |
| --- | --- |
| `~/.headroom/logs/proxy.log` | headroom 业务日志（含 PERF 每请求统计、route_counts、Kompress 事件） |
| `/home/litellm/headroom-proxy.jsonl` | 结构化请求日志（savings_percent、transforms_applied、waste_signals） |
| `/home/litellm/headroom.log` | 系统级服务的 stdout/stderr（迁移后） |
| `~/.headroom/proxy_savings.json` | 会话级累计节省（会话结束刷新） |

### 3.6 验证

```bash
# 1) 健康检查
curl -s -o /dev/null -w '%{http_code}\n' --max-time 3 http://127.0.0.1:8787/     # 期望 200

# 2) 确认参数已注入到进程
tr '\0' '\n' < /proc/$(pgrep -f 'headroom proxy --host' | head -1)/environ \
  | rg 'HEADROOM_TARGET_RATIO|HEADROOM_SAVINGS_PROFILE|HEADROOM_LOSSLESS'

# 3) 压缩率统计（PERF 行）
rg 'PERF' ~/.headroom/logs/proxy.log | wc -l

# 4) 累计节省（savings_percent）
cat ~/.headroom/proxy_savings.json   # lifetime.savings_percent

# 5) 单请求明细
tail -5 /home/litellm/headroom-proxy.jsonl   # savings_percent / transforms_applied
```

## 4. 压缩效果与根因分析

### 4.1 基线（优化前，13:41–14:01，37 请求）

| 指标 | 值 |
| --- | --- |
| 总输入 tokens（优化前） | 852,833 |
| 优化后输入 | 812,887 |
| 累计节省 | 39,946（**4.68%**） |
| 单请求中位节省 | 0.39% |
| Kompress 单块推理耗时 | 1.1–1.8 s（ONNX） |
| Kompress keep-ratio | 0.54–1.00，单块省 0–392 tokens |

### 4.2 新会话（systemd 重启后，14:14–14:17，11 请求）

| 指标 | 值 |
| --- | --- |
| 原始输入 | 582,089 tokens |
| 优化后输入 | 569,230 tokens |
| 压缩节省 | 12,859（**2.21%**，中位 2.17%） |
| 额外延迟注入 | tool_search_deferral 平均 ~21k tokens/请求（31 个工具）未计入压缩 |
| Kompress | 14:14:12 ONNX 后台加载成功，code/text/tool 块按 0.07–0.24 保留比压缩 |
| 压缩时延 | 优化约 0.4–6.4s/请求 |

### 4.3 路由决策分布（新会话）

`content_blocks=51–69, ratio_too_high=28–37, cache_hit=29–38, small=2–8, compressed=1–4, cross_turn_dedup=7–24, system_msg=6–7, error_protected=8–12, read_protected=4`

主要 transform：`lossless_log`、`tool_schema_compaction`、`cross_turn_dedup`、`tool_search_deferral`、`read_lifecycle:stale`。

### 4.4 根因结论

1. **`ratio_too_high` 28–37 块被拒**：内容块小于 `HEADROOM_MIN_TOKENS`（默认 500）或压缩收益不足，路由直接跳过——这是最大的未压缩蛋糕。
2. **`cache_hit` 29–38**：同轮/跨轮重复内容走缓存，不重复压缩（正常行为）。
3. **`lossless_log` 只记录不压缩**：占绝大多数 transform 调用，token 没有减少。
4. **JSON 膨胀未折叠**：`waste_signals.json_bloat` 每请求约 12–13k tokens（工具结果 JSON 格式化冗余），当前变换仅打日志。
5. **Kompress 覆盖面窄**：仅少量 content block 被执行（`compressed=1–4`），且默认 keep-ratio 由模型保守自决；新会话已按 0.07–0.24 保留比压缩。
6. **当前最大节省来自 tool_search_deferral**（每请求约 31 个工具 / 21k tokens 延迟注入），属「延迟」而非「压缩」。

结论：压缩率低的直接原因是**大量小块被路由拒绝 + 有损压缩未被充分启用**，而非代理不工作。单请求压缩率受内容结构（受保护 system/error 消息占比）影响，参数与进程本身均已确认生效。

## 5. 已知问题与排障

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 启动横幅 `Kompress: not installed` | 显示缺陷：eager 状态为 `deferred`（首请求 lazy load），未映射为 banner 的 `enabled`；实际 ONNX 加载正常 | 以运行日志为准（`Kompress slow compress backend=onnx` / `Kompress ONNX loaded`） |
| 首次请求前 `Kompress: downloading model chopratejas/kompress-v2-base in the background` | 模型后台下载（缓存于 `~/.cache/huggingface/hub/models--chopratejas--kompress-v2-base`），期间请求不压缩 | 等待 `Kompress ONNX loaded` 日志出现即可；可预热 `curl -X POST .../v1/messages` 空请求触发 |
| `systemctl status headroom` 报 Unit not found | user 级服务需 `--user` | `systemctl --user status headroom`；迁移系统级后无需 |
| 系统级迁移时 8787 端口冲突 | user 级实例仍占用端口 | 先 `systemctl --user disable --now headroom` 再启用系统级 |
| 修改 headroom.env 不生效 | systemd 缓存环境 | `systemctl --user restart headroom`（或系统级 `sudo systemctl restart headroom`） |

## 6. 管理命令速查

```bash
# user 级（当前）
systemctl --user status|restart|stop|start headroom
systemctl --user enable|disable --now headroom
journalctl --user -u headroom -n 100

# 系统级（迁移后，root/任意用户）
systemctl status|restart|stop|start headroom
systemctl enable|disable --now headroom
journalctl -u headroom -n 100

# 直查
curl -s http://127.0.0.1:8787/health
pgrep -af 'headroom proxy --host'
```

## 7. 回滚方案

```bash
# 系统级 → user 级
sudo systemctl disable --now headroom
sudo rm /etc/systemd/system/headroom.service && sudo systemctl daemon-reload
systemctl --user enable --now headroom

# user 级 → 手动进程（临时）
systemctl --user disable --now headroom
setsid nohup env $(cat /home/sharkyai/.headroom/headroom.env | xargs) \
  /home/litellm/.venv/bin/python /home/litellm/.venv/bin/headroom proxy \
  --host 127.0.0.1 --port 8787 --backend anthropic >> ~/.headroom/logs/proxy.log 2>&1 &

# 回到保守参数：注释 headroom.env 中 TARGET_RATIO / SAVINGS_PROFILE / LOSSLESS 行后重启服务
```

切换期间代理短暂不可用（Claude Code 可能报连接错误），属正常现象。

## 8. 后续调参建议

1. 观察 24h 新参数下的 PERF 统计；若累计压缩率仍 <5%，优先把 `HEADROOM_MIN_TOKENS` 下调至 400/300 并评估 `HEADROOM_FORCE_KOMPRESS_ALL=1`。
2. 工具结果 JSON 膨胀（每请求 12–13k tokens）是最大浪费信号，后续可关注 headroom 的 lossless 折叠/表格压缩变换是否可显式开启。
3. 如需 PyTorch 完整 Kompress 后端，可把 ExecStart 切换到 `/home/headroom-ai/.venv` 或安装 `headroom-ai[ml]`；当前 ONNX 后端已够用。
4. 代理进程由 systemd 托管后，重启策略 `Restart=on-failure` 覆盖崩溃自愈；LiteLLM(4000) 与模型层仍为独立进程。

## 9. 变更记录

- 2026-08-05 14:05：写入优化参数 settings.json（后确认对直启 proxy 不生效）。
- 2026-08-05 14:06–14:07：以 env 注入 + setsid 临时验证参数生效（/health 200）。
- 2026-08-05 14:10：创建 `~/.headroom/headroom.env`（权限 600）与 `~/.config/systemd/user/headroom.service`。
- 2026-08-05 14:11：停临时进程，`systemctl --user enable --now headroom`，健康检查 200；env 注入经 `/proc/<pid>/environ` 核验。
- 2026-08-05 14:14：Kompress ONNX 后台下载并加载成功（keep-ratio 0.07–0.24）；新会话 11 请求压缩 2.21% + deferral ~21k tokens/请求。
- 2026-08-05 14:20：`loginctl enable-linger sharkyai`（Linger=yes），user 级开机自启完成。
- 2026-08-05 14:24：按 `litellm.service` 同款生成系统级 unit `/tmp/headroom.service`，安装命令写入 §3.5.2；本文档同步全量配置过程。
