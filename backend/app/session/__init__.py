"""会话/上下文管理：manager（CRUD / 消息 / 上下文解析）。"""

from .manager import (
    append_message,
    create_session,
    delete_session,
    get_session,
    load_history,
    new_session_id,
    rename_session,
    resolve_context,
    update_message,
)

__all__ = [
    "append_message",
    "create_session",
    "delete_session",
    "get_session",
    "load_history",
    "new_session_id",
    "rename_session",
    "resolve_context",
    "update_message",
]
