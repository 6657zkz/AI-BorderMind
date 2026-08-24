"""专家注册表：自动发现 personas/ 目录下的 ExpertAgent 子类并注册。

添加新专家 = 在 personas/ 放一个 .py 文件，定义 ExpertAgent 子类（role/display_name/
description/operators/depends_on/system_prompt），系统构建工作流时自动识别。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

from ..operators import OperatorError
from .base import ExpertAgent

_PKG = "app.agents.personas"


def _discover_agents() -> dict[str, ExpertAgent]:
    agents: dict[str, ExpertAgent] = {}
    pkg = importlib.import_module(_PKG)
    for modinfo in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"{_PKG}.{modinfo.name}")
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj is not ExpertAgent and issubclass(obj, ExpertAgent) and obj.__module__ == mod.__name__:
                agents[obj.role] = obj()
    return agents


AGENTS: dict[str, ExpertAgent] = _discover_agents()

EXECUTIVE_ROLE = "executive_expert"
# 参与工作流的全部节点角色（除最终整合者），fan-out 目标
ALL_ROLES: list[str] = [r for r in AGENTS if r != EXECUTIVE_ROLE]

# 任务拆解目录：供拆解器（LLM 选角色）使用
CATALOG: list[dict[str, str]] = [
    {"role": a.role, "name": a.display_name, "desc": a.description}
    for a in AGENTS.values()
    if a.role != EXECUTIVE_ROLE
]


def get_agent(role: str) -> ExpertAgent:
    try:
        return AGENTS[role]
    except KeyError:
        raise OperatorError(f"未知专家: {role}") from None


def topo_order(roles: list[str]) -> list[str]:
    """按 depends_on 拓扑排序；依赖缺失的节点先执行。"""
    ordered: list[str] = []
    visited: set[str] = set()

    def visit(role: str) -> None:
        if role in visited:
            return
        visited.add(role)
        agent = AGENTS.get(role)
        if agent:
            for dep in agent.depends_on:
                if dep in AGENTS and dep not in visited:
                    visit(dep)
        ordered.append(role)

    for role in roles:
        visit(role)
    return ordered
