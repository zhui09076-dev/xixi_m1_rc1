"""
Body Interface - 语义意图输出 + 无资产安全回退

规则:
- Soul 和 Container 只能发送语义意图
- 禁止发送具体 PNG、视频或模型文件路径
- Body 无资产时允许：无人物模式 / 中性占位 / 默认站姿回退
- Body 离线或缺资产不能导致系统崩溃
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("xixi.body")


@dataclass
class BodyIntent:
    """Body 语义意图"""
    # 语义姿态
    posture: Optional[str] = None  # standing, sitting, working, resting, walking, waving

    # 语义动作
    action: Optional[str] = None  # idle, wave, nod, shake_head, point, type, write, read
    action_intensity: float = 0.5  # 0.0-1.0

    # 语义表情
    expression: Optional[str] = None  # neutral, smile, thoughtful, surprised, concerned, happy, calm

    # 镜头意图
    camera: Optional[str] = None  # close_up, medium, full_body, over_shoulder, profile

    # UI 意图
    ui_intent: Optional[str] = None  # show_chat, show_note, show_todo, show_project, show_settings, hide_all

    # 过渡时间（毫秒）
    transition_ms: int = 300

    # 可中断标记
    interruptible: bool = True

    # 优先级
    priority: str = "normal"  # low, normal, high, urgent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "posture": self.posture,
            "action": self.action,
            "action_intensity": self.action_intensity,
            "expression": self.expression,
            "camera": self.camera,
            "ui_intent": self.ui_intent,
            "transition_ms": self.transition_ms,
            "interruptible": self.interruptible,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BodyIntent":
        return cls(
            posture=data.get("posture"),
            action=data.get("action"),
            action_intensity=data.get("action_intensity", 0.5),
            expression=data.get("expression"),
            camera=data.get("camera"),
            ui_intent=data.get("ui_intent"),
            transition_ms=data.get("transition_ms", 300),
            interruptible=data.get("interruptible", True),
            priority=data.get("priority", "normal"),
        )


class BodyInterface:
    """
    Body 接口管理器

    状态:
    - online: Body 资产可用，正常发送语义意图
    - degraded: Body 资产部分缺失，使用中性占位
    - offline: Body 完全离线，使用无人物模式
    """

    def __init__(self, asset_manager=None):
        self.asset_manager = asset_manager
        self.status = "offline"  # online / degraded / offline
        self.current_intent: Optional[BodyIntent] = None
        self.fallback_mode = "neutral_placeholder"  # no_character / neutral_placeholder / default_standing
        self._check_assets()

    def _check_assets(self) -> None:
        """检查 Body 资产可用性"""
        # 简化检查：检查 assets 目录是否存在有效资产包
        try:
            if self.asset_manager:
                if hasattr(self.asset_manager, "get_active"):
                    pkg = self.asset_manager.get_active()
                    available = pkg is not None and bool(getattr(pkg, "layers", None) or getattr(pkg, "poses", None))
                    name = getattr(pkg, "package_id", "body-package") if pkg else "none"
                elif hasattr(self.asset_manager, "list_characters"):
                    available = bool(self.asset_manager.list_characters())
                    name = "asset-manifest"
                else:
                    available, name = False, "none"
                if available:
                    self.status = "online"
                    logger.info("Body assets available: %s", name)
                else:
                    self.status = "degraded"
                    logger.info("Body assets incomplete, using neutral placeholder")
            else:
                self.status = "offline"
        except Exception as e:
            logger.error("Body asset check failed: %s", e)
            self.status = "offline"

    def set_intent(self, intent: BodyIntent) -> Dict[str, Any]:
        """
        设置 Body 意图。

        返回: {"status": "sent"/"degraded"/"offline", "intent": ..., "fallback": ...}
        """
        self.current_intent = intent

        if self.status == "online":
            return {
                "status": "sent",
                "intent": intent.to_dict(),
                "fallback": None,
            }

        elif self.status == "degraded":
            # 使用中性占位
            fallback = self._create_fallback_intent(intent)
            return {
                "status": "degraded",
                "intent": intent.to_dict(),
                "fallback": fallback.to_dict(),
            }

        else:  # offline
            # 无人物模式：只保留 UI 意图
            ui_only = BodyIntent(
                ui_intent=intent.ui_intent,
                transition_ms=intent.transition_ms,
                interruptible=intent.interruptible,
            )
            return {
                "status": "offline",
                "intent": intent.to_dict(),
                "fallback": ui_only.to_dict(),
                "message": "Body assets unavailable. UI mode only.",
            }

    def _create_fallback_intent(self, original: BodyIntent) -> BodyIntent:
        """创建降级回退意图"""
        return BodyIntent(
            posture="standing" if original.posture else None,
            action="idle" if original.action else None,
            expression="neutral" if original.expression else None,
            camera=original.camera,
            ui_intent=original.ui_intent,
            transition_ms=original.transition_ms,
            interruptible=original.interruptible,
            priority=original.priority,
        )

    def get_status(self) -> Dict[str, Any]:
        """获取 Body 状态"""
        return {
            "status": self.status,
            "current_intent": self.current_intent.to_dict() if self.current_intent else None,
            "fallback_mode": self.fallback_mode,
        }

    def handle_no_assets(self) -> None:
        """处理无资产情况 - 安全回退"""
        self.status = "offline"
        self.fallback_mode = "no_character"
        logger.info("Body switched to no-character mode. Conversation and memory unaffected.")

    def map_state_to_intent(self, state: Dict) -> BodyIntent:
        """
        根据 Soul 状态生成 Body 意图。
        使用 state_to_body.yaml 的映射规则。
        """
        base = state.get("base", "waiting")
        emotion = state.get("emotion", "neutral")

        # 基础映射
        posture_map = {
            "sleeping": "resting",
            "alone": "standing",
            "working": "working",
            "thinking": "sitting",
            "waiting": "standing",
            "accompanying": "sitting",
            "communicating": "standing",
            "executing": "working",
        }

        expression_map = {
            "neutral": "neutral",
            "happy": "smile",
            "sad": "concerned",
            "surprised": "surprised",
            "angry": "concerned",
            "calm": "calm",
            "excited": "happy",
        }

        return BodyIntent(
            posture=posture_map.get(base, "standing"),
            expression=expression_map.get(emotion, "neutral"),
            action="idle",
            camera="medium",
            transition_ms=500,
            interruptible=True,
        )
