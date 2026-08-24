"""项目上下文：service（CRUD / 画像 / project_ctx 组装）+ scope（范围澄清持久化）。"""

from .scope import apply_product, apply_profile_field, apply_scope, parse_scope, parse_target_margin, top_products
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
    "apply_profile_field",
    "parse_scope",
    "parse_target_margin",
    "apply_product",
    "top_products",
]
