# 西西接口协议 xixi/1.0

## 1. 目标

协议连接五个边界：

```text
UI ↔ Container ↔ Soul
              ↔ Tools
              ↔ Body
              ↔ Model
```

协议不把组件揉成一个进程。KM可以先在同一进程内实现，消息结构仍保持不变，后续拆进程无需重新定义业务语义。

## 2. 唯一事实来源

- 身份指针：Container
- 人格与行为规则：Soul包
- 真实记忆：Container数据库
- 权限状态：Container权限网关
- 工具结果：Tool adapter
- 模型运行状态：Model adapter
- UI显示状态：UI
- 身体资产解析：Body runtime

Soul输出是提议，不是真实执行结果。

## 3. 消息包络

每个消息必须包含：

- `protocol`
- `id`
- `type`
- `timestamp`
- `session_id`
- `trace_id`
- `source`
- `target`
- `sequence`
- `payload`

`reply_to`用于请求响应关联。`sequence`在单个会话内单调递增。

## 4. Turn生命周期

```text
user.input
  ↓
soul.turn.request
  ↓
soul.turn.output
  ├─ reply → assistant.stream.*
  ├─ memory_actions → memory.apply.*
  ├─ tool_requests → permission/tool flow
  ├─ body_intent → body.intent.set
  └─ state/ui → ui.mode.set
```

最终回复只能在容器掌握真实工具结果后完成。工具失败时不得使用Soul之前的乐观表述冒充成功。

## 5. 打断

收到`user.interrupt`后：

1. 立即取消模型生成；
2. 停止TTS和口型；
3. 停止尚未开始的工具调用；
4. 正在执行且不可取消的工具转入`partial`或明确等待；
5. 发出`assistant.stream.interrupted`；
6. `partial_text_saved`必须为`false`；
7. 需要恢复的任务返回`task_resume_token`。

## 6. 权限

- `ordinary`：公开网页、只读状态、无私人数据外发。
- `scoped`：已授权根目录内的可逆操作。
- `outbound_private`：私人数据离开本机。
- `irreversible`：永久删除、覆盖唯一原件、关键安全设置。

只有`outbound_private`和`irreversible`进入`permission.request`。
`ordinary`和已授权`scoped`不得反复弹窗。

## 7. 身体

Soul和Container只能发送语义意图，禁止发送具体PNG、视频、骨骼或模型路径。
Body runtime负责解析为资产ID，缺失时发送`body.status`并回退。

## 8. 兼容与升级

- 主版本不兼容时拒绝连接。
- 次版本新增字段必须保持可忽略。
- 消息类型新增时，旧客户端返回`XIXI_UNSUPPORTED_MESSAGE_TYPE`。
- 包升级不能重置身份、记忆、项目或权限。
