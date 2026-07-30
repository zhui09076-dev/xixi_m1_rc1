# 西西桌面伴侣 - 完整工程包

## 快速开始

### 1. 安装（Windows）
```batch
scripts\install.bat
```

### 2. 启动
```batch
scripts\start.bat
```

### 3. 停止
```batch
scripts\stop.bat
```

## 项目结构

```
xixi/
├── main.py                 # 主入口
├── config.yaml             # 配置文件
├── requirements.txt        # 依赖
│
├── core/                   # 核心框架
│   ├── __init__.py
│   ├── protocol_server.py      # xixi/1.0 协议服务器
│   ├── soul_loader.py          # Soul 包加载/校验/提示构建
│   ├── llm.py                  # Ollama LLM 引擎（流式/可配置上下文）
│   ├── memory.py               # 六类记忆系统
│   ├── permission_gateway.py   # 四级风险权限网关
│   ├── tool_executor.py        # 真实工具执行
│   ├── body_interface.py       # Body 语义意图
│   ├── web_bridge.py           # QWebChannel 桥接
│   ├── task_scheduler.py       # 1重+1轻任务调度
│   ├── lifecycle.py            # 安装/启动/停止/备份/回滚
│   └── [其他保留文件]
│
├── ui/                     # UI 层
│   ├── web_main_window.py      # QWebEngineView 加载 UI RC1
│   └── [其他保留文件]
│
├── host/                   # 桌面宿主层
├── renderer/               # 渲染层
├── scripts/                # 脚本
│   ├── install.bat
│   ├── start.bat
│   └── stop.bat
│
├── docs/                   # 文档
│   ├── VERIFICATION_CHECKLIST.md   # 22项验证清单
│   ├── CHANGES_FROM_RC3.md         # 与RC3的修改对比
│   └── KNOWN_ISSUES.md             # 已知问题
│
└── supplements/            # 输入包（由用户提供）
    ├── soul/xixi_soul_rc1/
    ├── ui_docs/xixi_ui_rc1/
    ├── interface_protocol/xixi_interface_protocol_rc1/
    └── body_source/xixi_body_clean_start/

├── ui_runtime/             # 与 QWebChannel 接通的运行版 UI
└── project_reference/      # 完整设定、当前状态、冻结总方案和任务拆分
```

## 主链路闭环

```
用户输入
  → ProtocolServer (xixi/1.0)
  → Container
  → SoulLoader (加载 xixi_soul_rc1, 校验 manifest/checksum)
  → PromptBuilder (组装 system context)
  → LLMEngine (Ollama 流式生成, 可配置 65536 上下文)
  → StreamDelta (每分块立即发送到 UI)
  → SoulRuntimeValidator (JSON Schema 校验, 一次修复重试)
  → MemoryManager (六类记忆, 角色隔离, supersede)
  → PermissionGateway (四级风险, 弹窗, 拒绝阻断)
  → ToolExecutor (真实执行, 结果回传)
  → BodyInterface (语义意图, 无资产回退)
  → TaskScheduler (1重+1轻, 状态同步, 重启恢复)
  → LifecycleManager (备份/回滚/健康检查)
```

## 配置说明

```yaml
llm:
  base_url: "http://localhost:11434"
  model: "richardyoung/qwen3.6-27b-abliterated:latest"
  context_length: 65536      # 可配置，默认 65536

soul:
  path: "supplements/soul/xixi_soul_rc1"
  verify_checksums: true

protocol:
  host: "127.0.0.1"
  port: 17861
```

## 验证

参见 docs/VERIFICATION_CHECKLIST.md 完成 22 项真实验证。

## 已知问题

参见 docs/KNOWN_ISSUES.md。

## 版本

基于 xixi_m1_container_rc3（唯一正确基线）升级
容器版本: 0.1.0
协议版本: xixi/1.0
