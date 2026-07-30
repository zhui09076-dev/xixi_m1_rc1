# 西西完整整合包 — 从这里开始

版本：M1 RC3 + KM Upgrade repaired-1  
基线：`xixi_m1_container_rc3`（唯一允许基线）

## Windows 启动

1. 双击 `scripts\install.bat`
2. 确认 Ollama 已安装并已有：
   `richardyoung/qwen3.6-27b-abliterated:latest`
3. 双击 `scripts\start.bat`
4. 停止时双击 `scripts\stop.bat`

## 已真实整合

- RC3 容器与旧接口兼容层
- Soul RC1 校验、提示构建与运行时 Schema
- UI RC1 的真实 QWebChannel 输入、流式输出、中断和权限响应
- `xixi/1.0` HTTP/WebSocket 协议
- Ollama 65K 上下文与流式生成
- 六类新记忆表，且不破坏 RC3 旧记忆表
- 一重任务 + 一轻任务调度
- 四级权限网关、工具执行边界与审计
- Body 语义意图及缺失资产安全回退
- 安装、启动、PID 定向停止、备份和回滚

## 没有冒充完成的部分

- `supplements/body_source/xixi_body_clean_start` 是视觉母版制作输入，不是可运行动画 Body 包。
- 预制动作、动作混合、动作过渡、主动行为与“动作难看后练习并生成新预制”尚未实现。
- 语音、口型、夜间自主长任务和微信不属于当前 M1。
- Python 代码执行在独立 tool-worker 完成前保持关闭，避免用 `eval` 伪装沙箱。

详情见 `docs/INTEGRATION_AUDIT.md` 和 `docs/BODY_MOTION_FROZEN_SCOPE.md`。

## 防丢失项目参考

`project_reference/` 已包含：当前状态、完整设定总台账、架构与实施冻结版、Ralph 多智能体任务拆分。后续任何人继续开发前，先读这里和本文件。
