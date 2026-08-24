"""chat 接口：研判请求（JSON 全量返回 + SSE 事件流）。

SSE 用 LangGraph workflow.stream() 按节点完成度推事件，前端可看到
「专家逐个完成 → 高管整合 → 汇总」的实时过程。
画像澄清：项目缺品类/市场时，先尝试从本条消息解析范围并持久化；
解析不了则交工作流反问；仅设置范围（无意图）时回一句确认并引导提问。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import AnalysisRun, SessionLocal, get_db
from ..evidence import (
    complete_analysis_run,
    create_analysis_run,
    fail_analysis_run,
    get_run_snapshot,
)
from ..graph import workflow
from ..project import apply_product, apply_profile_field, apply_scope, parse_scope, parse_target_margin, top_products
from ..session import append_message, get_session, latest_pending_clarification, resolve_context, update_message
from .schemas import ChatRequest

logger = logging.getLogger("chuhai.api")
router = APIRouter(prefix="/api", tags=["chat"])

_ROLE_LABEL = {
    "selection_expert": "选品专家",
    "pricing_expert": "定价专家",
    "positioning_expert": "打法专家",
    "executive_expert": "高管洞察",
}


def _initial_state(message: str, project_ctx: dict[str, Any], run_id: str | None = None) -> dict[str, Any]:
    return {
        "query": message,
        "run_id": run_id,
        "project_ctx": project_ctx,
        "decision_graph": None,
        "execution_plan": None,
        "clarifications": [],
        "roles": [],
        "results": {},
        "upstream": {},
        "clarification": None,
        "final": None,
    }


# ack 判定用：消息是否像一次分析请求（而非纯画像补充）
_RESEARCH_KEYWORDS = [
    "选品", "定价", "价格", "价位", "打法", "竞争", "机会", "值得做", "要不要", "能不能",
    "需求", "趋势", "成本", "毛利", "竞品", "分析", "评估", "建议", "定位", "格局",
    "卖点", "对标", "搜索", "差评", "评论", "进入", "切入",
]
# 需要竞品产品维度（触发自动锁定竞品）的关键词
_PRODUCT_LEVEL_KEYWORDS = ["打法", "竞争", "竞品", "对标", "卖点", "定位", "优劣", "对手", "格局", "差异"]


def _has_intent(message: str) -> bool:
    return any(kw in message for kw in _RESEARCH_KEYWORDS)


def _product_level_intent(message: str) -> bool:
    return any(kw in message for kw in _PRODUCT_LEVEL_KEYWORDS)


def _resolve_clarification_answer(
    db: DbSession,
    session_id: str,
    message: str,
) -> tuple[dict[str, Any], str, str | None] | None:
    pending = latest_pending_clarification(db, session_id)
    if pending is None:
        return None
    need, original_query = pending
    if need.get("field_id") != "target_margin":
        return None
    target_margin = parse_target_margin(message)
    if target_margin is None:
        return None
    project_ctx = resolve_context(db, session_id)
    apply_profile_field(db, project_ctx["project_id"], "target_margin", target_margin)
    run_id = db.execute(
        select(AnalysisRun.run_id)
        .where(AnalysisRun.session_id == session_id, AnalysisRun.status == "waiting_clarification")
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return resolve_context(db, session_id), original_query, run_id


def _resolve_scope(db: DbSession, session_id: str, message: str) -> tuple[dict[str, Any], str | None]:
    """解析用户补充的画像信息（品类/市场 + 竞品）。返回 (project_ctx, ack)：
    ack 非空表示本条只补充了画像、需回确认不跑工作流；带了意图则直接跑。
    缺范围时解析范围；已有范围但本条无意图时也尝试解析（支持改范围）。
    打法分析缺竞品时自动锁定类目头部竞品（减少反问）。"""
    project_ctx = resolve_context(db, session_id)
    acks: list[str] = []
    has_scope = bool(project_ctx.get("category_id") and project_ctx.get("market_code"))
    has_intent = _has_intent(message)

    if (not has_scope) or (has_scope and not has_intent):
        scope = parse_scope(db, message)
        if scope is not None:
            apply_scope(db, project_ctx["project_id"], scope)
            project_ctx = resolve_context(db, session_id)
            acks.append(f"已确认研判范围：{scope['category_name']} · {scope.get('market_name') or scope['market_code']}")

    # 竞品级意图 + 无竞品 → 自动锁定类目头部竞品直接分析（不再反问「针对哪个」）
    product_ids = (project_ctx.get("profile") or {}).get("product_ids") or []
    if _product_level_intent(message) and project_ctx.get("category_id") and not product_ids:
        tops = top_products(db, project_ctx["category_id"], 3)
        for pid, _ in tops:
            apply_product(db, project_ctx["project_id"], pid)
        project_ctx = resolve_context(db, session_id)
        if tops:
            acks.append(f"已按类目头部竞品 {'、'.join(name for _, name in tops)} 分析打法")

    if not acks:
        return project_ctx, None  # 没解析到新画像 → 交给工作流（可能反问）
    if has_intent:
        return project_ctx, None  # 本条同时带了意图 → 直接跑工作流
    return project_ctx, "、".join(acks) + "。你想分析什么？选品 / 定价 / 打法 / 竞争格局？"


@router.post("/chat")
def api_chat(body: ChatRequest, db: DbSession = Depends(get_db)):
    session = get_session(db, body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    clarification_answer = _resolve_clarification_answer(db, body.session_id, body.message)
    resumed_run_id = None
    if clarification_answer is None:
        project_ctx, ack = _resolve_scope(db, body.session_id, body.message)
        query = body.message
    else:
        project_ctx, query, resumed_run_id = clarification_answer
        ack = None
    user_message = append_message(db, body.session_id, "user", body.message)
    if ack:
        final = {"mode": "chat", "answer": ack}
        append_message(db, body.session_id, "assistant", json.dumps(final, ensure_ascii=False))
        return {"session_id": body.session_id, "final": final}

    if resumed_run_id:
        run = db.get(AnalysisRun, resumed_run_id)
        if run is None:
            raise HTTPException(status_code=409, detail="等待澄清的研判运行不存在")
        run.user_message_id = user_message.id
        run.project_context_json = project_ctx
        run.status = "planning"
        run.completed_at = None
        db.commit()
    else:
        run = create_analysis_run(
            db,
            session_id=body.session_id,
            user_message_id=user_message.id,
            query=query,
            project_ctx=project_ctx,
        )
    from ..graph import run_research

    try:
        result = run_research(query, project_ctx, run_id=run.run_id)
        final = result.get("final") or {}
        complete_analysis_run(
            db,
            run_id=run.run_id,
            final=final,
            decision_graph=result.get("decision_graph"),
            execution_plan=result.get("execution_plan"),
        )
    except Exception as exc:
        fail_analysis_run(
            db,
            run_id=run.run_id,
            error={"message": str(exc), "code": "workflow_error"},
        )
        raise

    append_message(db, body.session_id, "assistant", json.dumps(final, ensure_ascii=False))
    return {"session_id": body.session_id, "run_id": run.run_id, "final": final}


_STREAM_WORKFLOW_TIMEOUT_SECONDS = 240


@router.post("/chat/stream")
async def api_chat_stream(body: ChatRequest, db: DbSession = Depends(get_db)):
    session = get_session(db, body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    clarification_answer = _resolve_clarification_answer(db, body.session_id, body.message)
    resumed_run_id = None
    if clarification_answer is None:
        project_ctx, ack = _resolve_scope(db, body.session_id, body.message)
        query = body.message
    else:
        project_ctx, query, resumed_run_id = clarification_answer
        ack = None
    user_message = append_message(db, body.session_id, "user", body.message)
    analysis_run = None
    if not ack:
        if resumed_run_id:
            analysis_run = db.get(AnalysisRun, resumed_run_id)
            if analysis_run is None:
                raise HTTPException(status_code=409, detail="等待澄清的研判运行不存在")
            analysis_run.user_message_id = user_message.id
            analysis_run.project_context_json = project_ctx
            analysis_run.status = "planning"
            analysis_run.completed_at = None
            db.commit()
        else:
            analysis_run = create_analysis_run(
                db,
                session_id=body.session_id,
                user_message_id=user_message.id,
                query=query,
                project_ctx=project_ctx,
            )
    initial = _initial_state(query, project_ctx, run_id=analysis_run.run_id if analysis_run else None)
    loading = {
        "kind": "loading",
        "streaming": True,
        "experts": [],
        "final": None,
        "chainId": None,
        "runId": analysis_run.run_id if analysis_run else None,
        "startedAt": int(time.time() * 1000),
    }
    assistant_message = append_message(db, body.session_id, "assistant", json.dumps(loading, ensure_ascii=False))
    logger.info("stream start session=%s query=%r ctx=%s ack=%s", body.session_id, query, project_ctx, bool(ack))
    t0 = time.monotonic()

    def sse(name: str, data: dict) -> str:
        return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def gen():
        def save(content: dict) -> None:
            with SessionLocal() as worker_db:
                update_message(worker_db, assistant_message.id, json.dumps(content, ensure_ascii=False))

        if ack:
            final = {"mode": "chat", "answer": ack}
            save(final)
            yield sse("result", final)
            yield sse("done", {})
            return

        yield sse("run_created", {"run_id": analysis_run.run_id})
        q: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        subscriber_closed = threading.Event()
        terminal_persisted = threading.Event()
        stop_keepalive = threading.Event()
        message_lock = threading.Lock()
        persisted = loading.copy()
        persisted["experts"] = []

        def persist() -> None:
            with SessionLocal() as worker_db:
                update_message(worker_db, assistant_message.id, json.dumps(persisted, ensure_ascii=False))

        def persist_event(mode: str, payload: Any) -> None:
            with message_lock:
                if mode == "custom":
                    event_type = payload.get("type")
                    role = payload.get("role")
                    if event_type in {"expert_start", "expert_done", "node_stage", "node_queued", "node_skipped"} and role:
                        experts = persisted["experts"]
                        expert = next((item for item in experts if item["role"] == role), None)
                        if expert is None:
                            expert = {
                                "role": role,
                                "label": _ROLE_LABEL.get(role, role),
                                "status": "queued",
                                "stage": None,
                                "error": None,
                            }
                            experts.append(expert)
                        if event_type == "expert_start":
                            expert["status"] = "working"
                        elif event_type == "expert_done":
                            expert["status"] = "error" if payload.get("error") else "done"
                            expert["error"] = payload.get("error")
                        elif event_type == "node_skipped":
                            expert["status"] = "skipped"
                        elif event_type == "node_stage":
                            expert["stage"] = payload.get("stage")
                        persist()
                elif mode == "updates":
                    for node, update in payload.items():
                        if node != "final":
                            continue
                        final = update.get("final")
                        if not final:
                            continue
                        if analysis_run and not terminal_persisted.is_set():
                            with SessionLocal() as worker_db:
                                complete_analysis_run(
                                    worker_db,
                                    run_id=analysis_run.run_id,
                                    final=final,
                                    decision_graph=final.get("decision_graph"),
                                    execution_plan=final.get("execution_plan"),
                                )
                            terminal_persisted.set()
                        persisted.clear()
                        persisted.update(final)
                        persist()

        def persist_error(message: str, code: str) -> None:
            if analysis_run and not terminal_persisted.is_set():
                status = "timed_out" if code == "workflow_timeout" else "failed"
                with SessionLocal() as worker_db:
                    fail_analysis_run(
                        worker_db,
                        run_id=analysis_run.run_id,
                        error={"message": message, "code": code},
                        status=status,
                    )
                terminal_persisted.set()
            with message_lock:
                persisted.clear()
                persisted.update({"kind": "error", "error": message, "code": code, "streaming": False})
                persist()

        def publish(mode: str, payload: Any) -> None:
            if subscriber_closed.is_set():
                return
            try:
                loop.call_soon_threadsafe(q.put_nowait, (mode, payload))
            except RuntimeError:
                pass

        def keepalive() -> None:
            while not stop_keepalive.wait(5):
                publish("__keepalive__", None)

        def run_workflow() -> None:
            try:
                for mode, payload in workflow.stream(initial, stream_mode=["updates", "custom"]):
                    persist_event(mode, payload)
                    publish(mode, payload)
                publish("__done__", None)
            except Exception as exc:  # noqa: BLE001
                logger.exception("stream workflow failed session=%s", body.session_id)
                persist_error(str(exc), "workflow_error")
                publish("__error__", str(exc))
            finally:
                stop_keepalive.set()

        future = loop.run_in_executor(None, run_workflow)
        ka_thread = threading.Thread(target=keepalive, daemon=True)
        ka_thread.start()
        final = None
        completed = False
        deadline = time.monotonic() + _STREAM_WORKFLOW_TIMEOUT_SECONDS

        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = {
                        "message": "研判超时，请缩小问题范围后重试",
                        "code": "workflow_timeout",
                        "stage": "workflow",
                        "retryable": True,
                    }
                    persist_error(error["message"], error["code"])
                    yield sse("error", error)
                    break
                try:
                    mode, payload = await asyncio.wait_for(q.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    error = {
                        "message": "研判超时，请缩小问题范围后重试",
                        "code": "workflow_timeout",
                        "stage": "workflow",
                        "retryable": True,
                    }
                    persist_error(error["message"], error["code"])
                    yield sse("error", error)
                    break
                if mode == "__done__":
                    completed = True
                    break
                if mode == "__keepalive__":
                    yield ": keepalive\n\n"
                    continue
                if mode == "__error__":
                    error = {
                        "message": payload,
                        "code": "workflow_error",
                        "stage": "workflow",
                        "retryable": True,
                    }
                    persist_error(error["message"], error["code"])
                    yield sse("error", error)
                    break
                if mode == "custom":
                    d = payload
                    if d.get("type") == "expert_start":
                        yield sse(
                            "expert_start",
                            {"role": d["role"], "label": _ROLE_LABEL.get(d["role"], d["role"])},
                        )
                    elif d.get("type") == "expert_done":
                        yield sse("expert_done", {"role": d["role"], "error": d.get("error")})
                    elif d.get("type") == "node_stage":
                        yield sse(
                            "node_progress",
                            {
                                "role": d["role"],
                                "node_id": d.get("node_id"),
                                "stage": d.get("stage"),
                                "elapsed_ms": d.get("elapsed_ms"),
                            },
                        )
                elif mode == "updates":
                    for node, update in payload.items():
                        if node == "final":
                            final = update.get("final")
                            if not final:
                                continue
                            if final.get("clarification"):
                                yield sse(
                                    "clarification",
                                    {
                                        "message": final["clarification"],
                                        "clarifications": final.get("clarifications") or [],
                                        "execution_plan": final.get("execution_plan"),
                                    },
                                )
                                continue
                            yield sse("result", final)
                        elif node == "plan" and update.get("clarification"):
                            clarification = {"mode": "research", "clarification": update["clarification"]}
                            with message_lock:
                                persisted.clear()
                                persisted.update(clarification)
                                persist()
                            yield sse("clarification", {"message": update["clarification"]})
            if completed and final is None:
                error = {
                    "message": "工作流未产出结果",
                    "code": "missing_result",
                    "stage": "final",
                    "retryable": True,
                }
                persist_error(error["message"], error["code"])
                yield sse("error", error)
            yield sse("done", {})
            logger.info("stream done session=%s elapsed=%dms", body.session_id, int((time.monotonic() - t0) * 1000))
        finally:
            subscriber_closed.set()
            if completed:
                stop_keepalive.set()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
