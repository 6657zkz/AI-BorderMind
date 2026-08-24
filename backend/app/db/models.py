"""SQLAlchemy 模型：对齐 db/schema.sql 的 21 张表（四层 + 租户会话层）。

命名与字段严格跟随 DDL；此处不发明 schema.sql 没有的结构。
JSONB 字段仅在 PostgreSQL 方言下可用（本项目固定 PostgreSQL + pgvector）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _bigint_pk() -> Mapped[int]:
    return mapped_column(BigInteger, primary_key=True, autoincrement=True)


def _text_pk() -> Mapped[str]:
    return mapped_column(String, primary_key=True)


def _ts() -> Mapped[int]:
    return mapped_column(BigInteger, nullable=False)


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------------------------------------------------------------------
# 一、维度层
# ---------------------------------------------------------------------


class Marketplace(Base):
    __tablename__ = "marketplace"

    market_code: Mapped[str] = _text_pk()
    country: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str | None] = mapped_column(String)
    tax_rate: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0)


class Category(Base):
    __tablename__ = "category"

    category_id: Mapped[str] = _text_pk()
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("category.category_id"))
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name_en: Mapped[str | None] = mapped_column(String)
    name_local: Mapped[str | None] = mapped_column(String)
    tariff_rate: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0)


class Product(Base):
    __tablename__ = "product"

    product_id: Mapped[str] = _text_pk()
    market_code: Mapped[str] = mapped_column(
        ForeignKey("marketplace.market_code"), nullable=False
    )
    category_id: Mapped[str] = mapped_column(ForeignKey("category.category_id"), nullable=False)
    brand: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    seller_type: Mapped[str | None] = mapped_column(String)  # brand_store / third_party / fba
    launch_date: Mapped[datetime | None] = mapped_column(Date)
    compliance: Mapped[str | None] = mapped_column(String)
    return_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2))


# ---------------------------------------------------------------------
# 二、事实层（append-only，审计列）
# ---------------------------------------------------------------------


class Review(Base):
    __tablename__ = "review"
    __table_args__ = (Index("idx_review_product_ts", "product_id", "ts"),)

    review_id: Mapped[str] = _text_pk()
    product_id: Mapped[str] = mapped_column(ForeignKey("product.product_id"), nullable=False)
    ts: Mapped[int] = _ts()
    rating: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    helpful_votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    _ingested_at: Mapped[datetime] = _now()
    _source_system: Mapped[str | None] = mapped_column(String)


class PriceTick(Base):
    __tablename__ = "price_tick"

    product_id: Mapped[str] = mapped_column(ForeignKey("product.product_id"), primary_key=True)
    market_code: Mapped[str] = mapped_column(String, nullable=False)
    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, nullable=False)
    discount_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    buybox_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    stock_status: Mapped[str | None] = mapped_column(String)
    sales_rank: Mapped[int | None] = mapped_column(Integer)
    _ingested_at: Mapped[datetime] = _now()
    _source_system: Mapped[str | None] = mapped_column(String)


class SearchVolume(Base):
    __tablename__ = "search_volume"

    category_id: Mapped[str] = mapped_column(
        ForeignKey("category.category_id"), primary_key=True
    )
    market_code: Mapped[str] = mapped_column(String, primary_key=True)
    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    _ingested_at: Mapped[datetime] = _now()
    _source_system: Mapped[str | None] = mapped_column(String)


class SupplySignal(Base):
    __tablename__ = "supply_signal"
    __table_args__ = (Index("idx_supply_signal_type_ts", "signal_type", "ts"),)

    id: Mapped[int] = _bigint_pk()
    ts: Mapped[int] = _ts()
    signal_type: Mapped[str] = mapped_column(String, nullable=False)  # freight_index / fx_rate ...
    region: Mapped[str | None] = mapped_column(String)
    value: Mapped[float | None] = mapped_column(Numeric(14, 4))
    unit: Mapped[str | None] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)
    _ingested_at: Mapped[datetime] = _now()
    _source_system: Mapped[str | None] = mapped_column(String)


# ---------------------------------------------------------------------
# 三、AI 分析层（Gold）
# ---------------------------------------------------------------------


class ReviewAspect(Base):
    __tablename__ = "review_aspect"
    __table_args__ = (
        Index("idx_review_aspect_product", "product_id", "aspect"),
        Index("idx_review_aspect_ap", "aspect", "polarity"),
    )

    id: Mapped[int] = _bigint_pk()
    review_id: Mapped[str] = mapped_column(ForeignKey("review.review_id"), nullable=False)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    aspect: Mapped[str] = mapped_column(String, nullable=False)  # 对齐方面词典
    polarity: Mapped[str] = mapped_column(String, nullable=False)  # pos / neg / neu
    score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    evidence: Mapped[str | None] = mapped_column(Text)


class MarketOpportunity(Base):
    __tablename__ = "market_opportunity"

    category_id: Mapped[str] = mapped_column(String, primary_key=True)
    market_code: Mapped[str] = mapped_column(String, primary_key=True)
    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    demand_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    competition_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    price_band_gap: Mapped[float | None] = mapped_column(Numeric(8, 4))
    opportunity_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    drivers_json: Mapped[dict | None] = mapped_column(JSONB)


class PricingBand(Base):
    __tablename__ = "pricing_band"

    category_id: Mapped[str] = mapped_column(String, primary_key=True)
    market_code: Mapped[str] = mapped_column(String, primary_key=True)
    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    p25: Mapped[float | None] = mapped_column(Numeric(12, 2))
    p50: Mapped[float | None] = mapped_column(Numeric(12, 2))
    p75: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_floor: Mapped[float | None] = mapped_column(Numeric(12, 2))
    recommended_window: Mapped[str | None] = mapped_column(String)


class ProductPosition(Base):
    __tablename__ = "product_position"

    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    market_code: Mapped[str] = mapped_column(String, primary_key=True)
    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    top_pros: Mapped[list | None] = mapped_column(JSONB)  # [aspect, freq] 数组
    top_cons: Mapped[list | None] = mapped_column(JSONB)
    positioning_label: Mapped[str | None] = mapped_column(String)


class Signal(Base):
    __tablename__ = "signal"
    __table_args__ = (Index("idx_signal_type_observed", "signal_type", "observed_at"),)

    id: Mapped[int] = _bigint_pk()
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    entity: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(String)
    evidence_url: Mapped[str | None] = mapped_column(String)
    observed_at: Mapped[int | None] = mapped_column(BigInteger)
    confidence: Mapped[str | None] = mapped_column(String)  # low / medium / high
    status: Mapped[str] = mapped_column(String, nullable=False, default="new")
    project_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = _now()


# ---------------------------------------------------------------------
# 四、内部数据层 L2
# ---------------------------------------------------------------------


class InternalSku(Base):
    __tablename__ = "internal_sku"

    sku: Mapped[str] = _text_pk()
    merchant_id: Mapped[str | None] = mapped_column(String)
    category_id: Mapped[str | None] = mapped_column(String)
    market_code: Mapped[str | None] = mapped_column(String)
    cost_cogs: Mapped[float | None] = mapped_column(Numeric(12, 2))
    shipping_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    commission_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    target_margin: Mapped[float | None] = mapped_column(Numeric(8, 4))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InternalSales(Base):
    __tablename__ = "internal_sales"

    sku: Mapped[str] = mapped_column(ForeignKey("internal_sku.sku"), primary_key=True)
    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    units: Mapped[int | None] = mapped_column(Integer)
    revenue: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ad_spend: Mapped[float | None] = mapped_column(Numeric(12, 2))
    acos: Mapped[float | None] = mapped_column(Numeric(8, 4))


class SkuProductMap(Base):
    __tablename__ = "sku_product_map"

    sku: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, primary_key=True)


# ---------------------------------------------------------------------
# 五、知识层
# ---------------------------------------------------------------------


class MetricDict(Base):
    __tablename__ = "metric_dict"

    metric_id: Mapped[str] = _text_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    formula: Mapped[str | None] = mapped_column(String)
    data_source: Mapped[str | None] = mapped_column(String)
    unit: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")


class AspectDict(Base):
    __tablename__ = "aspect_dict"

    aspect_id: Mapped[int] = _bigint_pk()
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)  # seed / return_reason_code / ai_proposed
    status: Mapped[str] = mapped_column(String, nullable=False, default="seed")
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------
# 六、租户与会话层
# ---------------------------------------------------------------------


class Merchant(Base):
    __tablename__ = "merchant"

    merchant_id: Mapped[str] = _text_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = _now()


class Project(Base):
    __tablename__ = "project"

    project_id: Mapped[str] = _text_pk()
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.merchant_id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[str | None] = mapped_column(String)
    market_code: Mapped[str | None] = mapped_column(String)
    profile_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Session(Base):
    __tablename__ = "session"

    session_id: Mapped[str] = _text_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("project.project_id"), nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchant.merchant_id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String)  # 会话名（默认取首条消息 / 用户重命名）
    mode: Mapped[str | None] = mapped_column(String)  # research / monitor
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = _bigint_pk()
    session_id: Mapped[str] = mapped_column(ForeignKey("session.session_id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # user / assistant / signal
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[int | None] = mapped_column(BigInteger)


class AnalysisRun(Base):
    __tablename__ = "analysis_run"
    __table_args__ = (
        Index("idx_analysis_run_session_started", "session_id", "started_at"),
        Index("idx_analysis_run_status_started", "status", "started_at"),
    )

    run_id: Mapped[str] = _text_pk()
    session_id: Mapped[str] = mapped_column(ForeignKey("session.session_id", ondelete="CASCADE"), nullable=False)
    user_message_id: Mapped[int] = mapped_column(ForeignKey("message.id", ondelete="CASCADE"), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    project_context_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    decision_graph_json: Mapped[dict | None] = mapped_column(JSONB)
    execution_plan_json: Mapped[dict | None] = mapped_column(JSONB)
    final_json: Mapped[dict | None] = mapped_column(JSONB)
    error_json: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = _now()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisRunEvent(Base):
    __tablename__ = "analysis_run_event"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_analysis_run_event_run_seq"),
        Index("idx_analysis_run_event_run_seq", "run_id", "seq"),
    )

    id: Mapped[int] = _bigint_pk()
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_run.run_id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    node_id: Mapped[str | None] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _now()


class AnalysisClarification(Base):
    __tablename__ = "analysis_clarification"
    __table_args__ = (
        UniqueConstraint("run_id", "field_id", name="uq_analysis_clarification_run_field"),
        Index("idx_analysis_clarification_run_status", "run_id", "status"),
    )

    id: Mapped[int] = _bigint_pk()
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_run.run_id", ondelete="CASCADE"), nullable=False)
    field_id: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String, nullable=False, default="waiting")
    answer_json: Mapped[dict | None] = mapped_column(JSONB)
    answered_message_id: Mapped[int | None] = mapped_column(ForeignKey("message.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _now()
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisNodeRun(Base):
    __tablename__ = "analysis_node_run"
    __table_args__ = (
        UniqueConstraint("run_id", "node_id", name="uq_analysis_node_run_run_node"),
        Index("idx_analysis_node_run_run", "run_id", "id"),
        Index("idx_analysis_node_run_status", "run_id", "status"),
    )

    id: Mapped[int] = _bigint_pk()
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_run.run_id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    input_summary_json: Mapped[dict | None] = mapped_column(JSONB)
    output_summary_json: Mapped[dict | None] = mapped_column(JSONB)
    skipped_json: Mapped[list | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = _now()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)


class EvidenceChainRecord(Base):
    __tablename__ = "evidence_chain"
    __table_args__ = (Index("idx_evidence_chain_created", "created_at"),)

    chain_id: Mapped[str] = _text_pk()
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_run.run_id", ondelete="CASCADE"), nullable=False, unique=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _now()


class EvidenceEntryRecord(Base):
    __tablename__ = "evidence_entry"
    __table_args__ = (
        UniqueConstraint("chain_id", "ordinal", name="uq_evidence_entry_chain_ordinal"),
        Index("idx_evidence_entry_chain_ordinal", "chain_id", "ordinal"),
    )

    id: Mapped[int] = _bigint_pk()
    chain_id: Mapped[str] = mapped_column(ForeignKey("evidence_chain.chain_id", ondelete="CASCADE"), nullable=False)
    node_run_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_node_run.id", ondelete="SET NULL"))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    operator: Mapped[str] = mapped_column(String, nullable=False)
    params_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rows_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    executed_at: Mapped[str | None] = mapped_column(String)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = _now()
