# 状态所有权

| 数据 | 唯一写入方 | 其他方权限 |
|---|---|---|
| official identity pointer | Container | 只读 |
| Soul版本与规则 | Package manager | Container加载 |
| 用户原话 | Memory service | Soul只提出保存 |
| 长期记忆 | Memory service | Soul搜索/提出变更 |
| 项目状态 | Project service | UI展示，Soul提出更新 |
| 权限 | Permission gateway | UI收集决定 |
| 工具真实结果 | Tool adapter | Soul与UI只读 |
| 模型状态 | Model adapter | UI展示 |
| UI面板状态 | UI | Container可发模式建议 |
| Body资产映射 | Body runtime | Container只发语义意图 |

任何组件不得同时作为“提出者”和“最终裁决者”绕过Container。
