# review_diff.py --rules 插件示例：只检查新增行。
# (编号, 级别 error|warn, 正则, 扩展名元组或 None, 说明)
RULES = [
    ("P01", "error", r"\b(viewToTop|navigationFullHeight)\b", (".swift", ".m"),
     "顶部布局用 SnapKit/Masonry 约束到 safeAreaLayoutGuide.top，不手算导航栏高度"),
    ("P02", "warn", r"@objc(Members)?\b", (".swift",),
     "@objc 只在 OC 引用或运行时需要时加"),
    ("P03", "warn", r"setNavigationBarHidden\(true|isNavigationBarHidden\s*=\s*true", (".swift", ".m"),
     "不隐藏系统导航栏"),
    ("P04", "error", r"\bhasLoadedOnce\b", (".swift",),
     "宿主 VC 按 willAppear 骨架 → didAppear 加载，不用 hasLoadedOnce"),
    ("P05", "warn", r"\b(showHud|showHUD|SVProgressHUD\.show)\b", (".swift", ".m"),
     "加载数据用骨架，提交用按钮内转圈，不用全屏 HUD"),
    ("P06", "warn", r"\.truncationMode\(\.middle\)", (".swift",),
     "文件名截断保留开头 + 扩展名，不用中间截断"),
]
