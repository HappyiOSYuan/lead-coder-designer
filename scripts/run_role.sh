#!/bin/bash
# 调起编码或设计角色（外部 CLI），模型不锁死：谁来演、用什么模型都在 config.sh。
#
# 用法：
#   run_role.sh coder    -f <任务书.md> [-m 模型]
#   run_role.sh designer -d <设计目录> -f <任务书.md> [-m 模型] [--base <原稿目录>]
#   run_role.sh coder    "<一句话任务>"
#   run_role.sh --probe coder|designer        # 让角色只回复 OK，确认 CLI 和模型可用
#
# 行为：
#   - 读取 config.sh（$SOP_CONFIG → <项目根>/.sop/config.sh → skill 目录 config.sh）
#   - 依次尝试 主模型 → 备用模型：日志里出现适配器声明的额度报错就换下一个
#   - 设计角色：在设计目录里运行，项目根作为可读目录；已有 index.html / handoff.md 先备份成 _rN；
#     结束后自动跑 design_lint.py
#   - 日志写到 $SOP_HOME/logs/<角色>_<时间>.log；结束时只打印最后 30 行（报告段）
#   - stdin 一律接 /dev/null（不少 CLI 在后台会卡在读 stdin）
# 启动建议：用主控代理自己的「后台任务」功能运行本脚本（终端可见、完成会通知），
#          不要用 ( cmd & ) / nohup 脱离启动。

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$HERE")"

project_root() {  # 取最内层的工作区（git 仓库可能包着 svn 检出，例如用 git 管理的家目录）
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

load_config() {
  local c
  for c in "${SOP_CONFIG:-}" "$ROOT/.sop/config.sh" "$SKILL_DIR/config.sh"; do
    if [ -n "$c" ] && [ -f "$c" ]; then
      # shellcheck disable=SC1090
      . "$c"; echo "config: $c" >&2; return 0
    fi
  done
  echo "未找到 config.sh：复制 $SKILL_DIR/config.example.sh 到 $ROOT/.sop/config.sh 并填写" >&2
  exit 2
}

usage() { sed -n 2,19p "$0" >&2; exit 2; }

PROBE=0
if [ "${1:-}" = "--probe" ]; then PROBE=1; shift; fi
ROLE="${1:-}"; shift || true
case "$ROLE" in coder|designer) ;; *) usage ;; esac

TASK="" DIR="" BASE="" MODEL_OVERRIDE=""
while [ $# -gt 0 ]; do
  case "$1" in
    -f) TASK="$(cat "$2")"; shift 2 ;;
    -d) DIR="$2"; shift 2 ;;
    -m) MODEL_OVERRIDE="$2"; shift 2 ;;
    --base) BASE="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) TASK="$1"; shift ;;
  esac
done

load_config
SOP_HOME="${SOP_HOME:-$HOME/.cache/lead-coder-designer}"
mkdir -p "$SOP_HOME/logs"

if [ "$ROLE" = coder ]; then
  ADAPTER="${CODER_ADAPTER:?config 缺 CODER_ADAPTER}"
  MODEL="${MODEL_OVERRIDE:-${CODER_MODEL:-}}"; FALLBACK="${CODER_FALLBACK:-}"
  PREAMBLE="${CODER_PREAMBLE:-}"
  WORKDIR="$ROOT"
else
  ADAPTER="${DESIGNER_ADAPTER:?config 缺 DESIGNER_ADAPTER}"
  MODEL="${MODEL_OVERRIDE:-${DESIGNER_MODEL:-}}"; FALLBACK="${DESIGNER_FALLBACK:-}"
  PREAMBLE="${DESIGNER_PREAMBLE:-}"
  if [ $PROBE -eq 0 ]; then
    [ -n "$DIR" ] || { echo "设计角色需要 -d <设计目录>" >&2; exit 2; }
    case "$DIR" in /*) ;; *) DIR="$ROOT/$DIR" ;; esac
    mkdir -p "$DIR"
    WORKDIR="$DIR"
  else
    WORKDIR="$ROOT"
  fi
fi

ADAPTER_FILE="$HERE/adapters/$ADAPTER.sh"
[ -f "$ADAPTER_FILE" ] || { echo "没有适配器：$ADAPTER_FILE" >&2; exit 2; }
# 适配器提供：adapter_run <model|""> <workdir> <extra_dir|""> <prompt> ；变量 ADAPTER_QUOTA_RE
# shellcheck disable=SC1090
. "$ADAPTER_FILE"

if [ $PROBE -eq 1 ]; then
  TASK="只回复 OK 两个字母，不要做任何其他事。"
  PREAMBLE=""
fi
[ -n "$TASK" ] || usage

PROMPT="$TASK"
[ -n "$PREAMBLE" ] && PROMPT="$PREAMBLE

$TASK"

if [ "$ROLE" = designer ] && [ $PROBE -eq 0 ] && [ -f "$DIR/index.html" ]; then
  n=0; while [ -e "$DIR/index_r${n}.html" ]; do n=$((n+1)); done
  cp "$DIR/index.html" "$DIR/index_r${n}.html"
  [ -f "$DIR/handoff.md" ] && cp "$DIR/handoff.md" "$DIR/handoff_r$n.md"
  echo "备份：index_r${n}.html"
fi

EXTRA=""
[ "$ROLE" = designer ] && [ $PROBE -eq 0 ] && EXTRA="$ROOT"

STAMP="$(date +%Y%m%d_%H%M%S)"
CANDIDATES="${MODEL:-__default__} $FALLBACK"
rc=1
for m in $CANDIDATES; do
  [ "$m" = "__default__" ] && m=""
  LOG="$SOP_HOME/logs/${ROLE}_${STAMP}_${m:-default}.log"
  echo "角色：$ROLE  适配器：$ADAPTER  模型：${m:-默认}  日志：$LOG"
  adapter_run "$m" "$WORKDIR" "$EXTRA" "$PROMPT" < /dev/null > "$LOG" 2>&1
  rc=$?
  if [ -n "${ADAPTER_QUOTA_RE:-}" ] && grep -Eiq "$ADAPTER_QUOTA_RE" "$LOG" \
     && [ "$(wc -l < "$LOG")" -lt 40 ]; then
    echo "额度用完（$(grep -Eio "$ADAPTER_QUOTA_RE" "$LOG" | head -1)）→ 换下一个模型"
    rc=75
    continue
  fi
  break
done

echo "--- 退出码 ${rc}，日志结尾："
grep -v '^[[:space:]]*$' "$LOG" | tail -30

if [ "$ROLE" = designer ] && [ $PROBE -eq 0 ] && [ -f "$DIR/index.html" ]; then
  echo "--- 设计稿自检："
  if [ -n "$BASE" ]; then
    case "$BASE" in /*) ;; *) BASE="$ROOT/$BASE" ;; esac
    python3 -I "$HERE/design_lint.py" "$DIR" --base "$BASE" --limit 5
  else
    python3 -I "$HERE/design_lint.py" "$DIR" --limit 5
  fi
fi
exit $rc
