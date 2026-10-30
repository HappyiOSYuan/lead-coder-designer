# 适配器：Cursor CLI（cursor-agent）
# 注意：cursor-agent 会把 --model 记成新的默认模型，这里跑完把配置还原。
ADAPTER_QUOTA_RE='usage limit|quota|out of (fast |premium )?requests|exceeded.*(limit|usage)|limit (reached|exceeded)|upgrade (your|to) (plan|pro)|insufficient (credits|balance)|spend limit'

adapter_run() {  # <model> <workdir> <extra_dir> <prompt>
  local model="$1" workdir="$2" prompt="$4" cfg="$HOME/.cursor/cli-config.json" bak="" rc
  if [ -n "$model" ] && [ -f "$cfg" ]; then bak="$(mktemp)"; cp "$cfg" "$bak"; fi
  if [ -n "$model" ]; then
    cursor-agent -p --trust --force --workspace "$workdir" --model "$model" "$prompt"
  else
    cursor-agent -p --trust --force --workspace "$workdir" "$prompt"
  fi
  rc=$?
  if [ -n "$bak" ]; then cp "$bak" "$cfg"; rm -f "$bak"; fi
  return $rc
}
