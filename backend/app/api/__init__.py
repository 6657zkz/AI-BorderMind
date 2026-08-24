"""API 路由聚合。"""

from fastapi import APIRouter

from .analysis_runs import router as analysis_runs_router
from .chat import router as chat_router
from .evidence import router as evidence_router
from .monitor import router as monitor_router
from .session import router as session_router

api_router = APIRouter()
api_router.include_router(session_router)
api_router.include_router(analysis_runs_router)
api_router.include_router(chat_router)
api_router.include_router(monitor_router)
api_router.include_router(evidence_router)

__all__ = ["api_router"]
