# 运行验收

代码能编译不等于对。每个界面改动都要在真实运行环境里看一眼。

## 流程
1. 主控（或用户）编译安装。约定好谁编译：很多团队是用户在 IDE 里编译。
2. 主控说清楚：打开哪个页面、走到哪个状态（如「点进第一条待审批」）。
3. 用户操作到位后回复「打开了」。主控**只截一张图**。
4. 对照设计稿逐条说：哪些一致、哪些不一致（给出位置和现象），不一致的先查根因再派修正任务。
5. 一闪而过的状态（骨架、转场）截不到：问用户，或录屏后抽帧。

## 截图命令（按平台）
| 平台 | 命令 |
|---|---|
| iOS 模拟器 | `xcrun simctl io booted screenshot out.png`；录屏 `xcrun simctl io booted recordVideo out.mp4` |
| Android 模拟器/真机 | `adb exec-out screencap -p > out.png`；录屏 `adb shell screenrecord /sdcard/a.mp4` |
| Web | 无头浏览器 `--screenshot`，或 Playwright `page.screenshot()` |
| macOS 桌面 | `screencapture -x out.png` |

大图先缩小再看（如 `sips -Z 1000 out.png`），省 token。

## 布局问题拿真实数据
猜不出来的错位：导出视图层级的真实 frame（iOS 用 lldb `recursiveDescription`，Web 用 DevTools 的 computed box），比猜更快。
