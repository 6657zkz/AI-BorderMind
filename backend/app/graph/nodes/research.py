"""研判工作流节点：意图识别、画像澄清、受控规划、计划运行与结论汇总。"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from ...analysis_runtime import execute_plan
from ...db import SessionLocal
from ...evidence import save_plan_snapshot
from ...llm import LLMError, get_client
from ...planning import ExecutionPlan, PlanningError, plan_request

logger = logging.getLogger("chuhai.workflow")

CHAT_KEYWORDS = ["你好", "你是谁", "能做什么", "谢谢", "介绍一下", "help"]
CHAT_SYSTEM = "你是出海参谋（跨境出海决策智能体）。请用中文简洁回答，非市场研判问题不调用数据。"


def intent_node(state: dict[str, Any]) -> dict[str, Any]:
    if any(kw in state["query"] for kw in CHAT_KEYWORDS):
        logger.info("intent=chat query=%r", state["query"])
        return {"mode": "chat", "roles": [], "rewritten": None}
    logger.info("intent=research query=%r", state["query"])
    return {"mode": "research"}


def plan_node(state: dict[str, Any]) -> dict[str, Any]:
    if state["mode"] == "chat":
        return {"clarification": None}
    ctx = state["project_ctx"] or {}
    if not ctx.get("category_id") or not ctx.get("market_code"):
        logger.info("plan=clarification(缺品类/市场) ctx=%s", ctx)
        clarification = {
            "field_id": "scope",
            "question": "请补充研判范围：面向哪个品类、哪个目标市场？例如：TWS 耳机，美国站。",
            "options": [],
            "required_for": ["scope"],
        }
        return {"clarification": clarification["question"], "clarifications": [clarification]}
    logger.info("plan=proceed ctx=%s", ctx)
    return {"clarification": None}


def rewrite_node(state: dict[str, Any]) -> dict[str, Any]:
    try:
        planned = plan_request(state["query"], state.get("project_ctx") or {})
    except PlanningError as exc:
        logger.info("planning blocked query=%r error=%s", state["query"], exc)
        return {"clarification": str(exc)}
    except LLMError as exc:
        logger.warning("planning LLM failed query=%r error=%s", state["query"], exc)
        return {"clarification": f"无法生成受控研判计划：{exc}"}

    clarifications = [need.model_dump(mode="json") for need in planned.execution_plan.clarifications]
    plan_json = planned.execution_plan.model_dump(mode="json")
    base = {
        "rewritten": planned.title,
        "decision_graph": planned.decision_graph.model_dump(mode="json"),
        "execution_plan": plan_json,
    }
    if clarifications:
        logger.info("planning needs clarification title=%s fields=%s", planned.title, [item["field_id"] for item in clarifications])
        return {
            **base,
            "clarifications": clarifications,
            "clarification": clarifications[0]["question"],
        }

    if state.get("run_id"):
        with SessionLocal() as db:
            save_plan_snapshot(
                db,
                run_id=state["run_id"],
                decision_graph=base["decision_graph"],
                execution_plan=plan_json,
            )
    logger.info("planned=%s nodes=%s", planned.title, [node.id for node in planned.execution_plan.nodes])
    return {**base, "roles": [node.id for node in planned.execution_plan.nodes]}


def execute_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("clarification") or state.get("mode") != "research":
        return {}
    plan = ExecutionPlan.model_validate(state["execution_plan"])
    writer = get_stream_writer()

    def publish(event: dict[str, Any]) -> None:
        writer(event)

    executed = execute_plan(
        plan,
        query=state["query"],
        project_ctx=state.get("project_ctx") or {},
        run_id=state.get("run_id"),
        publish=publish,
    )
    return {"results": executed.results, "upstream": executed.upstream}


def final_node(state: dict[str, Any]) -> dict[str, Any]:
    if state["mode"] == "chat":
        try:
            answer = get_client().complete(
                [{"role": "user", "content": state["query"]}], system=CHAT_SYSTEM
            )
        except LLMError as exc:
            answer = f"（LLM 未配置，无法回答）{exc}"
        return {"final": {"mode": "chat", "answer": answer}}

    if state.get("clarification"):
        return {
            "final": {
                "mode": "research",
                "clarification": state["clarification"],
                "clarifications": state.get("clarifications") or [],
                "rewritten": state.get("rewritten"),
                "decision_graph": state.get("decision_graph"),
                "execution_plan": state.get("execution_plan"),
            }
        }

    plan = ExecutionPlan.model_validate(state["execution_plan"])
    results: dict[str, Any] = state.get("results") or {}
    sections = {node.id: results[node.id] for node in plan.nodes if node.id in results}
    evidence = [
        item
        for node in plan.nodes
        for item in (sections.get(node.id, {}).get("evidence") or [])
    ]
    executive = next((node for node in plan.nodes if node.capability_id == "executive_expert"), None)
    conclusion = sections.get(executive.id, {}).get("conclusion") if executive else None
    return {
        "final": {
            "mode": "research",
            "rewritten": state.get("rewritten"),
            "answer": conclusion,
            "sections": sections,
            "evidence": evidence,
            "roles": [node.id for node in plan.nodes],
            "decision_graph": state.get("decision_graph"),
            "execution_plan": state.get("execution_plan"),
        }
    }
