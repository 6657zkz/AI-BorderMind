"""专家角色注册表。

persona 仅提供专家 Playbook；展示目录、能力依赖和数据授权均来自 planning.catalog。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

from ..operators import OPERATORS, OperatorError
from ..planning.catalog import CAPABILITIES, validate_catalog
from .base import ExpertAgent

_PKG = "app.agents.personas"


def _discover_agents() -> dict[str, ExpertAgent]:
    agents: dict[str, ExpertAgent] = {}
    pkg = importlib.import_module(_PKG)
    for modinfo in pkgutil.iter_modules(pkg.__path__):
        module = importlib.import_module(f"{_PKG}.{modinfo.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is not ExpertAgent and issubclass(obj, ExpertAgent) and obj.__module__ == module.__name__:
                agents[obj.role] = obj()
    return agents


AGENTS: dict[str, ExpertAgent] = _discover_agents()

_catalog_errors = validate_catalog(persona_roles=AGENTS, operator_ids=OPERATORS)
if _catalog_errors:
    raise RuntimeError("能力目录校验失败：" + "；".join(_catalog_errors))

EXECUTIVE_ROLE = CAPABILITIES["executive_expert"].expert_role_id
ALL_ROLES: list[str] = [
    capability.expert_role_id
    for capability in CAPABILITIES.values()
    if capability.expert_role_id != EXECUTIVE_ROLE
]

def get_agent(role: str) -> ExpertAgent:
    try:
        return AGENTS[role]
    except KeyError:
        raise OperatorError(f"未知专家: {role}") from None
