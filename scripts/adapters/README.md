# 适配器

每个适配器是一个被 `run_role.sh` source 的 bash 片段，只需提供两样东西：

```bash
ADAPTER_QUOTA_RE='额度用完时日志里会出现的文字（扩展正则，不区分大小写）'

adapter_run() {  # <model> <workdir> <extra_dir> <prompt>
  # model     空 = 用 CLI 默认模型
  # workdir   在这个目录里运行（编码=项目根，设计=设计目录）
  # extra_dir 额外允许读写的目录（设计角色时 = 项目根），可能为空
  # prompt    完整任务文本
  # 要求：非交互、跑完退出、退出码反映成败；输出直接打到 stdout/stderr
}
```

新增一个 CLI：复制最像的一个改参数，然后 `run_role.sh --probe coder` 验证（config 里把 `CODER_ADAPTER` 改成新文件名）。

| 适配器 | 实测 | 备注 |
|---|---|---|
| cursor-agent | 是 | 跑完还原被 `--model` 改掉的默认模型 |
| agy | 是 | 无头不能跑命令；`--print-timeout 0` |
| codex | 是（--probe） | 沙箱 workspace-write |
| claude | 是（--probe） | `--permission-mode acceptEdits` |
| aider | 否 | 按文档参数写，欢迎修正 |
