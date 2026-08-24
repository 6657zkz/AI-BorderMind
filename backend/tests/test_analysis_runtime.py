from __future__ import annotations

import threading
import time

from app.agents import ExpertResult
from app.analysis_runtime import execute_plan
from app.planning import ExecutionPlan, PlanNode


def node(node_id: str, *, depends_on: list[str] | None = None) -> PlanNode:
    return PlanNode(
        id=node_id,
        capability_id=node_id,
        analysis_task_id="test_task",
        expert_role_id=f"{node_id}_role",
        depends_on=depends_on or [],
    )


def test_execute_plan_runs_ready_layer_in_parallel_and_injects_declared_dependencies() -> None:
    plan = ExecutionPlan(
        nodes=[
            node("market"),
            node("cost"),
            node("pricing", depends_on=["market", "cost"]),
        ]
    )
    starts: dict[str, float] = {}
    dependencies: dict[str, dict] = {}
    lock = threading.Lock()

    def run_node(plan_node: PlanNode, upstream: dict):
        with lock:
            starts[plan_node.id] = time.monotonic()
            dependencies[plan_node.id] = upstream
        if plan_node.id in {"market", "cost"}:
            time.sleep(0.08)
        return ExpertResult(
            role=plan_node.expert_role_id,
            conclusion={"node": plan_node.id},
            evidence=[],
        )

    started = time.monotonic()
    executed = execute_plan(
        plan,
        query="测试",
        project_ctx={},
        node_runner=run_node,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    assert abs(starts["market"] - starts["cost"]) < 0.05
    assert starts["pricing"] >= max(starts["market"], starts["cost"])
    assert dependencies["market"] == {}
    assert dependencies["cost"] == {}
    assert dependencies["pricing"] == {
        "market": {"node": "market"},
        "cost": {"node": "cost"},
    }
    assert list(executed.results) == ["market", "cost", "pricing"]


def test_execute_plan_skips_node_with_failed_dependency() -> None:
    plan = ExecutionPlan(nodes=[node("failed"), node("blocked", depends_on=["failed"])])
    called: list[str] = []

    def run_node(plan_node: PlanNode, upstream: dict):
        called.append(plan_node.id)
        return ExpertResult(
            role=plan_node.expert_role_id,
            conclusion={},
            evidence=[],
            error="source unavailable" if plan_node.id == "failed" else None,
        )

    executed = execute_plan(plan, query="测试", project_ctx={}, node_runner=run_node)

    assert called == ["failed"]
    assert executed.results["blocked"]["error"] == "上游节点未成功，已跳过"
    assert executed.results["blocked"]["skipped"] == [
        {"reason": "upstream_failed", "dependencies": ["failed"]}
    ]
