"""
意图分类器 v3
=============
- 8类对话意图
- 规则优先，大模型补充
- 输出: intent, confidence, matchedRule, modelUsed, createdAt
- "停电"不是interruption
- "你觉得怎么办"→advice（不是question）
"""

import re
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class IntentType(Enum):
    EXPRESSION = "expression"
    UNDERSTANDING = "understanding"
    QUESTION = "question"
    ADVICE = "advice"
    DECISION = "decision"
    INSTRUCTION = "instruction"
    CORRECTION = "correction"
    INTERRUPTION = "interruption"


@dataclass
class IntentResult:
    intent: IntentType
    confidence: float
    matched_rule: str
    model_used: str
    created_at: str


class IntentClassifier:
    def classify(self, text: str) -> IntentResult:
        text_lower = text.lower().strip()
        created_at = datetime.now().isoformat()

        # === 1. 打断 — 最高优先级 ===
        # 必须是明确指令，排除"停电"等
        interruption_patterns = [
            r"^停[下]?$", r"^别说了$", r"^闭嘴$", r"^中断任务$",
            r"^先别说了$", r"^取消生成$", r"^停止$", r"^够了$",
            r"^不要继续$", r"^停下来$"
        ]
        for pattern in interruption_patterns:
            if re.search(pattern, text_lower):
                return IntentResult(
                    IntentType.INTERRUPTION, 1.0,
                    f"regex:{pattern}", "rule", created_at
                )

        # === 2. 纠正 ===
        correction_keywords = ["错了", "不对", "纠正", "改一下", "你记错了", "理解错了"]
        for kw in correction_keywords:
            if kw in text_lower:
                return IntentResult(
                    IntentType.CORRECTION, 0.95,
                    f"keyword:{kw}", "rule", created_at
                )

        # === 3. 决定/确认 ===
        decision_patterns = [
            r"^我决定", r"^确认", r"^就这么办", r"^定了", r"^好，?就这样",
            r"^就这么定了", r"^确定了"
        ]
        for pattern in decision_patterns:
            if re.search(pattern, text_lower):
                return IntentResult(
                    IntentType.DECISION, 0.95,
                    f"regex:{pattern}", "rule", created_at
                )

        # === 4. 指令/执行 ===
        instruction_keywords = ["帮我", "执行", "运行", "打开", "创建", "写", "生成", "记住", "查一下"]
        for kw in instruction_keywords:
            if kw in text_lower:
                return IntentResult(
                    IntentType.INSTRUCTION, 0.9,
                    f"keyword:{kw}", "rule", created_at
                )

        # === 5. 征求建议 — 必须在 question 之前检查 ===
        # "你觉得怎么办" → advice, 不是 question
        advice_patterns = [
            r"你觉得.*(怎么办|怎么选|好吗|行吗)",
            r"建议.*(吗|呢|？)",
            r"推荐.*(吗|呢|？)",
            r"怎么办[？?]",
            r"怎么.*(选择|决定|处理)",
            r"给.*建议"
        ]
        for pattern in advice_patterns:
            if re.search(pattern, text_lower):
                return IntentResult(
                    IntentType.ADVICE, 0.9,
                    f"regex:{pattern}", "rule", created_at
                )

        # === 6. 询问 ===
        question_patterns = [
            r"[？?]", r"^为什么", r"^怎么", r"^什么", r"^多少",
            r"^哪里", r"^谁", r"^什么时候", r"^如何"
        ]
        for pattern in question_patterns:
            if re.search(pattern, text_lower):
                return IntentResult(
                    IntentType.QUESTION, 0.85,
                    f"regex:{pattern}", "rule", created_at
                )

        # === 7. 表达情绪/分享（需要被理解）===
        understanding_keywords = [
            "好累", "开心", "难过", "烦", "郁闷", "兴奋", "担心",
            "压力", "焦虑", "开心", "高兴", "失落", "困惑"
        ]
        for kw in understanding_keywords:
            if kw in text_lower:
                return IntentResult(
                    IntentType.UNDERSTANDING, 0.8,
                    f"keyword:{kw}", "rule", created_at
                )

        # === 8. 默认：表达 ===
        return IntentResult(
            IntentType.EXPRESSION, 0.7,
            "default:expression", "rule", created_at
        )

    def is_memory_command(self, text: str) -> bool:
        text_lower = text.lower().strip()
        memory_keywords = [
            "记住", "记下来", "保留原话", "随口说说", "别记住",
            "不要记住", "记错了", "改成", "忘掉", "删除刚才",
            "彻底删除", "完全删除", "列出来", "列出记忆",
            "从哪里来的", "来源"
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
        }
        return descriptions.get(intent, "未知")
