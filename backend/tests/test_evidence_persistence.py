from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.db import (
    AnalysisRun,
    Base,
    EvidenceChainRecord,
    EvidenceEntryRecord,
    Merchant,
    Message,
    Project,
    Session as SessionModel,
)
from app.evidence import (
    complete_analysis_run,
    create_analysis_run,
    finish_node_run,
    get_chain,
    recent_chains,
    start_node_run,
)
from app.operators.base import OperatorResult


@pytest.fixture
def trace_db():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL 未配置，跳过 PostgreSQL 持久化集成测试")

    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    suffix = uuid.uuid4().hex[:12]
    merchant_id = f"test_merchant_{suffix}"
    project_id = f"test_project_{suffix}"
    session_id = f"test_session_{suffix}"
    try:
        db.add(Merchant(merchant_id=merchant_id, name="测试商户"))
        db.add(Project(project_id=project_id, merchant_id=merchant_id, name="测试项目"))
        db.add(SessionModel(session_id=session_id, project_id=project_id, merchant_id=merchant_id))
        message = Message(session_id=session_id, role="user", content="测试研判", ts=1)
        db.add(message)
        db.commit()
        db.refresh(message)
        yield db, session_id, message.id
    finally:
        db.rollback()
        db.execute(delete(AnalysisRun).where(AnalysisRun.session_id == session_id))
        db.execute(delete(Message).where(Message.session_id == session_id))
        db.execute(delete(SessionModel).where(SessionModel.session_id == session_id))
        db.execute(delete(Project).where(Project.project_id == project_id))
        db.execute(delete(Merchant).where(Merchant.merchant_id == merchant_id))
        db.commit()
        db.close()
        engine.dispose()


def test_operator_result_exports_full_row_count() -> None:
    result = OperatorResult(
        operator="test_operator",
        params={},
        sql="SELECT 1",
        rows=[{"value": 1}],
        row_count=2,
        executed_at="2026-08-24T00:00:00+00:00",
        elapsed_ms=3,
        truncated=True,
    )

    assert result.as_dict()["row_count"] == 2
    assert result.as_dict()["truncated"] is True


def test_analysis_run_persists_ordered_evidence_and_node_link(trace_db) -> None:
    db, session_id, message_id = trace_db
    run = create_analysis_run(
        db,
        session_id=session_id,
        user_message_id=message_id,
        query="美国站 TWS 耳机需求趋势",
        project_ctx={"project_id": "test", "category_id": "cat_tws", "market_code": "US"},
    )

    node = start_node_run(
        db,
        run_id=run.run_id,
        node_id="demand_researcher",
        role="demand_researcher",
        input_summary={"query": run.query, "upstream_roles": []},
    )
    finish_node_run(
        db,
        run_id=run.run_id,
        node_id="demand_researcher",
        conclusion={"summary": "需求增长"},
        evidence_count=1,
        skipped=[],
        error=None,
        elapsed_ms=12,
    )

    final = {
        "mode": "research",
        "sections": {
            "demand_researcher": {
                "evidence": [
                    {
                        "operator": "search_volume_trend",
                        "params": {"category_id": "cat_tws", "market_code": "US"},
                        "sql": "SELECT volume FROM search_volume",
                        "rows": [{"volume": 100}],
                        "row_count": 2,
                        "truncated": True,
                        "executed_at": "2026-08-24T00:00:00+00:00",
                        "elapsed_ms": 5,
                    }
                ]
            }
        },
    }
    chain = complete_analysis_run(
        db,
        run_id=run.run_id,
        final=final,
        decision_graph={"query": run.query, "nodes": []},
        execution_plan={"goals": ["product_selection"], "nodes": []},
    )

    assert chain is not None
    assert final["chain_id"] == chain.chain_id
    db.expire_all()

    stored_run = db.get(AnalysisRun, run.run_id)
    assert stored_run.status == "succeeded"
    assert stored_run.final_json["chain_id"] == chain.chain_id
    assert stored_run.decision_graph_json == {"query": run.query, "nodes": []}

    stored_entry = db.execute(
        select(EvidenceEntryRecord).where(EvidenceEntryRecord.chain_id == chain.chain_id)
    ).scalar_one()
    assert stored_entry.ordinal == 0
    assert stored_entry.node_run_id == node.id
    assert stored_entry.row_count == 2
    assert stored_entry.truncated is True

    loaded = get_chain(db, chain.chain_id)
    assert loaded is not None
    assert loaded.as_dict()["entries"] == [
        {
            "role": "demand_researcher",
            "operator": "search_volume_trend",
            "params": {"category_id": "cat_tws", "market_code": "US"},
            "sql": "SELECT volume FROM search_volume",
            "rows": [{"volume": 100}],
            "executed_at": "2026-08-24T00:00:00+00:00",
            "elapsed_ms": 5,
            "row_count": 2,
            "truncated": True,
        }
    ]
    assert [item["chain_id"] for item in recent_chains(db, limit=10)] == [chain.chain_id]
    assert db.get(EvidenceChainRecord, chain.chain_id) is not None


def test_clarification_keeps_run_open(trace_db) -> None:
    db, session_id, message_id = trace_db
    run = create_analysis_run(
        db,
        session_id=session_id,
        user_message_id=message_id,
        query="美国站 TWS 耳机如何定价",
        project_ctx={"project_id": "test"},
    )
    final = {
        "mode": "research",
        "clarification": "你的目标毛利率是多少？",
        "clarifications": [{"field_id": "target_margin"}],
    }

    chain = complete_analysis_run(
        db,
        run_id=run.run_id,
        final=final,
        decision_graph={"query": run.query, "nodes": []},
        execution_plan={"goals": ["pricing_strategy"], "nodes": []},
    )

    assert chain is None
    db.expire_all()
    stored_run = db.get(AnalysisRun, run.run_id)
    assert stored_run.status == "waiting_clarification"
    assert stored_run.completed_at is None
    assert stored_run.final_json == final


def test_analysis_node_run_reuses_run_node_identity(trace_db) -> None:
    db, session_id, message_id = trace_db
    run = create_analysis_run(
        db,
        session_id=session_id,
        user_message_id=message_id,
        query="测试重试",
        project_ctx={"project_id": "test"},
    )

    first = start_node_run(
        db,
        run_id=run.run_id,
        node_id="demand_researcher",
        role="demand_researcher",
        input_summary={},
    )
    retry = start_node_run(
        db,
        run_id=run.run_id,
        node_id="demand_researcher",
        role="demand_researcher",
        input_summary={},
    )

    assert retry.id == first.id
    assert retry.retry_count == 1
