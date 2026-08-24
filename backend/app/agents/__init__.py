"""Role 层专家：base + registry（自动发现 personas）+ 富人格提示词。"""

from .base import ExpertAgent, ExpertContext, ExpertResult
from .registry import (
    AGENTS,
    ALL_ROLES,
    EXECUTIVE_ROLE,
    get_agent,
)

__all__ = [
    "ExpertAgent",
    "ExpertContext",
    "ExpertResult",
    "AGENTS",
    "ALL_ROLES",
    "EXECUTIVE_ROLE",
    "get_agent",
]
