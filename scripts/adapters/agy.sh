# 适配器：Antigravity CLI（agy，Gemini 模型）
# 无头模式会自动拒绝 shell 命令：任务书里写明「不运行任何命令」，素材由主控提前准备好。
# --print-timeout 必须为 0（非 0 时只打印帮助）。
ADAPTER_QUOTA_RE='RESOURCE_EXHAUSTED|quota reached'

adapter_run() {  # <model> <workdir> <extra_dir> <prompt>
  local model="$1" workdir="$2" extra="$3" prompt="$4" args=(--mode accept-edits --print-timeout 0)
  [ -n "$model" ] && args+=(--model "$model")
  [ -n "$extra" ] && args+=(--add-dir "$extra")
  (cd "$workdir" && agy "${args[@]}" -p "$prompt")
}
