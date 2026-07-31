from __future__ import annotations

from typing import Any


def _section(title: str, value: Any) -> str:
    if value is None:
        return ""
    return f"\n\n## {title}\n{value}"


def build_prompt(
    system_base: str,
    constitution_summary: str,
    identity_summary: str,
    personality_mode: str,
    current_state: str,
    current_project: str,
    relevant_memory: str,
    recent_conversation: str,
    available_capabilities: str,
    user_message: str,
) -> str:
    parts = [system_base.strip()]
    parts.append(_section("宪法摘要", constitution_summary))
    parts.append(_section("身份摘要", identity_summary))
    parts.append(_section("当前人格模式", personality_mode))
    parts.append(_section("当前状态", current_state))
    parts.append(_section("当前项目", current_project))
    parts.append(_section("相关记忆", relevant_memory))
    parts.append(_section("最近对话", recent_conversation))
    parts.append(_section("可用能力", available_capabilities))
    parts.append(_section("用户消息", user_message))
    return "".join(parts).strip()
