#!/bin/bash
# 主控额度不足时，用备选主控 CLI 临时接管，并通过共用交接文件同步现场。
#
# 用法：
#   takeover_lead.sh              # 启动备选主控，先读 AGENTS.md / MEMORY.md / leader-handoff.md
#   takeover_lead.sh -m MODEL     # 指定本次接管模型
#   takeover_lead.sh -c           # 继续上一次接管会话（需 CLI 支持 -c）
#
# 配置（在 <项目根>/.sop/config.sh 里填写）：
#   LEAD_BACKUP_CLI="agy"                 # 可选：agy | claude | codex 等交互式 CLI
#   LEAD_BACKUP_MODEL="gemini-4-neon-high"
#   SOP_HOME="${HOME}/.cache/lead-coder-designer"
# 交接文件：$SOP_HOME/leader-handoff.md

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$HERE")"

project_root() {
  local g s
  g="$(git rev-parse --show-toplevel 2>/dev/null)"
  s="$(svn info --show-item wc-root 2>/dev/null)"
  if [ -n "$g" ] && [ -n "$s" ]; then
    [ ${#s} -gt ${#g} ] && echo "$s" || echo "$g"
  elif [ -n "$s" ]; then echo "$s"
  elif [ -n "$g" ]; then echo "$g"
  else pwd
  fi
}
ROOT="$(project_root)"

for c in "${SOP_CONFIG:-}" "$ROOT/.sop/config.sh" "$SKILL_DIR/config.sh"; do
  if [ -n "$c" ] && [ -f "$c" ]; then
    # shellcheck disable=SC1090
    . "$c"; break
  fi
done

CLI="${LEAD_BACKUP_CLI:-agy}"
MODEL="${LEAD_BACKUP_MODEL:-}"
CONTINUE=0
while [ $# -gt 0 ]; do
  case "$1" in
    -m) MODEL="$2"; shift 2 ;;
    -c) CONTINUE=1; shift ;;
    -h|--help) sed -n 2,14p "$0" >&2; exit 0 ;;
    *) echo "usage: $0 [-m MODEL] [-c]" >&2; exit 2 ;;
  esac
done

SOP_HOME="${SOP_HOME:-$HOME/.cache/lead-coder-designer}"
HANDOFF="$SOP_HOME/leader-handoff.md"
mkdir -p "$SOP_HOME"
[ -f "$HANDOFF" ] || printf '# 主控交接记录\n\n' > "$HANDOFF"

PROMPT="你现在临时接管本工程（$ROOT）的主控角色（原主控额度不足）。
1. 先读：AGENTS.md（分工、收尾清单）、.agents/MEMORY.md（项目记忆，如有）、$HANDOFF（交接记录）。
2. 主控职责照 AGENTS.md 分工表：定位代码、写任务书、审 diff、看截图验收、与用户沟通；不直接改业务代码，也不直接改设计稿 HTML。
3. 派发编码/设计用 $HERE/run_role.sh；审 diff 用 $HERE/review_diff.py（error 必须为 0）。
4. 不提交版本库。新约定或踩坑写进 .agents/MEMORY.md（一条一行，开头 [标签]），写完跑 python3 -I $HERE/memory_check.py。
5. 每完成或派出一件事，就在 $HANDOFF 末尾追加一行：时间、做了什么、任务书路径、结果或待用户确认事项，方便原主控恢复后接手。
读完后用两三句话告诉用户你接手了什么、现在在等什么，然后等用户指示。"

cd "$ROOT" || exit 1

case "$CLI" in
  agy)
    args=()
    [ -n "$MODEL" ] && args+=(--model "$MODEL")
    if [ $CONTINUE -eq 1 ]; then
      exec agy "${args[@]}" -c
    fi
    exec agy "${args[@]}" --add-dir "$SOP_HOME" -i "$PROMPT"
    ;;
  claude)
    args=()
    [ -n "$MODEL" ] && args+=(--model "$MODEL")
    if [ $CONTINUE -eq 1 ]; then
      exec claude "${args[@]}" -c
    fi
    exec claude "${args[@]}" --add-dir "$SOP_HOME" "$PROMPT"
    ;;
  *)
    echo "暂未内置 $CLI 的交互启动参数，请手动启动后先读：$HANDOFF" >&2
    exit 2
    ;;
esac
