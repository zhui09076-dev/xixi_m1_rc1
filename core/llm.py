"""
LLM Engine - Ollama Integration
支持: 可配置上下文、真实流式、模型切换、状态查询、Soul system context 注入
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

try:
    import aiohttp
except ImportError:
    class _AiohttpUnavailable:
        ClientError = OSError

    aiohttp = _AiohttpUnavailable()

logger = logging.getLogger("xixi.llm")


@dataclass
class LLMConfig:
    """LLM 配置"""
    base_url: str = "http://localhost:11434"
    model: str = "richardyoung/qwen3.6-27b-abliterated:latest"
    context_length: int = 65536  # 可配置，默认 65536，不硬编码 8192
    temperature: float = 0.7
    top_p: float = 0.9
    timeout: float = 120.0
    stream: bool = True
    num_gpu: int = -1
    num_thread: int = 0
    top_k: int = 40
    repeat_penalty: float = 1.1
    keep_alive: str = "5m"

    @property
    def host(self) -> str:
        return self.base_url

    def __contains__(self, key: str) -> bool:
        return key == "host" or hasattr(self, key)

    def to_api_options(self) -> Dict[str, Any]:
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "num_ctx": self.context_length,
        }


@dataclass
class StreamDelta:
    """流式输出分块"""
    text: str = ""
    done: bool = False
    model: str = ""
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None


@dataclass
class ModelStatus:
    """模型状态"""
    name: str
    loaded: bool
    size: Optional[int] = None
    parameter_size: Optional[str] = None
    format: Optional[str] = None
    families: Optional[List[str]] = None


class LLMEngine:
    """
    Ollama LLM 引擎

    特性:
    - 异步流式生成
    - 可配置上下文长度
    - 模型加载/卸载/切换/状态查询
    - 连接池管理（自动关闭 session）
    - 降级处理（模型离线时显示真实状态）
    - Soul system context 注入
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        self._current_generate_task: Optional[asyncio.Task] = None
        self._cancelled = False
        self._available = None
        self._offline_reason = ""

    def is_available(self) -> bool:
        return bool(self._available)

    def get_offline_reason(self) -> str:
        return self._offline_reason

    def abort(self) -> None:
        self.cancel_generation()

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp session（线程安全）"""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=self.config.timeout)
                self._session = aiohttp.ClientSession(timeout=timeout)
                logger.debug("Created new aiohttp ClientSession")
            return self._session

    async def close(self) -> None:
        """关闭 session，释放连接"""
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
                logger.info("LLMEngine aiohttp session closed")

    # ── 模型管理 ──

    async def list_models(self) -> List[ModelStatus]:
        """列出本地可用模型"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.config.base_url}/api/tags") as resp:
                if resp.status != 200:
                    logger.error("Failed to list models: HTTP %d", resp.status)
                    return []
                data = await resp.json()
                models = []
                for m in data.get("models", []):
                    models.append(ModelStatus(
                        name=m.get("name", "unknown"),
                        loaded=True,  # /api/tags 返回的都是已下载的
                        size=m.get("size"),
                        parameter_size=m.get("details", {}).get("parameter_size"),
                        format=m.get("details", {}).get("format"),
                        families=m.get("details", {}).get("families", []),
                    ))
                return models
        except aiohttp.ClientError as e:
            logger.error("Cannot connect to Ollama: %s", e)
            return []
        except Exception as e:
            logger.exception("Error listing models: %s", e)
            return []

    async def load_model(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        加载模型到内存。
        Ollama 会在第一次 generate 时自动加载，此方法用于预加载。
        """
        model = model_name or self.config.model
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.config.base_url}/api/generate",
                json={"model": model, "prompt": "", "stream": False},
            ) as resp:
                if resp.status == 200:
                    logger.info("Model %s loaded successfully", model)
                    return True, f"Model {model} loaded"
                else:
                    text = await resp.text()
                    logger.error("Failed to load model %s: %s", model, text)
                    return False, f"HTTP {resp.status}: {text}"
        except aiohttp.ClientError as e:
            logger.error("Cannot connect to Ollama to load model: %s", e)
            return False, f"Connection error: {e}"
        except Exception as e:
            logger.exception("Error loading model: %s", e)
            return False, str(e)

    async def unload_model(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        """卸载模型（释放 GPU/内存）"""
        model = model_name or self.config.model
        try:
            session = await self._get_session()
            # Ollama 没有直接的 unload API，可以通过加载一个空模型或发送特殊请求
            # 这里使用 generate 带 keep_alive=0 来释放
            async with session.post(
                f"{self.config.base_url}/api/generate",
                json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
            ) as resp:
                if resp.status == 200:
                    logger.info("Model %s unload requested", model)
                    return True, f"Model {model} unload requested"
                else:
                    text = await resp.text()
                    return False, f"HTTP {resp.status}: {text}"
        except Exception as e:
            logger.exception("Error unloading model: %s", e)
            return False, str(e)

    def switch_model(self, model_name: str) -> None:
        """切换当前模型（不改变 identity_id）"""
        old_model = self.config.model
        self.config.model = model_name
        logger.info("Model switched from %s to %s", old_model, model_name)

    async def check_health(self) -> Tuple[bool, str]:
        """检查 Ollama 服务健康状态"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.config.base_url}/api/tags") as resp:
                if resp.status == 200:
                    return True, "Ollama is online"
                return False, f"Ollama returned HTTP {resp.status}"
        except aiohttp.ClientError as e:
            return False, f"Ollama offline: {e}"
        except Exception as e:
            return False, str(e)

    # ── 流式生成 ──

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        on_delta: Optional[Callable[[StreamDelta], None]] = None,
    ) -> AsyncIterator[StreamDelta]:
        """
        流式生成回复。

        参数:
            messages: 对话历史 [{"role": "user"/"assistant", "content": "..."}]
            system: Soul 构建的 system context
            on_delta: 每收到一个分块的回调（用于立即发送到 UI）

        生成:
            StreamDelta 对象，包含文本分块和元数据
        """
        if self._current_generate_task is not None:
            logger.warning("Another generation is in progress, cancelling it")
            self._cancelled = True
            self._current_generate_task.cancel()
            try:
                await self._current_generate_task
            except asyncio.CancelledError:
                pass
            self._current_generate_task = None

        self._cancelled = False

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "options": self.config.to_api_options(),
        }
        if system:
            payload["system"] = system

        logger.debug("Generating with model %s, context=%d", 
                     self.config.model, self.config.context_length)

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error("Ollama generate error: HTTP %d - %s", resp.status, error_text)
                    yield StreamDelta(
                        text=f"[模型错误: HTTP {resp.status}]",
                        done=True,
                    )
                    return

                async for line in resp.content:
                    if self._cancelled:
                        logger.info("Generation cancelled by user")
                        yield StreamDelta(text="", done=True, model=self.config.model)
                        return

                    if not line:
                        continue

                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # 解析 Ollama stream 格式
                    delta_text = chunk.get("message", {}).get("content", "")
                    done = chunk.get("done", False)

                    delta = StreamDelta(
                        text=delta_text,
                        done=done,
                        model=chunk.get("model", self.config.model),
                        total_duration=chunk.get("total_duration"),
                        load_duration=chunk.get("load_duration"),
                        prompt_eval_count=chunk.get("prompt_eval_count"),
                        eval_count=chunk.get("eval_count"),
                    )

                    # 回调：立即发送给 UI
                    if on_delta and delta_text:
                        try:
                            on_delta(delta)
                        except Exception as e:
                            logger.error("on_delta callback error: %s", e)

                    yield delta

                    if done:
                        break

        except asyncio.CancelledError:
            logger.info("Generation task cancelled")
            yield StreamDelta(text="", done=True, model=self.config.model)
        except aiohttp.ClientError as e:
            logger.error("Ollama connection error during generation: %s", e)
            yield StreamDelta(
                text=f"[模型连接失败: {e}]",
                done=True,
                model=self.config.model,
            )
        except Exception as e:
            logger.exception("Generation error: %s", e)
            yield StreamDelta(
                text=f"[生成错误: {e}]",
                done=True,
                model=self.config.model,
            )
        finally:
            self._current_generate_task = None

    def cancel_generation(self) -> None:
        """取消当前生成（由打断信号调用）"""
        self._cancelled = True
        if self._current_generate_task and not self._current_generate_task.done():
            self._current_generate_task.cancel()
            logger.info("Generation cancellation requested")

    # ── 非流式生成（用于内部任务） ──

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        非流式生成。返回 (success, text, metadata)。
        """
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": self.config.to_api_options(),
        }
        if system:
            payload["system"] = system

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return False, f"HTTP {resp.status}: {error_text}", None

                data = await resp.json()
                text = data.get("message", {}).get("content", "")
                return True, text, data
        except Exception as e:
            logger.exception("Non-streaming generate error: %s", e)
            return False, str(e), None

    # ── 工具/函数调用支持（预留） ──

    async def generate_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        system: Optional[str] = None,
    ) -> Tuple[bool, Any, Optional[Dict]]:
        """
        带工具调用的生成（Ollama 支持 tools 参数）。
        返回 (success, response_or_error, metadata)
        """
        payload = {
            "model": self.config.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": self.config.to_api_options(),
        }
        if system:
            payload["system"] = system

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return False, f"HTTP {resp.status}: {error_text}", None

                data = await resp.json()
                return True, data.get("message", {}), data
        except Exception as e:
            logger.exception("Generate with tools error: %s", e)
            return False, str(e), None
