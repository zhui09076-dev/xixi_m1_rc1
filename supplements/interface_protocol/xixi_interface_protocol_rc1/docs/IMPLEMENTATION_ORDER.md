# KM实现顺序

## P0：先跑通

1. Envelope解析与Schema校验
2. `session.hello/session.ready`
3. `user.input`
4. `soul.turn.request/soul.turn.output`
5. `assistant.stream.start/delta/complete`
6. `user.interrupt/assistant.stream.interrupted`
7. 错误返回

## P1：真实可用

1. Memory apply往返
2. Permission gateway
3. Tool execution result
4. UI mode
5. Model status
6. Task status

## P2：身体

1. Body intent adapter
2. Body status
3. 缺失资产回退
4. 中断动画和镜头

Body包晚于协议，不影响P0和P1。
