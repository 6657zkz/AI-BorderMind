"""项目上下文服务：项目 CRUD + 经营画像持久化 + 构建 graph 用的 project_ctx。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import Project


def get_project(db: DbSession, project_id: str) -> Project | None:
    return db.get(Project, project_id)


def create_project(
    db: DbSession,
    project_id: str,
    merchant_id: str,
    name: str,
    category_id: str | None = None,
    market_code: str | None = None,
) -> Project:
    project = Project(
        project_id=project_id,
        merchant_id=merchant_id,
        name=name,
        category_id=category_id,
        market_code=market_code,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_profile(db: DbSession, project_id: str, profile_json: dict) -> Project | None:
    """经营画像（反问采集后）持久化到 project.profile_json。"""
    project = get_project(db, project_id)
    if project is None:
        return None
    project.profile_json = profile_json
    db.commit()
    db.refresh(project)
    return project


def rename_project(db: DbSession, project_id: str, name: str) -> Project | None:
    project = get_project(db, project_id)
    if project is None:
        return None
    project.name = name.strip() or project.name
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: DbSession, project_id: str) -> bool:
    from ..db import Message, Session as SessionModel

    project = get_project(db, project_id)
    if project is None:
        return False
    session_ids = db.execute(
        select(SessionModel.session_id).where(SessionModel.project_id == project_id)
    ).scalars().all()
    for sid in session_ids:
        db.execute(Message.__table__.delete().where(Message.session_id == sid))
    db.execute(SessionModel.__table__.delete().where(SessionModel.project_id == project_id))
    db.delete(project)
    db.commit()
    return True


def build_context(db: DbSession, project_id: str) -> dict[str, Any]:
    """组装 graph 需要的 project_ctx：实体（品类/市场）+ 画像摘要。"""
    project = get_project(db, project_id)
    if project is None:
        raise ValueError(f"项目不存在: {project_id}")
    return {
        "project_id": project.project_id,
        "merchant_id": project.merchant_id,
        "name": project.name,
        "category_id": project.category_id,
        "market_code": project.market_code,
        "profile": project.profile_json or {},
    }
