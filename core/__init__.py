"""XiXi core package with lazy exports for optional runtime dependencies."""
from importlib import import_module

_EXPORTS = {
    "AssetManager": (".asset_manager", "AssetManager"),
    "Config": (".config", "Config"),
    "Constitution": (".constitution", "PersonalityConstitution"),
    "PersonalityConstitution": (".constitution", "PersonalityConstitution"),
    "Database": (".database", "Database"),
    "IdentityManager": (".identity", "IdentityManager"),
    "IntentClassifier": (".intent_classifier", "IntentClassifier"),
    "LLMEngine": (".llm", "LLMEngine"),
    "LLMConfig": (".llm", "LLMConfig"),
    "StreamDelta": (".llm", "StreamDelta"),
    "setup_logging": (".logger", "setup_logging"),
    "MemoryManager": (".memory", "MemoryManager"),
    "MemorySystem": (".memory", "MemorySystem"),
    "PermissionGateway": (".permission_gateway", "PermissionGateway"),
    "PermissionDecision": (".permission_gateway", "PermissionDecision"),
    "StateManager": (".state", "StateMachine"),
    "StateMachine": (".state", "StateMachine"),
    "XiXiState": (".state", "XiXiState"),
    "BootMode": (".state", "BootMode"),
    "SystemMonitor": (".system_monitor", "SystemMonitor"),
    "TaskScheduler": (".task_scheduler", "TaskScheduler"),
    "VersionRegistry": (".version_registry", "VersionRegistry"),
    "ProtocolServer": (".protocol_server", "ProtocolServer"),
    "MsgType": (".protocol_server", "MsgType"),
    "ErrorCode": (".protocol_server", "ErrorCode"),
    "XixiEnvelope": (".protocol_server", "XixiEnvelope"),
    "SoulPackage": (".soul_loader", "SoulPackage"),
    "SoulLoader": (".soul_loader", "SoulLoader"),
    "SoulPromptBuilder": (".soul_loader", "SoulPromptBuilder"),
    "SoulRuntimeValidator": (".soul_loader", "SoulRuntimeValidator"),
    "load_soul_package": (".soul_loader", "load_soul_package"),
    "ToolExecutor": (".tool_executor", "ToolExecutor"),
    "ToolResult": (".tool_executor", "ToolResult"),
    "BodyInterface": (".body_interface", "BodyInterface"),
    "BodyIntent": (".body_interface", "BodyIntent"),
    "WebBridge": (".web_bridge", "WebBridge"),
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute = _EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value
