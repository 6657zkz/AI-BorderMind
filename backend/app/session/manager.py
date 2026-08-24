"""会话管理：会话 CRUD + 消息持久化 + 历史加载 + 上下文解析。

1 商户 + N 项目 + 会话历史：会话属于项目，消息按会话持久化。
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import Message, Session as SessionModel
from ..project.service import build_context


def new_session_id() -> str:
    return f"s_{uuid.uuid4().hex[:12]}"


def create_session(
    db: DbSession, project_id: str, merchant_id: str, mode: str = "research", name: str = "新会话"
) -> SessionModel:
    session = SessionModel(
        session_id=new_session_id(),
        project_id=project_id,
        merchant_id=merchant_id,
        mode=mode,
        name=name,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: DbSession, session_id: str) -> SessionModel | None:
    return db.get(SessionModel, session_id)


def rename_session(db: DbSession, session_id: str, name: str) -> SessionModel | None:
    session = get_session(db, session_id)
    if session is None:
        return None
    session.name = name.strip() or session.name
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: DbSession, session_id: str) -> bool:
    from ..db import Message

    session = get_session(db, session_id)
    if session is None:
        return False
    db.execute(Message.__table__.delete().where(Message.session_id == session_id))
    db.delete(session)
    db.commit()
    return True


def append_message(db: DbSession, session_id: str, role: str, content: str) -> Message:
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
        ts=int(time.time() * 1000),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def update_message(db: DbSession, message_id: int, content: str) -> Message | None:
    message = db.get(Message, message_id)
    if message is None:
        return None
    message.content = content
    message.ts = int(time.time() * 1000)
    db.commit()
    db.refresh(message)
    return message


def load_history(db: DbSession, session_id: str, limit: int = 20) -> list[dict[str, str]]:
    rows = (
        db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


def latest_pending_clarification(db: DbSession, session_id: str) -> tuple[dict[str, Any], str] | None:
    assistant = (
        db.execute(
            select(Message)
            .where(Message.session_id == session_id, Message.role == "assistant")
            .order_by(Message.id.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    if assistant is None:
        return None
    try:
        payload = json.loads(assistant.content)
    except json.JSONDecodeError:
        return None
    clarifications = payload.get("clarifications") or []
    if not payload.get("clarification") or not clarifications:
        return None
    previous_query = (
        db.execute(
            select(Message.content)
            .where(Message.session_id == session_id, Message.role == "user", Message.id < assistant.id)
            .order_by(Message.id.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    if previous_query is None:
        return None
    return clarifications[0], previous_query


def resolve_context(db: DbSession, session_id: str) -> dict[str, Any]:
    """会话 → 项目上下文（graph 的 project_ctx 源）。"""
    session = get_session(db, session_id)
    if session is None:
        raise ValueError(f"会话不存在: {session_id}")
    return build_context(db, session.project_id)
