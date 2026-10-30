# lead-coder-designer 配置。复制到 <项目根>/.sop/config.sh 后修改。
# run_role.sh 查找顺序：$SOP_CONFIG → <项目根>/.sop/config.sh → 本 skill 目录下的 config.sh
# 项目根 = 执行命令时所在 git/svn 工作区的根（找不到就用当前目录）。

# ---- 编码角色 ----
# 可选适配器：cursor-agent | codex | claude | agy | aider（见 scripts/adapters/）
CODER_ADAPTER="cursor-agent"
CODER_MODEL=""                      # 留空 = 该 CLI 的默认模型
CODER_FALLBACK=""                   # 空格分隔；额度用完时依次尝试，如 "claude-opus-5-5-medium"

# ---- 设计角色 ----
DESIGNER_ADAPTER="agy"
DESIGNER_MODEL=""                   # 如 "gemini-4-argon-high"
DESIGNER_FALLBACK=""                # 如 "gemini-3.8-flash-high"
DESIGN_DIR="DesignMockups"          # 设计稿根目录（相对项目根），建议加入版本库忽略

# ---- 运行目录 ----
SOP_HOME="${SOP_HOME:-${HOME}/.cache/lead-coder-designer}"   # 任务书、日志、快照放这里，不进工程目录

# ---- 交给设计角色的固定前言（每次自动加在任务书前面）----
DESIGNER_PREAMBLE="你是 AGENTS.md 里的设计角色：只做设计。只写当前目录；不改工程代码，不运行任何 shell 命令。"

# ---- 交给编码角色的固定前言 ----
CODER_PREAMBLE="你是 AGENTS.md 里的编码角色：先读项目根 AGENTS.md，按任务书改代码，只改任务范围内的文件，按收尾清单自检后用简短报告结束。不要提交版本库。"
