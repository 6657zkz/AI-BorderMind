from __future__ import annotations

import concurrent.futures
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..agents import ExpertContext, ExpertResult, get_agent
from ..db import SessionLocal
from ..evidence import append_run_event, finish_node_run, skip_node_run, start_node_run
from ..planning import ExecutionPlan, PlanNode

logger = logging.getLogger("chuhai.runtime")

NodeRunner = Callable[[PlanNode, dict[str, Any]], ExpertResult]
EventPublisher = Callable[[dict[str, Any]], None]


@dataclass
class PlanExecutionResult:
    results: dict[str, dict[str, Any]]
    upstream: dict[str, dict[str, Any]]


def execute_plan(
    plan: ExecutionPlan,
    *,
    query: str,
    project_ctx: dict[str, Any],
    run_id: str | None = None,
    publish: EventPublisher | None = None,
    node_runner: NodeRunner | None = None,
) -> PlanExecutionResult:
    results: dict[str, dict[str, Any]] = {}
    upstream: dict[str, dict[str, Any]] = {}

    def emit(event_type: str, node: PlanNode, **data: Any) -> None:
        event = {
            "type": event_type,
            "node_id": node.id,
            "role": node.expert_role_id,
            **data,
        }
        if run_id:
            with SessionLocal() as db:
                append_run_event(
                    db,
                    run_id=run_id,
                    node_id=node.id,
                    event_type=event_type,
                    payload={key: value for key, value in event.items() if key not in {"type", "node_id"}},
                )
                db.commit()
        if publish is not None:
            publish(event)

    def run_node(node: PlanNode, dependencies: dict[str, Any]) -> ExpertResult:
        if node_runner is not None:
            return node_runner(node, dependencies)
        return _execute_node(
            node,
            query=query,
            project_ctx=project_ctx,
            dependencies=dependencies,
            run_id=run_id,
            publish=emit,
        )

    for layer in plan.topological_layers():
        runnable: list[PlanNode] = []
        for node in layer:
            failed_dependencies = [
                dependency
                for dependency in node.depends_on
                if (results.get(dependency) or {}).get("error")
            ]
            if failed_dependencies:
                reason = {
                    "reason": "upstream_failed",
                    "dependencies": failed_dependencies,
                }
                result = ExpertResult(
                    role=node.expert_role_id,
                    conclusion={},
                    evidence=[],
                    skipped=[reason],
                    error="上游节点未成功，已跳过",
                )
                if run_id:
                    with SessionLocal() as db:
                        start_node_run(
                            db,
                            run_id=run_id,
                            node_id=node.id,
                            role=node.expert_role_id,
                            input_summary={"query": query, "upstream_node_ids": list(node.depends_on)},
                        )
                        skip_node_run(
                            db,
                            run_id=run_id,
                            node_id=node.id,
                            skipped=[reason],
                        )
                results[node.id] = result.as_dict()
                upstream[node.id] = result.conclusion
                emit("node_skipped", node, reason=reason)
                continue
            runnable.append(node)

        if not runnable:
            continue

        for node in runnable:
            emit("node_queued", node)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(runnable)) as pool:
            futures = {
                pool.submit(
                    run_node,
                    node,
                    {dependency: upstream[dependency] for dependency in node.depends_on},
                ): node
                for node in runnable
            }
            for future in concurrent.futures.as_completed(futures):
                node = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("plan node crashed node=%s", node.id)
                    result = ExpertResult(
                        role=node.expert_role_id,
                        conclusion={},
                        evidence=[],
                        error=f"节点执行失败: {exc}",
                    )
                results[node.id] = result.as_dict()
                upstream[node.id] = result.conclusion
                emit("expert_done", node, error=result.error)

    return PlanExecutionResult(results=results, upstream=upstream)


def _execute_node(
    node: PlanNode,
    *,
    query: str,
    project_ctx: dict[str, Any],
    dependencies: dict[str, Any],
    run_id: str | None,
    publish: Callable[[str, PlanNode], None] | Callable[..., None],
) -> ExpertResult:
    started = time.monotonic()
    publish("expert_start", node)
    publish("node_stage", node, stage="data_fetch_started")
    with SessionLocal() as db:
        if run_id:
            start_node_run(
                db,
                run_id=run_id,
                node_id=node.id,
                role=node.expert_role_id,
                input_summary={
                    "query": query,
                    "upstream_node_ids": list(node.depends_on),
                    "capability_id": node.capability_id,
                },
            )
        try:
            agent = get_agent(node.expert_role_id)
            result = agent.run(
                db,
                ExpertContext(query=query, project_ctx=project_ctx, upstream=dependencies),
                capability_id=node.capability_id,
                on_stage=lambda stage, **data: publish("node_stage", node, stage=stage, **data),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("plan node failed node=%s", node.id)
            result = ExpertResult(
                role=node.expert_role_id,
                conclusion={},
                evidence=[],
                error=f"节点执行失败: {exc}",
            )
        elapsed = int((time.monotonic() - started) * 1000)
        if run_id:
            finish_node_run(
                db,
                run_id=run_id,
                node_id=node.id,
                conclusion=result.conclusion,
                evidence_count=len(result.evidence),
                skipped=result.skipped,
                error=result.error,
                elapsed_ms=elapsed,
            )
    publish("node_stage", node, stage="failed" if result.error else "succeeded", elapsed_ms=elapsed)
    logger.info(
        "plan_node=%s role=%s elapsed=%dms evidence=%d error=%s",
        node.id,
        node.expert_role_id,
        elapsed,
        len(result.evidence),
        result.error,
    )
    return result
