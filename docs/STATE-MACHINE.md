# STATE-MACHINE.md
# 状态机规范
# Version: 1.1.0

---

## 1. 八个基础状态

数据库和状态机使用以下稳定 ID：

```python
class XiXiState(Enum):
    SLEEPING      = "sleeping"
    ALONE         = "alone"
    WORKING       = "working"
    THINKING      = "thinking"
    WAITING       = "waiting"
    ACCOMPANYING  = "accompanying"
    COMMUNICATING = "communicating"
    EXECUTING     = "executing"
```

UI 可以显示中文，但数据库和状态机使用上述 ID。

---

## 2. 状态分层

必须将以下概念分离，不能全部混入 mood：

```python
class StateSnapshot:
    state_id: str           # 当前状态ID
    emotion: str            # 当前情绪
    relationship_state: str # 关系状态
    attention: Attention    # 注意力对象
    boot_mode: str          # 启动模式
    entered_at: str         # 进入当前状态时间
    last_interaction_at: str # 最后交互时间
    previous_state: str     # 上一个状态
    reason: str             # 状态转换原因
    metadata: str           # JSON 附加信息

class Attention:
    target: str            # user / task / file / idle
    target_id: str         # 具体ID
    intensity: float       # 0.0-1.0
    since: str             # ISO时间
```

---

## 3. 启动模式

```python
class BootMode(Enum):
    RECONNECT  = "reconnect"   # 短时间重启或睡眠唤醒
    RESTORE    = "restore"     # 普通开机或较长时间离线
    COLD_START = "cold_start"  # 首次启动、数据缺失、数据损坏
```

### 行为差异

| 模式 | 行为 |
|------|------|
| reconnect | 恢复中断前状态和上下文，简短问候（"嗯？" / "回来了？"） |
| restore | 根据离线时间和之前状态进行合理恢复，生成时间差问候 |
| cold_start | 完整自我介绍，建立初始关系基线 |

不能只创建三个枚举。Database.set_state、get_state、StateMachine.to_dict 和 from_dict 的数据结构必须完全一致。

保存后重新读取，以下数据不得丢失：
- stateId, emotion, relationshipState, attention, bootMode, enteredAt, lastInteractionAt

---

## 4. 状态转换规则

```
用户交互
  → 如果是 sleeping: 转为 alone（被唤醒）
  → 如果是 alone/accompanying: 转为 communicating（开始交流）

空闲超时
  → 5分钟未说话 + communicating: 转为 accompanying
  → 30分钟未交互 + communicating/accompanying: 转为 alone
  → 长时间未交互: 可进入 sleeping

任务触发
  → 用户要求执行: 转为 executing
  → 任务完成: 回到 alone 或 accompanying

思考触发
  → 西西主动思考: 转为 thinking
  → 思考完成: 回到原状态
```
