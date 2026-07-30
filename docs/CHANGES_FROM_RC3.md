# 与 RC3 相比的完整修改清单

## 一、新增文件（11个）

| 文件 | 大小 | 说明 |
|------|------|------|
| core/protocol_server.py | ~12KB | xixi/1.0 协议服务器 |
| core/soul_loader.py | ~10KB | Soul 包加载、提示构建、Schema 校验 |
| core/tool_executor.py | ~11KB | 真实工具执行框架 |
| core/body_interface.py | ~7KB | Body 语义意图 + 无资产回退 |
| core/web_bridge.py | ~5KB | QWebChannel 桥接对象 |
| core/task_scheduler.py | ~18KB | 1重+1轻任务调度 |
| core/lifecycle.py | ~14KB | 安装/启动/停止/备份/回滚 |
| ui/web_main_window.py | ~11KB | QWebEngineView 加载 UI RC1 |
| scripts/install.bat | ~2KB | 一键安装 |
| scripts/start.bat | ~1KB | 一键启动 |
| scripts/stop.bat | ~1KB | 一键停止 |

## 二、重写文件（5个）

| 文件 | 修改内容 | 行数变化 |
|------|----------|----------|
| core/llm.py | 可配置上下文、流式生成、模型管理、session安全 | 重写 |
| core/memory.py | 六类记忆、角色隔离、supersede、自然语言控制 | 重写 |
| core/permission_gateway.py | 四级风险、权限弹窗、审计日志 | 重写 |
| core/task_scheduler.py | 状态同步、重启恢复、resume token | 重写 |
| main.py | Container类、生命周期集成、任务调度集成 | 重写 |

## 三、修改文件（3个）

| 文件 | 修改内容 |
|------|----------|
| core/__init__.py | 导出新类：ProtocolServer, SoulPackage, ToolExecutor, BodyInterface, WebBridge, LifecycleManager |
| config.yaml | 添加 protocol 段（host/port/heartbeat）、soul 段（path/verify_checksums） |
| requirements.txt | 添加 jsonschema>=4.17.0, PyQt6-WebEngine>=6.4.0 |

## 四、保留未修改的文件（18个）

| 文件 | 说明 |
|------|------|
| core/asset_manager.py | 资产包管理，无需修改 |
| core/config.py | 配置加载，兼容新字段 |
| core/constitution.py | 简化版保留，Soul包优先 |
| core/database.py | 数据库基类，MemoryManager扩展了表 |
| core/identity.py | 身份管理，兼容 |
| core/intent_classifier.py | 意图分类，兼容 |
| core/logger.py | 日志系统，兼容 |
| core/state.py | 状态机，兼容 |
| core/system_monitor.py | 系统监控，兼容 |
| core/version_registry.py | 版本注册，兼容 |
| host/__init__.py | 宿主层导出 |
| host/dpi.py | DPI管理 |
| host/system_tray.py | 系统托盘 |
| host/window.py | 桌面窗口 |
| renderer/__init__.py | 渲染层导出 |
| renderer/base.py | 渲染器基类 |
| renderer/qt_renderer.py | Qt渲染器 |
| tests/*.py | 测试套件，需更新以覆盖新功能 |

## 五、架构变化

### RC3 架构
```
用户 -> Qt UI -> core (简化Soul/LLM/Memory/Permission) -> Ollama
```

### 最终架构
```
用户 -> UI RC1 (QWebEngineView) 
     -> WebBridge -> ProtocolServer (xixi/1.0)
     -> Container -> SoulLoader (manifest校验/checksum/提示构建)
                  -> LLMEngine (流式/可配置上下文/模型管理)
                  -> MemoryManager (六类记忆/supersede/角色隔离)
                  -> PermissionGateway (四级风险/审计)
                  -> ToolExecutor (真实执行/结果回传)
                  -> BodyInterface (语义意图/无资产回退)
                  -> TaskScheduler (1重1轻/状态同步/恢复)
                  -> LifecycleManager (安装/启动/停止/备份/回滚)
     -> Ollama
```

## 六、关键行为变化

| 行为 | RC3 | 最终版 |
|------|-----|--------|
| Soul加载 | 无，使用硬编码提示 | 加载xixi_soul_rc1，校验manifest/checksum |
| 系统提示 | "你是西西，一个友好的桌面伴侣" | 完整宪法+身份+人格+状态+记忆+能力 |
| 上下文长度 | 硬编码8192 | 可配置，默认65536 |
| 流式输出 | 基础实现，有泄漏风险 | 完整实现，每delta立即回调，session安全关闭 |
| 打断 | 无 | 取消生成+停止delta+取消工具+不写记忆 |
| 记忆类型 | 基础表结构 | 六类完整实现+supersede+角色隔离 |
| 权限 | 10级网关框架 | 四级风险+真实弹窗+拒绝阻断+审计 |
| 工具 | 无 | 文件/网页/代码/系统命令真实执行 |
| UI | 占位文本面板 | QWebEngineView加载UI RC1 |
| Body | 无 | 语义意图+无资产安全回退 |
| 任务 | 框架 | 1重1轻+状态同步+重启恢复 |
| 生命周期 | 基础启动 | 安装/启动/停止/备份/回滚/健康检查 |
| 协议 | 无 | xixi/1.0完整实现 |
