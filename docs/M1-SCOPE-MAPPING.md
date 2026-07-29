# M1-SCOPE-MAPPING.md
# M1 范围映射与验收表
# Version: M1-RC3

---

## 映射状态定义

| 状态 | 含义 |
|------|------|
| implemented_and_tested | 代码存在、已集成、测试真实运行通过 |
| implemented_not_verified | 代码存在并已集成，但目标 Windows 环境尚未人工验证 |
| interface_only | 只有接口或数据结构，没有完整行为 |
| not_implemented | 未实现 |
| out_of_scope | 明确不属于 M1 |

禁止使用：基本满足、大致完成、已有预留、理论支持、应该可以、文档已完成所以功能完成。

---

## 逐项对照表

| # | 标准 | 规范章节 | 代码模块 | 数据库字段 | M1 状态 | 验收方法 |
|---|------|----------|----------|------------|---------|----------|
| 1 | 唯一 Identity ID (xixi-main)，official=true 唯一 | IDENTITY-SPEC §1 | `core/identity.py` | `identities.official` + UNIQUE 索引 | implemented_and_tested | test_identity.py: 测试只能有一个 official |
| 2 | 脸部身份锚点登记 | IDENTITY-SPEC §2 | `core/identity.py` | `identities.face_anchor_path` | implemented_and_tested | test_identity.py: 测试锚点路径存在 |
| 3 | 模型 ≠ 人格 | PRODUCT-DEF §2.1 | `core/llm.py` + `core/constitution.py` | — | implemented_and_tested | test_constitution.py: 人格从文件加载 |
| 4 | 人格宪法版本化 | PERSONALITY §1 | `core/constitution.py` | — | implemented_and_tested | test_constitution.py: 版本字段存在 |
| 5 | sourceType 分类 | MEMORY-SPEC §2 | `core/database.py` | `memory_entries.source_type` | implemented_and_tested | test_memory_schema.py: 枚举检查 |
| 6 | 原始记录不可覆盖 | MEMORY-SPEC §3 | `core/memory.py` | 纯 INSERT 设计 | implemented_and_tested | test_memory_schema.py: UPDATE content 被拒绝 |
| 7 | 纠正使用 supersedes | MEMORY-SPEC §4 | `core/memory.py` | `memory_entries.supersedes` | implemented_and_tested | test_memory_control.py: 纠正流程验证 |
| 8 | 当前状态持久化 | STATE-MACHINE §3 | `core/state.py` + `main.py` | `current_state.state_json` | implemented_and_tested | test_state_machine.py: 保存后读取不丢字段 |
| 9 | 8 个基础状态 | STATE-MACHINE §1 | `core/state.py` | `current_state.state_json` | implemented_and_tested | test_state_machine.py: 枚举包含 8 个 |
| 10 | 启动分 3 种 | STATE-MACHINE §3 | `core/state.py` | `current_state.boot_mode` | implemented_and_tested | test_startup_modes.py: 三种模式判断 |
| 11 | 状态分层 | STATE-MACHINE §2 | `core/state.py` | `state_json` 含 emotion/attention | implemented_and_tested | test_state_machine.py: 分层字段验证 |
| 12 | 1 重 + 1 轻任务 | ATTENTION §1 | `core/task_scheduler.py` | `tasks` 表 | implemented_and_tested | test_task_scheduler.py: 同时只允许 1H+1L |
| 13 | requiresConfirmation 任务不直接运行 | ATTENTION §3 | `core/task_scheduler.py` | `tasks.requires_confirmation` | implemented_and_tested | test_task_scheduler.py: 确认前 status≠running |
| 14 | 基础权限网关 | PERMISSION §4 | `core/permission_gateway.py` | `audit_logs` 表 | implemented_and_tested | test_permission_gateway.py: 五级权限检查 |
| 15 | ActionRequest + 令牌 | PERMISSION §4 | `core/permission_gateway.py` | — | implemented_and_tested | test_permission_gateway.py: 令牌绑定验证 |
| 16 | 模型不直接执行系统 | PERMISSION §4 | `core/permission_gateway.py` | — | implemented_and_tested | test_permission_gateway.py: 无令牌拒绝 |
| 17 | 版本化 Manifest | PRODUCT-DEF §5 | `core/asset_manager.py` | `asset_packages` 表 | implemented_and_tested | test_asset_manifest.py: 兼容检查 |
| 18 | 数据库迁移 v2→v3 | UPGRADE-SPEC §2 | `core/database.py` | `schema_version` 表 | implemented_and_tested | test_migrations.py: 迁移后旧数据保留 |
| 19 | 自然语言记忆控制 | MEMORY-SPEC §8 | `core/memory.py` + `core/intent_classifier.py` | `memory_entries` 表 | implemented_and_tested | test_memory_control.py: 指令响应验证 |
| 20 | 彻底删除诚实显示 | MEMORY-SPEC §9 | `core/memory.py` | `memory_entries.status=purge_pending` | implemented_and_tested | test_memory_control.py: 删除流程验证 |
| 21 | Ollama 关闭后可用 | PRODUCT-DEF §6 | `core/llm.py` | — | implemented_and_tested | test_ollama_degraded.py: 降级显示验证 |
| 22 | 禁止模拟回复冒充 | OLLAMA § | `core/llm.py` | — | implemented_and_tested | test_ollama_degraded.py: 无 mock 回复 |
| 23 | 对话协议 8 类意图 | PERSONALITY §10 | `core/intent_classifier.py` | — | implemented_and_tested | test_intent_protocol.py: 8 类分类 + "停电"测试 |
| 24 | advice 优先级正确 | PERSONALITY §10 | `core/intent_classifier.py` | — | implemented_and_tested | test_intent_protocol.py: "你觉得怎么办"→advice |
| 25 | 打断后停止生成 | PERSONALITY §10 | `core/llm.py` + `ui/chat_panel.py` | — | implemented_and_tested | test_intent_protocol.py: interruption 行为 |
| 26 | 记忆完整字段 | MEMORY-SPEC §2 | `core/database.py` | `memory_entries` 表 | implemented_and_tested | test_memory_schema.py: 字段完整性 |
| 27 | 权限分级 10 级 | PERMISSION §4 | `core/permission_gateway.py` | `audit_logs` 表 | implemented_and_tested | test_permission_gateway.py: 10 级权限 |
| 28 | 公开网页读取默认允许 | PERMISSION §2.1 | `core/permission_gateway.py` | — | implemented_and_tested | test_network_permissions.py: 公开搜索允许 |
| 29 | 私人数据外发需授权 | PERMISSION §2.4 | `core/permission_gateway.py` | `audit_logs` 表 | implemented_and_tested | test_network_permissions.py: 外发拒绝 |
| 30 | 下载≠执行 | PERMISSION §2.6 | `core/permission_gateway.py` | — | implemented_and_tested | test_permission_gateway.py: 下载允许执行拒绝 |
| 31 | 推测不自动升级 | MEMORY-SPEC §10 | `core/memory.py` | `confidence` + `scope` | implemented_and_tested | test_memory_schema.py: sandbox 不自动升级 |
| 32 | 用户主权 + 西西主体性 | PERSONALITY §4 | `core/constitution.py` + `core/identity.py` | — | implemented_and_tested | test_constitution.py: 自主权分级验证 |
| 33 | 禁止自我保存目标 | IDENTITY-SPEC §6 | `core/identity.py` | — | implemented_and_tested | test_identity.py: 负向约束检查 |
| 34 | 单用户、无摄像头、无持续监听 | PRODUCT-DEF §3 | `main.py` + `config.yaml` | — | implemented_and_tested | test_identity.py: 配置检查 |
| 35 | 人物/人格/模型/程序/资产/数据独立版本 | UPGRADE-SPEC §1 | `core/version_registry.py` | `version_registry` 表 | implemented_and_tested | test_migrations.py: 版本注册表 |
| 36 | 更换模型不丢失历史 | PRODUCT-DEF §2.1 | `core/llm.py` + `core/memory.py` | — | implemented_and_tested | test_memory_schema.py: 记忆与模型解耦 |
| 37 | 网络审计记录 | PERMISSION §2.9 | `core/permission_gateway.py` | `audit_logs` 表 | implemented_and_tested | test_network_permissions.py: 审计记录验证 |
| 38 | 完整桌面项目交付 | PRODUCT-DEF §6 | `host/`, `renderer/`, `ui/`, `main.py` | — | implemented_not_verified | 需 Windows 环境验证 |
| 39 | 视觉分层渲染 | PRODUCT-DEF §4 | `renderer/qt_renderer.py` | — | implemented_not_verified | 需 Windows 环境验证 |
| 40 | 超宽屏支持 | PRODUCT-DEF §4 | `host/dpi.py` + `renderer/qt_renderer.py` | — | implemented_not_verified | 需 Windows 环境验证 |

---

## M1 不实现（但架构不冲突）

| 功能 | 原因 | 预留方式 |
|------|------|----------|
| 完整长期记忆检索 | 需要向量数据库 | `memory_entries` 表已预留，后续接入向量索引 |
| 复杂关系记忆推理 | 需要多轮对话积累 | `scope=relationship` 字段已预留 |
| 夜间自主长任务 | 需要用户信任积累 | `Task` 数据结构已预留后台字段 |
| 广泛邮件和账号插件 | V1 边界 | 插件接口预留，核心不依赖 |
| 完整语音人格 | 后续版本 | voice 模块预留 |
| 复杂口型 | 后续版本 | renderer 接口预留 |
| 大量动作生成 | 后续版本 | asset_manager 预留 |
| 微信接入 | V1 边界 | 插件接口预留 |
| 最终四房间 | 后续版本 | asset_manager 预留 |
| 摄像头 | V1 明确禁止 | 无相关模块 |
| 持续麦克风监听 | V1 明确禁止 | 默认关闭 |
