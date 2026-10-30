# 示例：iOS（UIKit + SwiftUI，svn）项目接入

真实项目脱敏后的接入方式：一个 OC → Swift 迁移中的企业 App，主控 = Claude Code，编码 = Cursor CLI，设计 = Antigravity（Gemini）。

| 文件 | 说明 |
|---|---|
| `config.sh` | 这个项目的角色配置 |
| `AGENTS.excerpt.md` | 项目根 AGENTS.md 的骨架（分工、设计约束、方向门、收尾清单） |
| `rules.py` | 给 `review_diff.py --rules` 用的项目规则插件示例 |
| `brief-example.md` | 一份真实任务书（模拟器验收发现骨架不对之后的修正任务） |

接入步骤：
1. `mkdir .sop && cp config.sh .sop/config.sh`（.sop 加入版本库忽略）
2. 把 `AGENTS.excerpt.md` 改成自己的项目内容，放到项目根 `AGENTS.md`
3. `run_role.sh --probe coder && run_role.sh --probe designer`
