from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ORDER = [
    "session.hello",
    "session.ready",
    "user.input",
    "soul.turn.request",
    "soul.turn.output",
    "permission.request",
    "permission.response",
    "tool.execute.request",
    "tool.execute.result",
    "assistant.stream.start",
    "assistant.stream.delta",
    "assistant.stream.complete",
]

for name in ORDER:
    message = json.loads((ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8"))
    print(json.dumps(message, ensure_ascii=False))
