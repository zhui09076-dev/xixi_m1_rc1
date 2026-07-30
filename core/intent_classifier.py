"""意图分类器 v5 — 只处理明显操作，无匹配返回 None"""
import re
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


class IntentType(Enum):
    EXPRESSION = "expression"
    UNDERSTANDING = "understanding"
    QUESTION = "question"
    ADVICE = "advice"
    DECISION = "decision"
    INSTRUCTION = "instruction"
    CORRECTION = "correction"
    INTERRUPTION = "interruption"
    MEMORY_COMMAND = "memory_command"
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    intent: IntentType
    confidence: float
    matched_rule: str
    model_used: str
    created_at: str


class IntentClassifier:
    """
    意图分类器：只处理明显操作（中断、纠正、记忆命令）。
    没有明显操作时返回 None。
    不强制每句话只有一个意图。
    """

    # 明显操作模式（按优先级排序）
    OBVIOUS_PATTERNS = [
        # 中断
        (IntentType.INTERRUPTION, [
            r"^停下?$", r"^别说了$", r"^闭嘴$", r"^中断任务$",
            r"^先别说了$", r"^取消生成$", r"^停止$", r"^够了$",
            r"^不要继续$", r"^停下来$", r"^stop$", r"^halt$", r"^cancel$",
        ], 1.0),
        # 纠正
        (IntentType.CORRECTION, [
            r"^错了$", r"^不对$", r"^你记错了$", r"^理解错了$",
            r"^纠正一下$", r"^改一下$", r"^应该是$", r"^不是.*而是",
            r"^纠正", r"^更正",
        ], 0.95),
        # 记忆命令
        (IntentType.MEMORY_COMMAND, [
            r"记住", r"记下来", r"保留原话", r"随口说说",
            r"别记住", r"不要记住", r"不要记进",
            r"记错了", r"改成", r"忘掉", r"删除刚才",
            r"彻底删除", r"完全删除", r"列出记忆",
            r"从哪里来的", r"来源",
        ], 0.9),
    ]

    def classify(self, text: str) -> Optional[IntentResult]:
        """
        只返回明显操作的意图。如果没有明显操作，返回 None。
        调用方应理解为"这句话没有需要容器处理的明显操作"。
        """
        text_lower = text.lower().strip()
        created_at = datetime.now().isoformat()

        for intent_type, patterns, confidence in self.OBVIOUS_PATTERNS:
            for pattern in patterns:
                if pattern.startswith("^") or pattern.endswith("$") or len(pattern) > 4:
                    try:
                        if re.search(pattern, text_lower):
                            return IntentResult(intent_type, confidence, f"regex:{pattern}", "rule", created_at)
                    except re.error:
                        continue
                else:
                    if pattern in text_lower:
                        return IntentResult(intent_type, confidence, f"keyword:{pattern}", "rule", created_at)

        # 没有明显操作，返回 None
        return None

    def is_memory_command(self, text: str) -> bool:
        text_lower = text.lower().strip()
        memory_keywords = [
            "记住", "记下来", "保留原话", "随口说说", "别记住",
            "不要记住", "不要记进", "记错了", "改成", "忘掉",
            "删除刚才", "彻底删除", "完全删除", "列出记忆", "从哪里来的", "来源"
        ]
        return any(kw in text_lower for kw in memory_keywords)

    def get_intent_description(self, intent: IntentType) -> str:
        descriptions = {
            IntentType.EXPRESSION: "表达或分享",
            IntentType.UNDERSTANDING: "希望被理解",
            IntentType.QUESTION: "询问事实或判断",
            IntentType.ADVICE: "征求建议",
            IntentType.DECISION: "确认决定",
            IntentType.INSTRUCTION: "要求记录或执行",
            IntentType.CORRECTION: "纠正西西",
            IntentType.INTERRUPTION: "要求停止",
            IntentType.MEMORY_COMMAND: "记忆相关命令",
            IntentType.UNKNOWN: "未分类",
        }
        return descriptions.get(intent, "未知")
