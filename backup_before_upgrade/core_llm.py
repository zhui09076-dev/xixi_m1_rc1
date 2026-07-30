"""LLM 引擎 v5 — 全部配置化，打断和离线状态可靠"""
import asyncio
import threading
try:
    import aiohttp
except ImportError:
    aiohttp = None
from typing import AsyncIterator, Optional, Dict, Any
from datetime import datetime, timedelta
from core.constitution import PersonalityConstitution
from core.memory import MemorySystem
from core.state import StateMachine
from core.intent_classifier import IntentClassifier, IntentType


class LLMEngine:
    """
    LLM 引擎：
    - 上下文/模型/资源参数全部配置化
    - 打断真实可靠（同步+异步双模式）
    - 离线状态检测真实可靠
    """

    DEFAULT_CONFIG = {
        "host": "http://localhost:11434",
        "model": "richardyoung/qwen3.6-27b-abliterated:latest",
        "timeout": 120,
        "context_length": 8192,
        "num_gpu": -1,
        "num_thread": 0,
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "keep_alive": "5m",
        "system_prompt_template": "default",
    }

    def __init__(self, config: Dict[str, Any] = None,
                 constitution: PersonalityConstitution = None,
                 memory: MemorySystem = None,
                 state_machine: StateMachine = None,
                 intent_classifier: IntentClassifier = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.constitution = constitution or PersonalityConstitution()
        self.memory = memory
        self.state_machine = state_machine
        self.intent_classifier = intent_classifier
        self._session: Optional[aiohttp.ClientSession] = None
        self._abort_flag = False
        self._last_used = datetime.now()
        self._available = None
        self._current_response = None
        self._offline_reason = ""
        self._lock = threading.Lock()

    def update_config(self, updates: Dict[str, Any]):
        """运行时更新配置"""
        self.config.update(updates)

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

    async def _get_session(self):
        if aiohttp is None:
            raise ImportError("aiohttp not installed")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _check_ollama(self) -> bool:
        """检查 Ollama 服务及指定模型是否存在"""
        if aiohttp is None:
            self._available = False
            self._offline_reason = "aiohttp not installed"
            return False
        try:
            session = await self._get_session()
            async with session.get(
                    f"{self.config['host']}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = data.get("models", [])
                    model_names = [m.get("name", m.get("model", "")) for m in models]
                    if self.config["model"] in model_names:
                        self._available = True
                        self._offline_reason = ""
                        return True
                    self._available = False
                    self._offline_reason = f"模型 '{self.config['model']}' 未找到"
                    return False
                self._available = False
                self._offline_reason = f"Ollama 返回状态码 {resp.status}"
                return False
        except asyncio.TimeoutError:
            self._available = False
            self._offline_reason = "Ollama 连接超时"
            return False
        except aiohttp.ClientConnectorError:
            self._available = False
            self._offline_reason = "Ollama 服务未启动"
            return False
        except Exception as e:
            self._available = False
            self._offline_reason = f"Ollama 检查异常: {str(e)}"
            return False

    def abort(self):
        """中断当前生成（同步安全）"""
        with self._lock:
            self._abort_flag = True
        # 尝试异步卸载，但不阻塞
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._unload_model())
        except RuntimeError:
            # 无事件循环，创建新线程执行
            def _async_unload():
                try:
                    asyncio.run(self._unload_model())
                except Exception:
                    pass
            t = threading.Thread(target=_async_unload, daemon=True)
            t.start()

    async def _unload_model(self):
        """卸载模型以强制中断"""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.config['host']}/api/generate",
                json={"model": self.config["model"], "keep_alive": 0},
                timeout=aiohttp.ClientTimeout(total=5)
            ):
                pass
        except Exception:
            pass

    def is_available(self) -> bool:
        """返回上次检测的可用状态"""
        return self._available or False

    def get_offline_reason(self) -> str:
        """返回离线原因"""
        return self._offline_reason

    async def chat_stream(self, user_message: str) -> AsyncIterator[str]:
        with self._lock:
            self._abort_flag = False
        self._last_used = datetime.now()

        # 意图分类（只处理明显操作）
        intent_result = None
        if self.intent_classifier:
            intent_result = self.intent_classifier.classify(user_message)

        # 记忆命令处理
        if self.memory:
            memory_result = self.memory.handle_memory_command(user_message)
            if memory_result:
                for char in memory_result:
                    with self._lock:
                        if self._abort_flag:
                            break
                    yield char
                return

        # 中断意图
        if intent_result and intent_result.intent == IntentType.INTERRUPTION:
            self.abort()
            yield "（已停止）"
            return

        # 检查 Ollama 可用性
        if not await self._check_ollama():
            yield f"大脑当前不可用（{self._offline_reason}）。\n\n你可以继续记录笔记、管理待办和查看项目，但对话功能暂时离线。"
            return

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
            "model": self.config["model"],
            "messages": messages,
            "stream": True,
            "options": {
                "num_ctx": self.config.get("context_length", 8192),
                "num_gpu": self.config.get("num_gpu", -1),
                "num_thread": self.config.get("num_thread", 0),
                "temperature": self.config.get("temperature", 0.7),
                "top_p": self.config.get("top_p", 0.9),
                "top_k": self.config.get("top_k", 40),
                "repeat_penalty": self.config.get("repeat_penalty", 1.1),
            },
            "keep_alive": self.config.get("keep_alive", "5m"),
        }

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.config['host']}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.get("timeout", 120))
            ) as resp:
                if resp.status != 200:
                    yield f"模型响应异常（状态码 {resp.status}）"
                    return
                async for line in resp.content:
                    with self._lock:
                        if self._abort_flag:
                            yield "\n\n（生成已中断）"
                            return
                    if line:
                        try:
                            chunk = line.decode("utf-8").strip()
                            if chunk.startswith("data: "):
                                chunk = chunk[6:]
                            data = json.loads(chunk)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                            if data.get("done"):
                                break
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue
        except asyncio.TimeoutError:
            yield "\n\n（模型响应超时）"
        except aiohttp.ClientConnectorError:
            self._available = False
            self._offline_reason = "Ollama 连接断开"
            yield f"\n\n（Ollama 连接断开：{self._offline_reason}）"
        except Exception as e:
            yield f"\n\n（生成异常：{str(e)}）"

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
