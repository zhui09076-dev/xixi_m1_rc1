# KM 升级包整合审计

## 结论

KM 包覆盖了正确的 M1 模块方向，但原包只是覆盖补丁，不是完整工程，而且原样合并不能启动。
本整合包以 RC3 为唯一基线，带入 Soul、UI、接口协议与 Body 视觉源文件，并修复阻断问题。

## 已修复的阻断项

1. 修复 `Config("config.yaml")` 与点路径读取不兼容。
2. 修复不存在的 `StateManager`、`Constitution`、`setup_logging` 等导入。
3. 修复 Memory、Permission、Task 构造函数收到 Database 对象导致 SQLite 打开失败。
4. 新表改用 `xixi_memory_entries`、`xixi_tasks`、`xixi_permission_requests`、`xixi_audit_logs`，避免与 RC3 旧表同名异构。
5. 保留 RC3 Memory、Task、Permission、LLM 兼容接口。
6. 修复 Lifecycle 与 Container 互相调用造成的无限递归。
7. 修复临时事件循环创建的 aiohttp Session 被跨循环复用。
8. 修复 Body 接口调用不存在的 `get_active_package()`，并正确识别占位 Body 为 degraded。
9. 修复 UI RC1 仅为静态演示、发送与中断不进入后端的问题。
10. 修复 Web 主窗引用不存在的 `DesktopWindow` 和错误的 ChatPanel 方法。
11. 修复停止脚本可能无法命中西西进程的问题，改为 PID 定向停止。
12. 禁用伪沙箱 `eval`，等待独立 tool-worker。

## 当前验收边界

- 可以做代码级、静态资源、数据库隔离、协议信封和内容包校验。
- Windows + PyQt6 + Ollama 的真实启动、界面、流式、中断、权限弹窗与退出仍需在用户电脑上运行验收。
- 当前 Body 视觉源文件不具备正式 `xixi-body` manifest、动作语义和动画资源，因此只能安全降级。
