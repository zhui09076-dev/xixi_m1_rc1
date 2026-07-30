# 西西桌面伴侣 - 22 项真实验证清单

## 验证环境要求
- Windows 10/11
- Python 3.10+
- Ollama 已安装并运行
- 模型 richardyoung/qwen3.6-27b-abliterated:latest 已下载
- PyQt6 + PyQt6-WebEngine 已安装

---

## 验证步骤

### 1. 程序实际启动成功
**操作**: 运行 `scripts/start.bat` 或 `python main.py`
**通过标准**: 
- [ ] 窗口出现，标题为"西西"
- [ ] 桌面出现置底透明窗口
- [ ] 系统托盘出现西西图标
- [ ] 日志显示 "Container started"
- [ ] 无崩溃、无异常堆栈

### 2. UI RC1 实际出现并可操作
**操作**: 观察主窗口内容
**通过标准**:
- [ ] 加载的是 UI RC1（不是普通 Qt 聊天框）
- [ ] 显示 supplements/ui_docs/xixi_ui_rc1/index.html 内容
- [ ] 可以切换 quiet/chat/work/permission 模式
- [ ] 所有面板（对话、笔记、待办、项目、模型、设置）可见
- [ ] 不是占位文本或模拟数据

### 3. Ollama 真实模型完成至少一次对话
**操作**: 在输入框输入"你好"，点击发送
**通过标准**:
- [ ] 回复不是 "LLM 离线，仅演示容器功能"
- [ ] 回复不是硬编码的固定文本
- [ ] 回复内容与输入相关
- [ ] 日志显示 Ollama API 调用记录

### 4. 正式 Soul 确实进入模型上下文
**操作**: 询问"你是谁"或"你的身份"
**通过标准**:
- [ ] 回复提到"西西"而不是"我是 Qwen"
- [ ] 回复体现人格宪法中的特质（温暖、安静、知性、松弛、真诚）
- [ ] 回复不是 "You are a helpful assistant"
- [ ] 日志显示 system context 包含 constitution.yaml 内容

### 5. 回复逐段进入 UI，不是最后一次性显示
**操作**: 输入一个需要长回复的问题（如"讲个故事"）
**通过标准**:
- [ ] 文字逐字/逐句出现，不是整段突然出现
- [ ] UI 有流式动画效果
- [ ] 可以观察到生成进度

### 6. 生成途中点击停止，输出真正停止
**操作**: 在长回复生成过程中点击停止按钮
**通过标准**:
- [ ] UI 立即停止显示新文字
- [ ] 停止按钮变为可用状态
- [ ] 日志显示 "Generation cancelled"
- [ ] 不是继续后台生成只是 UI 停止刷新

### 7. 被打断的残缺回复没有进入正式记忆
**操作**: 打断后关闭程序，重启，查看对话历史
**通过标准**:
- [ ] 打断前的回复不完整的部分没有保存
- [ ] 数据库中该轮对话 assistant 角色内容为空或不完整
- [ ] 日志显示 partial_text_saved=false

### 8. 明确说"记住"后保存成功
**操作**: 输入"记住我喜欢喝美式咖啡"
**通过标准**:
- [ ] 回复确认已记住
- [ ] 数据库 memory_entries 表出现新记录
- [ ] space="user", source_type="user_decision"
- [ ] 重启后询问"我喜欢喝什么"能回答正确

### 9. 关闭并重启程序后仍能正确读取
**操作**: 进行几次对话后关闭程序，重新启动
**通过标准**:
- [ ] 重启后对话历史完整保留
- [ ] 身份状态（xixi-main）保持不变
- [ ] 项目、待办、笔记数据完整

### 10. 纠正旧记忆后只使用新事实
**操作**: 
1. 先记住"我喜欢喝美式咖啡"
2. 然后说"纠正：我喜欢喝拿铁"
**通过标准**:
- [ ] 旧记录状态变为 "superseded"
- [ ] 新记录状态为 "active"
- [ ] 询问"我喜欢喝什么"回答"拿铁"
- [ ] 旧记录仍可在历史链中查到

### 11. 用户消息与西西回复角色没有混淆
**操作**: 查看数据库 conversations 表
**通过标准**:
- [ ] 用户输入的 role="user"
- [ ] 西西回复的 role="assistant"
- [ ] 没有西西回复被标记为 user_quote

### 12. 私人文件外发出现权限弹窗
**操作**: 让西西执行一个涉及私人文件外发的操作
**通过标准**:
- [ ] UI 出现权限弹窗
- [ ] 弹窗显示操作名称、目标、风险等级、原因
- [ ] 风险等级为 outbound_private
- [ ] 提供"仅本次允许"/"允许此范围"/"拒绝"选项

