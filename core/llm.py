"""
LLM 引擎 v3
============
- 与模型解耦，接收人格上下文
- 支持流式输出和打断
- Ollama 不可用时显示"大脑不可用"，不生成模拟回复
- 集成意图分类和记忆控制
"""

import aiohttp
import asyncio
from typing import AsyncIterator, Optional, Dict
from datetime import datetime, timedelta
from core.constitution import PersonalityConstitution
from core.memory import MemorySystem
from core.state import StateMachine
from core.intent_classifier import IntentClassifier, IntentType


class LLMEngine:
    def __init__(self, host: str = "http://localhost:11434", 
                 model: str = "richardyoung/qwen3.6-27b-abliterated:latest",
                 constitution: PersonalityConstitution = None,
                 memory: MemorySystem = None,
                 state_machine: StateMachine = None,
                 intent_classifier: IntentClassifier = None,
                 timeout: int = 120):
        self.host = host
        self.model = model
        self.constitution = constitution or PersonalityConstitution()
        self.memory = memory
        self.state_machine = state_machine
        self.intent_classifier = intent_classifier
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._abort_flag = False
        self._last_used = datetime.now()
        self._available = True

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _build_system_prompt(self) -> str:
        state_ctx = ""
        if self.state_machine:
            state_ctx = f"\n【当前状态】{self.state_machine.label}，{self.state_machine.mood}"

        memory_ctx = ""
        if self.memory:
            try:
                recent = self.memory.get_recent_chat(limit=5)
                if recent:
                    memory_ctx = "\n【最近对话】\n" + "\n".join(
                        [f"{'你' if r['role'] == 'user' else '西西'}：{r['content']}" for r in recent]
                    )
            except Exception:
                pass

        return self.constitution.to_system_prompt(state_ctx, memory_ctx)

    async def _check_ollama(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self.host}/api/tags", timeout=aiohttp.ClientTimeout(total=3)):
                self._available = True
                return True
        except Exception:
            self._available = False
            return False

    async def chat_stream(self, user_message: str) -> AsyncIterator[str]:
        self._abort_flag = False
        self._last_used = datetime.now()

        # 1. 意图识别
        intent_result = None
        if self.intent_classifier:
            intent_result = self.intent_classifier.classify(user_message)
            print(f"[Intent] {intent_result.intent.value} (confidence={intent_result.confidence}, rule={intent_result.matched_rule})")

        # 2. 记忆控制指令
        if self.memory:
            memory_result = self.memory.handle_memory_command(user_message)
            if memory_result:
                for char in memory_result:
                    if self._abort_flag:
                        break
                    yield char
                return

        # 3. 打断处理
        if intent_result and intent_result.intent == IntentType.INTERRUPTION:
            self.abort()
            yield "（已停止）"
            return

        # 4. 检查 Ollama 可用性
        if not await self._check_ollama():
            yield "大脑当前不可用（本地模型未启动）。\n\n你可以继续记录笔记、管理待办和查看项目，但对话功能暂时离线。"
            return

        # 5. 构建请求
        messages = [{"role": "system", "content": self._build_system_prompt()}]

        if self.memory:
            try:
                recent = self.memory.get_recent_chat(limit=10)
                for r in recent:
                    messages.append({"role": r["role"], "content": r["content"]})
            except Exception:
                pass

        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": 0.75, "num_ctx": 8192}
        }

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as resp:
                async for line in resp.content:
                    if self._abort_flag:
                        break
                    if line:
                        try:
                            data = line.decode("utf-8").strip()
                            if not data:
                                continue
                            import json
                            chunk = json.loads(data)
                            if "message" in chunk and "content" in chunk["message"]:
                                yield chunk["message"]["content"]
                            if chunk.get("done", False):
                                break
                        except Exception:
                            continue
        except Exception as e:
            self._available = False
            yield f"\n（对话连接中断：{str(e)}）"

    def abort(self):
        self._abort_flag = True

    def is_available(self) -> bool:
        return self._available

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def maybe_unload(self, idle_minutes: int = 10):
        if (datetime.now() - self._last_used) > timedelta(minutes=idle_minutes):
            asyncio.create_task(self.close())
