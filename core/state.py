"""状态机 v5"""
from typing import Dict, Optional
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime


class XiXiState(Enum):
    SLEEPING = "sleeping"
    ALONE = "alone"
    WORKING = "working"
    THINKING = "thinking"
    WAITING = "waiting"
    ACCOMPANYING = "accompanying"
    COMMUNICATING = "communicating"
    EXECUTING = "executing"


class BootMode(Enum):
    RECONNECT = "reconnect"
    RESTORE = "restore"
    COLD_START = "cold_start"


@dataclass
class Attention:
    target: str = "idle"
    target_id: str = ""
    intensity: float = 0.0
    since: str = ""


@dataclass
class StateSnapshot:
    state_id: str = "alone"
    emotion: str = "peaceful"
    relationship_state: str = "familiar"
    attention: dict = None
    boot_mode: str = "cold_start"
    entered_at: str = ""
    last_interaction_at: str = ""
    previous_state: str = ""
    reason: str = ""
    metadata: str = "{}"

    def __post_init__(self):
        if self.attention is None:
            self.attention = asdict(Attention())
        if not self.entered_at:
            self.entered_at = datetime.now().isoformat()
        if not self.last_interaction_at:
            self.last_interaction_at = datetime.now().isoformat()


class StateMachine:
    STATE_META = {
        XiXiState.SLEEPING: {"label": "睡眠", "pose": "resting", "mood": "peaceful"},
        XiXiState.ALONE: {"label": "独处", "pose": "standing", "mood": "peaceful"},
        XiXiState.WORKING: {"label": "工作", "pose": "working", "mood": "focused"},
        XiXiState.THINKING: {"label": "思考", "pose": "sitting", "mood": "thoughtful"},
        XiXiState.WAITING: {"label": "等待", "pose": "sitting", "mood": "patient"},
        XiXiState.ACCOMPANYING: {"label": "陪伴", "pose": "sitting", "mood": "warm"},
        XiXiState.COMMUNICATING: {"label": "交流", "pose": "sitting", "mood": "engaged"},
        XiXiState.EXECUTING: {"label": "执行", "pose": "working", "mood": "focused"},
    }

    def __init__(self, initial_state: XiXiState = XiXiState.ALONE,
                 boot_mode: BootMode = BootMode.COLD_START):
        self.state = initial_state
        self.snapshot = StateSnapshot(state_id=initial_state.value, boot_mode=boot_mode.value)
        self._update_meta()

    def _update_meta(self):
        meta = self.STATE_META.get(self.state, {})
        self.label = meta.get("label", "")
        self._pose = meta.get("pose", "standing")
        self._mood = meta.get("mood", "neutral")

    @property
    def pose(self) -> str:
        return self._pose

    @pose.setter
    def pose(self, value: str):
        self._pose = value

    @property
    def mood(self) -> str:
        return self._mood

    @mood.setter
    def mood(self, value: str):
        self._mood = value

    def transition(self, new_state: XiXiState, reason: str = "") -> Dict:
        if self.state == new_state:
            return {}
        old = self.state
        self.snapshot.previous_state = old.value
        self.state = new_state
        self.snapshot.state_id = new_state.value
        self.snapshot.entered_at = datetime.now().isoformat()
        self.snapshot.reason = reason
        self._update_meta()
        return {
            "from": old.value, "to": new_state.value,
            "reason": reason, "timestamp": datetime.now().isoformat(),
            "pose": self.pose, "mood": self.mood,
        }

    def on_interaction(self) -> Dict:
        self.snapshot.last_interaction_at = datetime.now().isoformat()
        if self.state == XiXiState.SLEEPING:
            return self.transition(XiXiState.ALONE, "被唤醒")
        elif self.state in [XiXiState.ALONE, XiXiState.ACCOMPANYING]:
            return self.transition(XiXiState.COMMUNICATING, "开始交流")
        return {}

    def on_idle(self, minutes: int) -> Dict:
        if minutes >= 5 and self.state == XiXiState.COMMUNICATING:
            return self.transition(XiXiState.ACCOMPANYING, "用户未说话")
        elif minutes >= 30 and self.state in [XiXiState.COMMUNICATING, XiXiState.ACCOMPANYING]:
            return self.transition(XiXiState.ALONE, "长时间未交互")
        elif minutes >= 60 and self.state == XiXiState.ALONE:
            return self.transition(XiXiState.SLEEPING, "进入睡眠")
        return {}

    def on_task_start(self) -> Dict:
        return self.transition(XiXiState.EXECUTING, "开始执行任务")

    def on_task_end(self) -> Dict:
        return self.transition(XiXiState.ALONE, "任务完成")

    def set_emotion(self, emotion: str):
        self.snapshot.emotion = emotion

    def set_relationship_state(self, state: str):
        self.snapshot.relationship_state = state

    def set_attention(self, target: str, target_id: str = "", intensity: float = 0.5):
        self.snapshot.attention = asdict(Attention(
            target=target, target_id=target_id,
            intensity=intensity, since=datetime.now().isoformat()
        ))

    def to_dict(self) -> Dict:
        return {
            "state": self.state.value,
            "snapshot": asdict(self.snapshot),
            "label": self.label,
            "pose": self.pose,
            "mood": self.mood,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "StateMachine":
        state_val = d.get("state", "alone")
        snapshot_data = d.get("snapshot", {})
        boot_mode = snapshot_data.get("boot_mode", "cold_start")
        sm = cls(initial_state=XiXiState(state_val), boot_mode=BootMode(boot_mode))
        if snapshot_data:
            for key, value in snapshot_data.items():
                if hasattr(sm.snapshot, key):
                    setattr(sm.snapshot, key, value)
        sm.label = d.get("label", sm.label)
        sm.pose = d.get("pose", sm.pose)
        sm.mood = d.get("mood", sm.mood)
        return sm


# RC3 name retained for compatibility
StateManager = StateMachine
