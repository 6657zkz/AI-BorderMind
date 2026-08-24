"""项目 / 会话接口：创建、列表、历史消息。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..db import Message, Project, Session as SessionModel, get_db
from ..project import create_project, delete_project, get_project, rename_project
from ..session import create_session, delete_session, get_session, rename_session
from .schemas import ProjectCreate, SessionCreate


class RenameBody(BaseModel):
    name: str

router = APIRouter(prefix="/api", tags=["session"])

_MERCHANT = "m_001"


@router.post("/project")
def api_create_project(body: ProjectCreate, db: DbSession = Depends(get_db)):
    project_id = body.project_id or f"p_{uuid.uuid4().hex[:10]}"
    project = create_project(
        db,
        project_id=project_id,
        merchant_id=body.merchant_id,
        name=body.name,
        category_id=body.category_id,
        market_code=body.market_code,
    )
    return {"project_id": project.project_id, "name": project.name}


@router.get("/project/{project_id}")
def api_get_project(project_id: str, db: DbSession = Depends(get_db)):
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {
        "project_id": project.project_id,
        "merchant_id": project.merchant_id,
        "name": project.name,
        "category_id": project.category_id,
        "market_code": project.market_code,
        "profile_json": project.profile_json,
    }


@router.patch("/project/{project_id}")
def api_rename_project(project_id: str, body: RenameBody, db: DbSession = Depends(get_db)):
    project = rename_project(db, project_id, body.name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project_id": project.project_id, "name": project.name}


@router.delete("/project/{project_id}")
def api_delete_project(project_id: str, db: DbSession = Depends(get_db)):
    if not delete_project(db, project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"ok": True}


@router.get("/projects")
def api_list_projects(db: DbSession = Depends(get_db)):
    """列出商户全部项目（demo 用 m_001），附带会话数与是否已确定范围。"""
    projects = db.execute(
        select(Project).where(Project.merchant_id == _MERCHANT).order_by(Project.created_at.desc())
    ).scalars().all()
    result = []
    for p in projects:
        n_sessions = db.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.project_id == p.project_id)
        ).scalar()
        result.append({
            "project_id": p.project_id,
            "name": p.name,
            "category_id": p.category_id,
            "market_code": p.market_code,
            "scoped": bool(p.category_id and p.market_code),
            "session_count": n_sessions,
        })
    return {"projects": result}


@router.post("/session")
def api_create_session(body: SessionCreate, db: DbSession = Depends(get_db)):
    project = get_project(db, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    session = create_session(db, body.project_id, project.merchant_id, mode="research")
    return {"session_id": session.session_id, "project_id": session.project_id}


@router.get("/sessions")
def api_list_sessions(project_id: str, db: DbSession = Depends(get_db)):
    """列出某项目的会话（含消息数 / 会话名）。"""
    sessions = db.execute(
        select(SessionModel)
        .where(SessionModel.project_id == project_id)
        .order_by(SessionModel.created_at.desc())
    ).scalars().all()
    result = []
    for s in sessions:
        n = db.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.session_id == s.session_id)
        ).scalar()
        result.append({
            "session_id": s.session_id,
            "mode": s.mode,
            "name": s.name or "新会话",
            "message_count": n,
        })
    return {"sessions": result}


@router.get("/messages")
def api_list_messages(session_id: str, db: DbSession = Depends(get_db)):
    """加载会话历史（按时间升序）。"""
    rows = db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.id)
    ).scalars().all()
    return {"messages": [{"role": m.role, "content": m.content} for m in rows]}


@router.get("/session/{session_id}")
def api_get_session(session_id: str, db: DbSession = Depends(get_db)):
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "session_id": session.session_id,
        "project_id": session.project_id,
        "mode": session.mode,
        "name": session.name,
    }


@router.patch("/session/{session_id}")
def api_rename_session(session_id: str, body: RenameBody, db: DbSession = Depends(get_db)):
    session = rename_session(db, session_id, body.name)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session_id": session.session_id, "name": session.name}


@router.delete("/session/{session_id}")
def api_delete_session(session_id: str, db: DbSession = Depends(get_db)):
    if not delete_session(db, session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}
