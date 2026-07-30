"""人格宪法 — 由 Soul 包提供具体内容"""
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class PersonalityConstitution:
    """人格宪法：容器持有结构，内容由 Soul 包填充"""
    name: str = "西西"
    version: str = "1.0.0"
    negative_constraints: List[str] = field(default_factory=list)
    positive_directives: List[str] = field(default_factory=list)
    relationship_principles: List[str] = field(default_factory=list)
    system_prompt_base: str = ""

    def to_system_prompt(self, state_ctx: str = "", memory_ctx: str = "") -> str:
        parts = [self.system_prompt_base or f"你是{self.name}，一个友好的桌面伴侣。"]
        if state_ctx:
            parts.append(state_ctx)
        if memory_ctx:
            parts.append(memory_ctx)
        if self.negative_constraints:
            parts.append("\n【约束】\n" + "\n".join(f"- {c}" for c in self.negative_constraints))
        return "\n".join(parts)

    @classmethod
    def from_soul_package(cls, soul_data: Dict) -> "PersonalityConstitution":
        """从 Soul 包数据加载"""
        constitution = soul_data.get("constitution", {})
        return cls(
            name=soul_data.get("identity", {}).get("name", "西西"),
            version=soul_data.get("version", "1.0.0"),
            negative_constraints=constitution.get("negative_constraints", []),
            positive_directives=constitution.get("positive_directives", []),
            relationship_principles=constitution.get("relationship_principles", []),
            system_prompt_base=constitution.get("system_prompt_base", ""),
        )
