# 适配器：Claude Code（claude -p，无头模式）
ADAPTER_QUOTA_RE='usage limit|rate limit|quota|credit balance'

adapter_run() {  # <model> <workdir> <extra_dir> <prompt>
  local model="$1" workdir="$2" extra="$3" prompt="$4" args=(-p --permission-mode acceptEdits)
  [ -n "$model" ] && args+=(--model "$model")
  [ -n "$extra" ] && args+=(--add-dir "$extra")
  (cd "$workdir" && claude "${args[@]}" "$prompt")
}
