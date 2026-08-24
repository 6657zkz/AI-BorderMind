"""算子库：TEXT2SQL 单元（规则写 SQL、LLM 只填参数）。"""

from .base import Operator, OperatorError, OperatorResult
from .library import OPERATORS, get_operator, list_operators

__all__ = [
    "Operator",
    "OperatorError",
    "OperatorResult",
    "OPERATORS",
    "get_operator",
    "list_operators",
]
