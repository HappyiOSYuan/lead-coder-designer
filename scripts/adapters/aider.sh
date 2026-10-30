# 适配器：aider（未在作者机器上实测，按官方参数写）
ADAPTER_QUOTA_RE='rate limit|quota|insufficient_quota|credit balance'

adapter_run() {  # <model> <workdir> <extra_dir> <prompt>
  local model="$1" workdir="$2" prompt="$4" args=(--yes-always --no-auto-commits --message "$prompt")
  [ -n "$model" ] && args+=(--model "$model")
  (cd "$workdir" && aider "${args[@]}")
}
