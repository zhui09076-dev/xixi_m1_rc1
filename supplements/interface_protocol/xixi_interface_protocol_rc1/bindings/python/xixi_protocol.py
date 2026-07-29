from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
import uuid

PROTOCOL = "xixi/1.0"
Actor = Literal["ui", "container", "soul", "body", "tool", "model", "system"]

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"

@dataclass(slots=True)
class Envelope:
    type: str
    source: Actor
    target: Actor
    payload: dict[str, Any]
    session_id: str
    trace_id: str
    sequence: int
    id: str = field(default_factory=lambda: new_id("msg"))
    protocol: str = PROTOCOL
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reply_to: str | None = None
    ack_required: bool = False
    replay_safe: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "id": self.id,
            "type": self.type,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "reply_to": self.reply_to,
            "source": self.source,
            "target": self.target,
            "sequence": self.sequence,
            "ack_required": self.ack_required,
            "replay_safe": self.replay_safe,
            "payload": self.payload,
        }
