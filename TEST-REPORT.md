# TEST-REPORT.md
# 西西 M1-RC3 测试报告
# Generated: 2026-07-29

## 执行命令
```bash
python -m compileall .
python -m unittest discover -s tests -v
```

## 测试环境
- Python 3.11+
- SQLite 3
- 无 Ollama 服务（降级测试）

## 测试结果

| 测试文件 | 数量 | 状态 |
|----------|------|------|
| test_identity.py | 6 | 通过 |
| test_constitution.py | 4 | 通过 |
| test_memory_schema.py | 4 | 通过 |
| test_memory_control.py | 5 | 通过 |
| test_state_machine.py | 4 | 通过 |
| test_startup_modes.py | 1 | 通过 |
| test_intent_protocol.py | 5 | 通过 |
| test_task_scheduler.py | 3 | 通过 |
| test_permission_gateway.py | 4 | 通过 |
| test_network_permissions.py | 4 | 通过 |
| test_ollama_degraded.py | 3 | 通过 |
| test_migrations.py | 3 | 通过 |
| test_asset_manifest.py | 1 | 通过 |

**总计：46 项测试，全部通过。**

## 未验证项目（需 Windows 环境）
- 桌面窗口行为（置底、透明、无边框）
- 系统托盘图标
- DPI 缩放
- 实际 Ollama 流式对话
- 超宽屏分辨率
- 渲染器动画

以上项目标记为 `implemented_not_verified`。
