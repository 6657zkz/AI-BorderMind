"""项目上下文：service（CRUD / 画像 / project_ctx 组装）+ scope（范围澄清持久化）。"""

from .decision_parameters import (
    DECISION_PARAMETERS,
    apply_decision_parameter,
    extract_decision_parameters,
    parse_decision_parameter,
)
from .scope import apply_product, apply_scope, parse_scope, top_products
from .service import (
    build_context,
    create_project,
    delete_project,
    get_project,
    rename_project,
    update_profile,
)

__all__ = [
    "build_context",
    "create_project",
    "get_project",
    "update_profile",
    "rename_project",
    "delete_project",
    "apply_scope",
    "parse_scope",
    "apply_decision_parameter",
    "extract_decision_parameters",
    "parse_decision_parameter",
    "DECISION_PARAMETERS",
    "apply_product",
    "top_products",
]
