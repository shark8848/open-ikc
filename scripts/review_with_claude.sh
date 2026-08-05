#!/usr/bin/env bash
# 用 Claude Code headless（-p）对本仓库当前改动做只读代码+安全审查。
# 用法：scripts/review_with_claude.sh [--since <提交>] [--out <报告路径>]
# 默认审查范围：未提交改动（含未跟踪文件清单）；工作区干净时回退到最近一次提交。
# 默认输出：docs/code-review_<日期>.md（错误日志随报告：<报告>.err）
# 说明：claude CLI 走 Anthropic API 需要网络；Codex 沙箱内执行需沙箱外批准。
set -euo pipefail

# 开关：OPEN_PLATFORM_AUTO_REVIEW=false 时跳过（与 AGENTS.md §13 / README 一致）
if [[ "${OPEN_PLATFORM_AUTO_REVIEW:-true}" != "true" ]]; then
    echo "跳过自动审查（OPEN_PLATFORM_AUTO_REVIEW=false）"
    exit 0
fi

cd "$(dirname "$0")/.."

STAMP="$(date +%Y-%m-%d)"
OUT="docs/code-review_${STAMP}.md"
SINCE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --since) SINCE="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        *) echo "未知参数：$1（支持 --since <提交>、--out <路径>）" >&2; exit 2 ;;
    esac
done

TMP_DIFF="$(mktemp)"
TMP_UNTRACKED="$(mktemp)"
trap 'rm -f "$TMP_DIFF" "$TMP_UNTRACKED"' EXIT

if [[ -n "$SINCE" ]]; then
    SCOPE_DESC="自 ${SINCE} 起的改动"
    if ! git diff "${SINCE}" > "$TMP_DIFF" 2>/dev/null; then
        echo "git diff 失败（--since=${SINCE} 可能不存在），中止审查" >&2
        exit 1
    fi
    DIFF_STAT="$(git diff "${SINCE}" --stat | tail -12)"
elif ! git diff --quiet; then
    SCOPE_DESC="未提交的工作区改动（含未跟踪文件）"
    git diff > "$TMP_DIFF" 2>/dev/null
    DIFF_STAT="$(git diff --stat | tail -12)"
else
    if git rev-parse -q --verify HEAD~1 >/dev/null 2>&1; then
        BASE="$(git log -1 --format='%h %s' HEAD~1)"
        SCOPE_DESC="最近一次提交 ${BASE}"
        git diff HEAD~1 > "$TMP_DIFF" 2>/dev/null
        DIFF_STAT="$(git diff HEAD~1 --stat | tail -12)"
    else
        BASE="$(git log -1 --format='%h %s' HEAD)"
        SCOPE_DESC="首个提交（无 HEAD~1）${BASE}"
        git show HEAD > "$TMP_DIFF" 2>/dev/null
        DIFF_STAT="$(git show HEAD --stat | tail -12)"
    fi
fi

# 未跟踪新文件纳入审查范围（脚本自身等新增文件不会出现在 git diff 中）
git ls-files --others --exclude-standard > "$TMP_UNTRACKED" 2>/dev/null || true
UNTRACKED="$(head -20 "$TMP_UNTRACKED")"
if [[ -n "$UNTRACKED" ]]; then
    DIFF_STAT="${DIFF_STAT}"$'\n'"未跟踪新文件："$'\n'"${UNTRACKED}"
fi

DIFF_TEXT="$(head -c 40000 "$TMP_DIFF")"

echo "审查范围：${SCOPE_DESC}"
echo "生成报告：${OUT}"

CLAUDE_BIN="${CLAUDE_BIN:-claude}"

# --permission-mode plan：机制性只读（禁止写工具）；prompt 文本约束为第二层
# 失败时清理半成品报告，避免空文件残留被误提交
cleanup_partial() {
    rm -f "$OUT" "${OUT}.err"
}

"$CLAUDE_BIN" -p "你是 open-ikc 开放平台 API 的代码与安全审查员。对以下改动做**只读审查，禁止修改任何文件**。审查要点：1) AUTHZ action/资源类型与角色映射一致性；2) 统一响应体与异常链路（errCode/errMsg/data/traceId）；3) 认证/鉴权/凭证与越权风险；4) schema 校验与数据边界；5) 测试覆盖是否支撑行为变更。以下是改动范围摘要与 diff（可能截断；未跟踪新文件可按路径读取核对）：

范围：${SCOPE_DESC}

${DIFF_STAT}

${DIFF_TEXT}

输出 markdown 报告：结论、问题列表（P0/P1/P2）、问题位置（文件:行）、依据与修复建议。" \
    --permission-mode plan --output-format text > "$OUT" 2> "${OUT}.err" || {
    echo "claude 调用失败，错误见 ${OUT}.err" >&2
    cleanup_partial
    exit 1
}

if [[ ! -s "$OUT" ]]; then
    echo "报告为空（claude 无输出），请检查 ${OUT}.err 后重跑" >&2
    cleanup_partial
    exit 1
fi

# claude 无 stderr 输出时清理空 .err，避免提交空文件误导
if [[ ! -s "${OUT}.err" ]]; then
    rm -f "${OUT}.err"
fi

echo "完成：${OUT}"
