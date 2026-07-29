# ATTENTION-AND-TASKS.md
# 注意力与任务规范
# Version: 1.1.0

---

## 1. 注意力限制

西西同一时间原则上只允许：

```
1个重任务 + 1个轻任务
```

其余任务进入队列，不同时无限运行。

---

## 2. 任务分级

### 重任务 (heavy)
- 长文生成
- 大型文件整理
- 完整代码项目
- 深度研究
- AIGC 生成
- 大型数据处理

### 轻任务 (light)
- 等待下载
- 提醒
- 定时检查
- 简单检索
- 状态观察
- 短记录

---

## 3. 任务字段

```python
class Task:
    task_id: str
    task_type: str           # heavy / light
    weight: str              # 任务权重描述
    status: str              # queued / waiting_confirmation / running / paused / completed / failed / cancelled
    completion_definition: str  # 完成标准
    requires_confirmation: bool
    confirmation_state: str    # pending / confirmed / rejected
    resource_budget: str       # 资源预算描述
    checkpoint: str
    created_at: str
    started_at: str
    finished_at: str
    failure_reason: str
    result_ref: str            # 结果引用
    requested_by: str         # user / xixi
```

requiresConfirmation=true 的任务：确认前不得进入 running。

---

## 4. 长任务流程

必须执行：

```
确认目标
→ 定义完成标准
→ 计划
→ 执行
→ 检查点
→ 验证
→ 交付
```

禁止：
- 为了达到字数注水
- 未完成却报告完成
- 只生成目录和空文件后标记 completed
- 遇到失败后继续假装执行
- 无限制后台推理
- 没有明确任务时自己持续烧显卡

---

## 5. 后台任务规则

- 后台或夜间任务只在用户明确委托后运行
- 必须记录任务开始时间、预计完成时间、当前进度
- 用户可以随时查看、暂停、取消后台任务
- 后台任务失败必须报告，不能静默失败
- 未获得用户明确任务时，不得自行启动长期后台重任务
- 不得为了"保持活跃"持续调用模型
- 不得在夜间自行运行重型任务
