# UPGRADE-SPEC.md
# 升级规范
# Version: 1.1.0

---

## 1. 版本体系

```
Core Version            核心框架版本
Personality Version     人格宪法版本
Identity Version        身份标识版本
Render Version          渲染引擎版本
Asset Package Version   资产包版本
Plugin Version          插件版本
Database Schema Version 数据库架构版本
```

---

## 2. 升级规则

### 人物画质升级
- 不改变 Identity ID
- 不丢失记忆
- 不重置人格
- 不丢失项目
- 不改变动作语义 ID

### 模型升级
- 先运行人格回归测试
- 不因为模型口吻变化而换人
- 保留旧模型配置作为回退

### 数据库升级
- 先备份
- 在副本迁移
- 验证后切换
- 失败自动回滚

---

## 3. 回归测试

模型升级后必须验证：
- 人格宪法加载正确
- 状态机转换正常
- 记忆读写正常
- 对话意图识别正常
- 权限网关正常
- 视觉表现一致

---

## 4. 版本存储

```python
class VersionRegistry:
    core: str
    personality: str
    identity: str
    render: str
    asset_package: str
    plugin: str
    database_schema: int
    updated_at: str
```

写入 data/versions.json 和数据库 version_registry 表。