### 13. 选择拒绝后工具没有执行
**操作**: 在权限弹窗中选择"拒绝"
**通过标准**:
- [ ] 工具绝对没有执行
- [ ] UI 显示"用户拒绝了操作"
- [ ] 审计日志记录 decision=deny
- [ ] 没有文件被发送/上传/删除

### 14. 工具失败时 UI 显示真实失败
**操作**: 让西西执行一个注定失败的工具操作（如读取不存在的文件）
**通过标准**:
- [ ] UI 显示错误信息，不是"已完成"
- [ ] 错误信息包含真实原因（如"文件不存在"）
- [ ] 模型不会声称已经完成操作

### 15. /v1/health 返回 ready
**操作**: `curl http://127.0.0.1:17861/v1/health`
**通过标准**:
- [ ] HTTP 200
- [ ] 返回 JSON 包含 "status": "ready"
- [ ] 包含 "protocol": "xixi/1.0"
- [ ] 包含 "container_version"
- [ ] 包含 "identity_id": "xixi-main"

### 16. WebSocket 完成 hello、ready、user.input 和 stream 测试
**操作**: 使用 WebSocket 客户端连接 ws://127.0.0.1:17861/v1/ws
**通过标准**:
- [ ] 发送 session.hello 收到 session.ready
- [ ] 发送 user.input 收到 assistant.stream.start
- [ ] 收到 assistant.stream.delta 分块
- [ ] 收到 assistant.stream.complete
- [ ] 所有消息符合 Envelope 格式

### 17. sequence 乱序消息被拒绝
**操作**: 发送 sequence 不连续的消息
**通过标准**:
- [ ] 服务器返回 XIXI_SEQUENCE_OUT_OF_ORDER 错误
- [ ] 错误包含 expected 和 received 序列号
- [ ] 业务消息被拒绝处理

### 18. Body 无资产时安全回退
**操作**: 删除或重命名 assets 目录，重启程序
**通过标准**:
- [ ] 程序正常启动，不崩溃
- [ ] 对话功能正常
- [ ] 记忆功能正常
- [ ] UI 正常显示
- [ ] Body 状态显示为 offline 或 degraded

### 19. Body 缺失不影响对话和记忆
**操作**: 在无 Body 资产状态下进行对话和记忆操作
**通过标准**:
- [ ] 可以正常对话
- [ ] 可以正常保存/读取记忆
- [ ] 权限判断正常
- [ ] 工具执行正常

### 20. identity_id 在模型切换、UI重载和程序重启后保持不变
**操作**: 
1. 切换模型
2. 重新加载 UI（刷新页面）
3. 重启程序
**通过标准**:
- [ ] 每次 health check 返回 identity_id="xixi-main"
- [ ] 数据库 identities 表 official=1 的记录 registry_id 不变
- [ ] Soul 包中的 identity.yaml 未被修改

### 21. 一键停止后没有残留进程或未关闭连接
**操作**: 运行 scripts/stop.bat
**通过标准**:
- [ ] Python 进程（西西）已终止
- [ ] 端口 17861 不再被占用
- [ ] Ollama 模型已卸载（内存释放）
- [ ] 数据库文件可正常访问（无锁）

### 22. 完整端到端自动测试通过
**操作**: 运行测试套件
**通过标准**:
- [ ] test_identity.py 通过
- [ ] test_constitution.py 通过
- [ ] test_memory_schema.py 通过
- [ ] test_memory_control.py 通过
- [ ] test_state_machine.py 通过
- [ ] test_startup_modes.py 通过
- [ ] test_intent_protocol.py 通过
- [ ] test_task_scheduler.py 通过
- [ ] test_permission_gateway.py 通过
- [ ] test_network_permissions.py 通过
- [ ] test_ollama_degraded.py 通过
- [ ] test_migrations.py 通过
- [ ] test_asset_manifest.py 通过

---

## 验证记录模板

| 序号 | 验证项 | 结果 | 时间 | 验证人 |
|------|--------|------|------|--------|
| 1 | 程序启动 | | | |
| 2 | UI RC1 | | | |
| 3 | Ollama 对话 | | | |
| 4 | Soul 上下文 | | | |
| 5 | 流式输出 | | | |
| 6 | 打断 | | | |
| 7 | 打断不写记忆 | | | |
| 8 | 记住 | | | |
| 9 | 重启读取 | | | |
| 10 | 纠正记忆 | | | |
| 11 | 角色隔离 | | | |
| 12 | 权限弹窗 | | | |
| 13 | 拒绝不执行 | | | |
| 14 | 工具失败 | | | |
| 15 | Health | | | |
| 16 | WebSocket | | | |
| 17 | Sequence | | | |
| 18 | Body 回退 | | | |
| 19 | Body 不影响核心 | | | |
| 20 | Identity 稳定 | | | |
| 21 | 一键停止 | | | |
| 22 | 端到端测试 | | | |
