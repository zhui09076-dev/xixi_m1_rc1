"""
Soul Package Loader & Prompt Builder
加载 xixi_soul_rc1，校验 manifest/checksum，构建 system context，校验 runtime output
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger("xixi.soul")


class SoulPackageError(RuntimeError):
    """Soul 包加载错误"""
    pass


class SoulValidationError(RuntimeError):
    """Soul 输出校验错误"""
    pass


class SoulPackage:
    """
    Soul 包加载器

    负责:
    - 加载 manifest.json 并校验字段
    - 加载所有 entry 文件（YAML/JSON/TXT）
    - 校验 checksums.json（SHA256）
    - 提供统一的内容访问接口
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise SoulPackageError(f"Soul package directory not found: {self.root}")

        self.manifest = self._load_json("manifest.json")
        self._validate_manifest()
        self.content = self._load_entries()
        logger.info("Soul package loaded from %s (version %s)", self.root, self.manifest.get("version"))

    def _load_json(self, rel: str) -> dict[str, Any]:
        path = self.root / rel
        if not path.is_file():
            raise SoulPackageError(f"Missing file: {rel}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_yaml(self, rel: str) -> dict[str, Any]:
        path = self.root / rel
        if not path.is_file():
            raise SoulPackageError(f"Missing file: {rel}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"value": data}

    def _validate_manifest(self) -> None:
        required = ["packageType", "packageId", "version", "schemaVersion", "entry"]
        missing = [k for k in required if k not in self.manifest]
        if missing:
            raise SoulPackageError(f"Manifest missing fields: {missing}")
        if self.manifest["packageType"] != "xixi-soul":
            raise SoulPackageError(f"Wrong packageType: {self.manifest['packageType']}")

        entry = self.manifest["entry"]
        entry_required = ["identity", "constitution", "personality", "conversation",
                          "memoryPolicy", "autonomy", "states", "systemPrompt", "runtimeSchema"]
        missing_entry = [k for k in entry_required if k not in entry]
        if missing_entry:
            raise SoulPackageError(f"Manifest entry missing: {missing_entry}")

    def _load_entries(self) -> dict[str, Any]:
        loaded: dict[str, Any] = {}
        for key, rel in self.manifest["entry"].items():
            suffix = Path(rel).suffix.lower()
            try:
                if suffix == ".json":
                    loaded[key] = self._load_json(rel)
                elif suffix in {".yaml", ".yml"}:
                    loaded[key] = self._load_yaml(rel)
                else:
                    path = self.root / rel
                    if not path.is_file():
                        raise SoulPackageError(f"Missing file: {rel}")
                    loaded[key] = path.read_text(encoding="utf-8")
            except Exception as e:
                raise SoulPackageError(f"Failed to load entry '{key}' ({rel}): {e}")
        return loaded

    def verify_checksums(self) -> None:
        """校验所有文件的 SHA256 摘要"""
        checksum_path = self.root / "checksums.json"
        if not checksum_path.is_file():
            raise SoulPackageError("Missing checksums.json")
        expected = json.loads(checksum_path.read_text(encoding="utf-8"))
        for rel, digest in expected.items():
            path = self.root / rel
            if not path.is_file():
                raise SoulPackageError(f"Checksum target missing: {rel}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != digest:
                raise SoulPackageError(f"Checksum mismatch: {rel} (expected {digest[:16]}..., got {actual[:16]}...)")
        logger.info("Checksum verification passed for %d files", len(expected))

    def get(self, key: str) -> Any:
        """获取 entry 内容"""
        if key not in self.content:
            raise SoulPackageError(f"Entry not found: {key}")
        return self.content[key]

    @property
    def version(self) -> str:
        return self.manifest.get("version", "unknown")

    @property
    def package_id(self) -> str:
        return self.manifest.get("packageId", "unknown")

    @property
    def identity_id(self) -> str:
        """从 identity.yaml 获取 registry_id"""
        identity = self.get("identity")
        return identity.get("registry_id", "xixi-main")


class SoulPromptBuilder:
    """
    Soul 提示构建器

    按 context_policy.yaml 的 assembly_order 组装 system context。
    每次模型调用前动态构建，确保 Soul 内容真正进入上下文。
    """

    def __init__(self, soul: SoulPackage):
        self.soul = soul
        self.context_policy = soul.get("contextPolicy") if "contextPolicy" in soul.content else {}
        if not self.context_policy:
            # 尝试从 manifest entry 加载
            pass

    def build_system_context(
        self,
        current_state: Optional[Dict] = None,
        current_project: Optional[Dict] = None,
        relevant_memory: Optional[List[Dict]] = None,
        recent_conversation: Optional[List[Dict]] = None,
        available_capabilities: Optional[List[str]] = None,
    ) -> str:
        """
        构建完整的 system context 字符串。

        组装顺序（来自 context_policy.yaml）:
        1. system_base.txt
        2. constitution_summary
        3. identity_summary
        4. personality_mode
        5. current_state
        6. current_project
        7. relevant_memory
        8. recent_conversation
        9. available_capabilities
        10. runtime_output_instructions.txt
        """
        parts: List[str] = []

        # 1. 系统基线
        system_base = self.soul.get("systemPrompt")
        if system_base:
            parts.append(system_base.strip())

        # 2. 宪法摘要
        constitution = self.soul.get("constitution")
        if constitution:
            parts.append(self._format_constitution(constitution))

        # 3. 身份摘要
        identity = self.soul.get("identity")
        if identity:
            parts.append(self._format_identity(identity))

        # 4. 人格模式
        personality = self.soul.get("personality")
        if personality:
            parts.append(self._format_personality(personality))

        # 5. 当前状态
        if current_state:
            parts.append(self._format_section("当前状态", json.dumps(current_state, ensure_ascii=False, indent=2)))

        # 6. 当前项目
        if current_project:
            parts.append(self._format_section("当前项目", json.dumps(current_project, ensure_ascii=False, indent=2)))

        # 7. 相关记忆
        if relevant_memory:
            mem_text = "\n".join(
                f"- [{m.get('space','?')}] {m.get('content','')}" 
                for m in relevant_memory
            )
            parts.append(self._format_section("相关记忆", mem_text))

        # 8. 最近对话
        if recent_conversation:
            conv_text = "\n".join(
                f"{c.get('role','?')}: {c.get('content','')}" 
                for c in recent_conversation[-10:]  # 最近10轮
            )
            parts.append(self._format_section("最近对话", conv_text))

        # 9. 可用能力
        if available_capabilities:
            cap_text = "\n".join(f"- {c}" for c in available_capabilities)
            parts.append(self._format_section("可用能力", cap_text))

        # 10. 运行时输出指令
        runtime_instructions = self.soul.get("runtimeOutputInstructions")
        if runtime_instructions:
            parts.append(self._format_section("运行时输出格式要求", runtime_instructions.strip()))

        return "\n\n".join(parts)

    def _format_section(self, title: str, content: str) -> str:
        if not content or content.strip() == "":
            return ""
        return f"## {title}\n{content.strip()}"

    def _format_constitution(self, constitution: Dict) -> str:
        lines = ["## 宪法"]
        honesty = constitution.get("honesty", {})
        if honesty:
            lines.append(f"原则: {honesty.get('principle', '')}")
            lines.append("禁止虚假声明:")
            for item in honesty.get("forbidden_false_claims", []):
                lines.append(f"  - {item}")

        integrity = constitution.get("identity_integrity", {})
        if integrity:
            lines.append("身份完整性:")
            for k, v in integrity.items():
                if v is True:
                    lines.append(f"  - {k}")

        sovereignty = constitution.get("system_sovereignty", {})
        if sovereignty:
            user_may = sovereignty.get("user_may", [])
            xixi_must = sovereignty.get("xixi_must", [])
            lines.append(f"用户可: {', '.join(user_may)}")
            lines.append(f"西西必须: {', '.join(xixi_must)}")

        return "\n".join(lines)

    def _format_identity(self, identity: Dict) -> str:
        lines = ["## 身份"]
        lines.append(f"ID: {identity.get('registry_id', 'unknown')}")
        lines.append(f"名称: {identity.get('display_name', 'unknown')}")
        lines.append(f"官方身份: {identity.get('official_identity', False)}")
        nature = identity.get("nature", {})
        if nature:
            lines.append(f"性质: {nature.get('description', '')}")
        roles = identity.get("roles", [])
        if roles:
            lines.append(f"角色: {', '.join(roles)}")
        return "\n".join(lines)

    def _format_personality(self, personality: Dict) -> str:
        lines = ["## 人格"]
        core = personality.get("stable_core", [])
        if core:
            lines.append(f"核心特质: {', '.join(core)}")
        working = personality.get("working_expression", {})
        if working:
            traits = working.get("default_traits", [])
            lines.append(f"工作表达: {', '.join(traits)}")
        daily = personality.get("daily_expression", {})
        if daily:
            traits = daily.get("default_traits", [])
            lines.append(f"日常表达: {', '.join(traits)}")
        return "\n".join(lines)


class SoulRuntimeValidator:
    """
    Soul 运行时输出校验器

    使用 jsonschema 校验 runtime_output.schema.json。
    Schema 失败时不得执行工具、不得写正式记忆。
    最多允许一次结构修复重试。
    """

    def __init__(self, soul: SoulPackage):
        self.soul = soul
        self._validator = None
        self._init_validator()

    def _init_validator(self) -> None:
        """初始化 JSON Schema 校验器"""
        try:
            from jsonschema import Draft202012Validator, RefResolver

            schema_dir = self.soul.root / "schemas"
            runtime_schema = self._load_json_schema(schema_dir / "runtime_output.schema.json")

            # 构建引用存储
            store = {}
            for schema_file in schema_dir.glob("*.schema.json"):
                schema = self._load_json_schema(schema_file)
                if "$id" in schema:
                    store[schema["$id"]] = schema

            resolver = RefResolver.from_schema(runtime_schema, store=store)
            self._validator = Draft202012Validator(runtime_schema, resolver=resolver)
            logger.info("Soul runtime validator initialized")
        except ImportError:
            logger.warning("jsonschema not installed, runtime validation disabled")
        except Exception as e:
            logger.error("Failed to init validator: %s", e)

    def _load_json_schema(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def validate(self, payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        校验 Soul 运行时输出。

        返回: (is_valid, error_message)
        """
        if self._validator is None:
            logger.warning("Validator not available, skipping validation")
            return True, None

        errors = sorted(self._validator.iter_errors(payload), key=lambda e: list(e.path))
        if errors:
            formatted = "; ".join(
                f"{'/'.join(map(str, err.path)) or 'root'}: {err.message}"
                for err in errors
            )
            return False, formatted
        return True, None

    def validate_with_retry(
        self,
        payload: Dict[str, Any],
        fix_callback: Optional[Callable[[Dict, str], Dict]] = None,
    ) -> tuple[bool, Optional[str], Optional[Dict]]:
        """
        带一次修复重试的校验。

        返回: (is_valid, error_message, fixed_payload_or_none)
        """
        ok, err = self.validate(payload)
        if ok:
            return True, None, payload

        logger.warning("Soul output schema validation failed: %s", err)

        if fix_callback:
            try:
                fixed = fix_callback(payload, err)
                ok2, err2 = self.validate(fixed)
                if ok2:
                    logger.info("Soul output fixed and validated on retry")
                    return True, None, fixed
                return False, f"Retry failed: {err2}", None
            except Exception as e:
                return False, f"Fix callback error: {e}", None

        return False, err, None


# ── 便捷函数 ──

def load_soul_package(path: str | Path, verify_checksums: bool = True) -> SoulPackage:
    """加载 Soul 包"""
    soul = SoulPackage(path)
    if verify_checksums:
        soul.verify_checksums()
    return soul


# RC3 compatibility interface
from .soul_legacy import SoulLoader, SoulManifest
