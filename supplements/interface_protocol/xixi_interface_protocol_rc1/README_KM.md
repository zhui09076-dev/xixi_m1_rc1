# 给 KM：西西接口协议 RC1

**不用等身体资产。现在就可以按这个协议实现容器接口。**

身体端只接收语义意图：

```json
{
  "posture": "waiting",
  "motion": "idle_breathing",
  "expression": "attentive_neutral",
  "camera": "medium",
  "ui": "permission",
  "intensity": 0.45
}
```

Body包以后只负责把这些意图映射成具体资产。缺少资产时必须安全回退，不能阻塞容器、Soul或UI。

## 先实现这五条主链路

1. `session.hello → session.ready`
2. `user.input → soul.turn.request → soul.turn.output`
3. `assistant.stream.start/delta/complete`
4. `permission.request → permission.response → tool.execute.result`
5. `user.interrupt → assistant.stream.interrupted`

## 地址

- WebSocket：`ws://127.0.0.1:17861/v1/ws`
- 健康检查：`http://127.0.0.1:17861/v1/health`
- 本地JSON文本帧，每帧一个完整对象。

## 兼容基线

- Soul：`xixi-soul-main 0.9.0-rc1`
- UI：`xixi-ui-main 0.9.0-rc1`
- 协议：`xixi/1.0`

## 关键纪律

- Soul只能提出工具与记忆动作，不能直接执行。
- 容器是权限、数据库、工具和真实状态的最终裁决者。
- UI只负责交互展示，不能伪造执行成功。
- 明确打断后，残缺回复不得写入正式记忆。
- 私人外发必须是`outbound_private`。
- 永久删除与覆盖唯一原件必须是`irreversible`。
- 模型切换、Body切换、UI重载都不能改变`identity_id`。
