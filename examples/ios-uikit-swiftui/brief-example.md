# 任务：审批列表 + 审批详情 骨架改成 SwiftUI 卡片骨架

用户在模拟器反馈：「刚打开的几个页面骨架不对」。原因（主控已查明）：下面 4 个 VC 仍走基类通用 shimmer（`buildSkeleton` 默认实现），SwiftUI 宿主在加载完前隐藏，`isInitialLoading` 的卡片骨架根本看不到；用户看到的是与新卡片布局不符的旧骨架。

## 范围（只改这些 VC，必要时微调对应 View 的骨架）
- `Modules/Approval/Leave/ViewController/LeaveListViewController.swift`
- `Modules/Approval/Overtime/ViewController/OvertimeListViewController.swift`
- `Modules/Approval/Leave/ViewController/LeaveDetailViewController.swift`
- `Modules/Approval/Overtime/ViewController/OvertimeDetailViewController.swift`

## 做法（照搬 `Modules/Request/Overtime/ViewController/RequestOvertimeDetailViewController.swift` L52-125）
- `override func startShimmerLoading() {}`、`override func buildSkeleton() {}`
- 宿主嵌入后即显示；首次加载 `displayState.isInitialLoading = true`，回调里置 false；去掉「加载完再揭开宿主」的调用。
- 下拉刷新不切骨架；错误重试照旧。
- SwiftUI 骨架与真实布局一致：
  - 列表：日期条 + 卡片（16 边距、圆角 14、描边、内衬 14/16；请假 4 行、加班 3 行）。
  - 详情：身份卡 + 内容卡（段头 + 字段行）+ 底部两个等宽按钮占位。
- 列表是分页控制器子页：每个 tab 首次进入都能看到骨架，不出现空白。

## 收尾
规则：宿主 VC、骨架、自检。编译用汇总脚本；`review_diff.py Modules/Approval` error 0。报告改动文件与行。不提交。
