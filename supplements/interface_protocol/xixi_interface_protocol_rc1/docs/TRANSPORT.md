# 传输层

## WebSocket

```text
ws://127.0.0.1:17861/v1/ws
```

- 仅监听回环地址。
- UTF-8文本帧。
- 每帧一个完整JSON对象。
- 单帧默认最大1 MiB。
- 二进制文件不进入WebSocket；消息中只传本地引用和哈希。
- 心跳20秒。
- 连接后第一条消息必须是`session.hello`。
- 服务端第一条业务响应必须是`session.ready`。

## 健康检查

```text
GET http://127.0.0.1:17861/v1/health
```

返回：

```json
{
  "status": "ready",
  "protocol": "xixi/1.0",
  "container_version": "0.1.0",
  "identity_id": "xixi-main"
}
```

## 重连

UI可携带`resume_session_id`。Container可以恢复未完成任务，但不得自动恢复：

- 私人外发授权；
- 永久删除确认；
- 已被用户打断的模型生成。

## 顺序

同一`session_id`内`sequence`必须递增。
不同`trace_id`可并发，但认知重任务仍受“一个重任务”规则约束。
