# MEMORY-SPEC.md
# 记忆规范
# Version: 1.1.0

---

## 1. 六类记忆

### 1.1 原始记录 (raw)
- 用户原话、语音转写原文、原始音频、上传附件
- 先原样保存，禁止覆盖
- 分类和总结只能作为附加信息
- 西西不能把整理后的内容冒充用户原话

### 1.2 工作记忆 (working)
- 当前话题、临时变量、当前步骤、正在看的文件、未完成推理
- 可以过期，可以压缩
- 不自动升级为长期事实

### 1.3 项目记忆 (project)
- 原始目标、成功标准、用户已确认决定、已确认事实
- 西西建议、未确认假设、被否定方向
- 文件版本、当前状态、阻塞、下一步、负责人、交付物

### 1.4 长期用户事实 (long_term)
- 长期偏好、身份信息、使用习惯、重要硬件、明确长期约束
- 不能因为用户随口说一次就永久写入

### 1.5 关系记忆 (relationship)
- 共同经历、长期互动习惯、已解决的分歧
- 用户明确表达的关系偏好、西西与用户之间形成的稳定模式
- 写入阈值必须高于普通对话记忆

### 1.6 西西私人思考沙盒 (private_sandbox)
- 临时观点、尚未确认的推测、对自身错误的反思
- 未成熟的建议、关系感受的临时解释
- 不能自动成为用户事实
- 不能直接触发现实行动
- 不能作为隐藏权限来源
- 不能绕过 Permission Gateway
- 可以被用户清除

---

## 2. 记忆字段规范

```python
class MemoryEntry:
    id: str
    content: str
    source_type: str       # user_quote / user_decision / tool_result /
                           # xixi_opinion / xixi_inference / creative_text / system_event
    source_ref: str        # 来源引用
    scope: str             # session / conversation / project / user / relationship / private_sandbox
    project_id: str        # 关联项目ID
    conversation_id: str   # 关联对话ID
    confidence: float      # 0.0-1.0
    retention: str         # temporary / session / project / long_term / user_pinned
    status: str            # active / superseded / pending / deleted / purge_pending
    created_at: str
    updated_at: str
    supersedes: str        # 被替代的旧记录ID
    deleted_at: str
    metadata: str          # JSON 附加信息
```

---

## 3. 原始记录不可覆盖

用户原话、语音转写原文和原始文件引用必须不可修改。
修正、摘要、标签和解释必须另建记录。
禁止通过 UPDATE 直接改写原始 content。

---

## 4. 纠正规则

用户说"你记错了"时：
- 不能覆盖旧记录
- 创建新记录
- 设置 supersedes=旧记录ID
- 将旧记录状态改为 superseded
- 保留修改来源、时间和用户指令

---

## 5. 保留原话

用户说"保留我的原话"后：
- 必须真实保存一条可持久化设置
- 后续相关记录必须保存原始文本
- 整理内容只能作为 annotation 或 derived record
- 不能用摘要替代原文

---

## 6. 不进入长期记忆

用户说"这只是随口说说" / "不要记进长期记忆"：
- 必须实际影响当前或指定内容的 retention
- 不能只回复一句"已设置"

---

## 7. 项目记忆

列出项目记忆时必须使用 projectId 过滤，不能返回所有最近记忆。

项目记忆必须区分：
- 原始目标、成功标准、用户决定、已确认事实
- 西西建议、未确认假设、被否定方向
- 当前状态、阻塞、下一步、文件版本、交付物

---

## 8. 忘掉刚才内容

不能默认删除数据库最近3条。
必须确定：当前对话、具体时间范围、具体消息范围、用户所指对象。
无法确定时，应先询问范围，不能猜测删除。

---

## 9. 彻底删除

不能默认删除最近5条。
彻底删除必须针对明确对象。

清理范围包括：
- 主记录、全文索引、向量索引、缓存
- 摘要中的引用、派生记录、项目引用
- 待清理备份标记

彻底删除流程必须诚实显示：
- 哪些已立即删除
- 哪些将在备份轮换时清理
- 预计清理周期
- 是否存在无法立即清理的历史备份

不能声称已经物理清除所有副本，除非实际完成。

---

## 10. 私人思考沙盒

西西允许保存临时推测、反思、未成熟观点和关系感受。

但私人沙盒内容：
- 不能自动成为用户事实
- 不能直接触发现实行动
- 不能成为隐藏权限来源
- 不能绕过 Permission Gateway
- 可以被用户清除
