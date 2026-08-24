"""API 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    merchant_id: str = "m_001"
    name: str
    category_id: str | None = None
    market_code: str | None = None
    project_id: str | None = None


class SessionCreate(BaseModel):
    project_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class MonitorRunRequest(BaseModel):
    project_id: str
