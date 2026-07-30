"""西西容器 M1 — 核心模块"""
from core.config import Config
from core.logger import setup_logger
from core.database import Database
from core.constitution import PersonalityConstitution
from core.memory import MemorySystem
from core.state import StateMachine, BootMode
from core.asset_manager import AssetManager
from core.system_monitor import SystemMonitor
from core.identity import IdentityManager
from core.permission_gateway import PermissionGateway
from core.task_scheduler import TaskScheduler
from core.intent_classifier import IntentClassifier
from core.version_registry import VersionRegistry
from core.soul_loader import SoulLoader
from core.body_loader import BodyLoader
from core.llm import LLMEngine

__all__ = [
    "Config", "setup_logger", "Database",
    "PersonalityConstitution", "MemorySystem", "StateMachine", "BootMode",
    "AssetManager", "SystemMonitor", "IdentityManager",
    "PermissionGateway", "TaskScheduler", "IntentClassifier",
    "VersionRegistry", "SoulLoader", "BodyLoader", "LLMEngine",
]
