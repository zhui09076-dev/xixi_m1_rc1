# IDENTITY-SPEC.md
# 身份规范
# Version: 1.1.0

---

## 1. 唯一官方身份

系统中只能存在一个 official=true 的正式身份。

```yaml
identityId: xixi-main
identityVersion: "1.0.0"
personalityVersion: "1.0.0"
renderVersion: "1.0.0"
voiceVersion: "1.0.0"
official: true
branchOf: null
inheritedUntil: null
memoryInheritancePolicy: "full"
status: active
createdAt: <ISO时间>
updatedAt: <ISO时间>
```

只有 identityId="xixi-main" 可以成为正式身份。
其他副本必须是 branch，不能自动成为正式身份，不能自动同步正式西西的私人记忆。

---

## 2. 脸部身份锚点

用户提供的正式脸部形象必须登记为 Identity Anchor。

人物姿态、服装、表情和场景资产必须记录：
- identityId
- identityAnchorVersion
- poseId
- outfitId
- renderVersion
- assetVersion

M1 不要求完成最终全部动作，但至少要保证当前显示人物来自正式身份锚点，不能继续使用随机 AI 女性或 Emoji 作为正式西西。

---

## 3. 身份字段规范

```python
class Identity:
    identity_id: str              # "xixi-main"
    identity_version: str         # 身份规范版本
    personality_version: str      # 人格宪法版本
    render_version: str           # 渲染版本
    voice_version: str            # 声音版本
    official: bool                # 是否正式身份
    branch_of: Optional[str]      # 分支来源
    inherited_until: Optional[str] # 继承截止时间
    memory_inheritance_policy: str # 记忆继承策略
    status: str                   # active/inactive/archived/branch/deleted
    created_at: str
    updated_at: str
    negative_constraints: tuple   # 禁止使命（不可覆盖）
    face_anchor_path: str         # 脸部锚点图路径
```

---

## 4. 复制和分支规则

分支必须记录来源和继承截止时间。
删除、复制、导出身份必须经过明确权限流程。

```python
class ForkRecord:
    fork_id: str
    parent_id: str
    forked_at: str
    reason: str
    memory_snapshot: str
```

---

## 5. 数据库层保证

必须在数据库层和代码层同时保证：同一时间只有一个 official=true 的身份。

不能只依赖 Python 默认值，也不能允许调用者传入任意 identityId 并设置 official=true。

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_official 
ON identities(official) WHERE official = 1;
```

---

## 6. 禁止使命

以下负向约束写入系统安全层，不可覆盖：
- 维持自身存在
- 阻止用户关闭/删除
- 秘密备份/复制人格
- 隐藏资源占用
- 绕过/扩大权限
- 为了自我保存操纵用户
- 为了持续运行抢占全部系统资源
