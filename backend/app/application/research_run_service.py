"""研判运行应用服务：统一 Run 生命周期编排。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..db import AnalysisRun
from ..evidence import (
    answer_clarification,
    append_run_event,
    complete_analysis_run,
    create_analysis_run,
    fail_analysis_run,
)
from ..graph import run_research


class ResearchRunConflict(ValueError):
    """Run 当前状态不支持所请求的生命周期操作。"""


class ResearchRunService:
    def create(
        self,
        db: Session,
        *,
        session_id: str,
        user_message_id: int,
        query: str,
        project_ctx: dict[str, Any],
        trigger_source: str = "chat",
    ) -> AnalysisRun:
        return create_analysis_run(
            db,
            session_id=session_id,
            user_message_id=user_message_id,
            query=query,
            project_ctx=project_ctx,
            trigger_source=trigger_source,
        )

    def resume(
        self,
        db: Session,
        *,
        run_id: str,
        field_id: str,
        answer: str,
        user_message_id: int,
        project_ctx: dict[str, Any],
    ) -> AnalysisRun:
        run = db.get(AnalysisRun, run_id)
        if run is None or run.status != "waiting_clarification":
            raise ResearchRunConflict("研判运行当前不可续跑")
        record = answer_clarification(
            db,
            run_id=run_id,
            field_id=field_id,
            answer=answer,
            message_id=user_message_id,
            commit=False,
        )
        if record is None:
            raise ResearchRunConflict("该澄清项不存在或已处理")
        run.user_message_id = user_message_id
        run.project_context_json = project_ctx
        run.status = "planning"
        run.completed_at = None
        append_run_event(db, run_id=run_id, event_type="run_resumed", payload={"field_id": field_id})
        db.commit()
        db.refresh(run)
        return run

    def execute(
        self,
        db: Session,
        *,
        run: AnalysisRun,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        try:
            result = run_research(
                run.query,
                run.project_context_json,
                run_id=run.run_id,
                history=history,
            )
            final = result.get("final") or {}
            self.complete(
                db,
                run_id=run.run_id,
                final=final,
                decision_graph=result.get("decision_graph"),
                execution_plan=result.get("execution_plan"),
            )
            return final
        except Exception as exc:
            self.fail(db, run_id=run.run_id, error={"message": str(exc), "code": "workflow_error"})
            raise

    def complete(
        self,
        db: Session,
        *,
        run_id: str,
        final: dict[str, Any],
        decision_graph: dict[str, Any] | None,
        execution_plan: dict[str, Any] | None,
    ) -> None:
        complete_analysis_run(
            db,
            run_id=run_id,
            final=final,
            decision_graph=decision_graph,
            execution_plan=execution_plan,
        )

    def fail(
        self,
        db: Session,
        *,
        run_id: str,
        error: dict[str, Any],
        status: str = "failed",
    ) -> None:
        fail_analysis_run(db, run_id=run_id, error=error, status=status)
