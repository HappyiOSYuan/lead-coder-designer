# 适配器：OpenAI Codex CLI（codex exec）
# 沙箱 workspace-write：只能写工作目录（和 --add-dir），通常不能写编译缓存，适合设计或不编译的编码。
ADAPTER_QUOTA_RE='rate limit|usage limit|quota|insufficient_quota'

adapter_run() {  # <model> <workdir> <extra_dir> <prompt>
  local model="$1" workdir="$2" extra="$3" prompt="$4" args=(exec -s workspace-write --skip-git-repo-check -C "$workdir")
  [ -n "$model" ] && args+=(-m "$model")
  [ -n "$extra" ] && args+=(--add-dir "$extra")
  codex "${args[@]}" "$prompt"
}
