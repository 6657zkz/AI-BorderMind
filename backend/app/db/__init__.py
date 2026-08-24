"""数据访问层：连接 + 模型（对齐 db/schema.sql 21 张表）。"""

from .models import (
    AnalysisClarification,
    AnalysisNodeRun,
    AnalysisRun,
    AnalysisRunEvent,
    AspectDict,
    Base,
    Category,
    EvidenceChainRecord,
    EvidenceEntryRecord,
    InternalSales,
    InternalSku,
    MarketOpportunity,
    Marketplace,
    Merchant,
    Message,
    MetricDict,
    PriceTick,
    PricingBand,
    Product,
    ProductPosition,
    Project,
    Review,
    ReviewAspect,
    SearchVolume,
    Session,
    Signal,
    SkuProductMap,
    SupplySignal,
)
from .session import SessionLocal, engine, get_db

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    # 研判运行与证据层
    "AnalysisRun",
    "AnalysisNodeRun",
    "AnalysisRunEvent",
    "AnalysisClarification",
    "EvidenceChainRecord",
    "EvidenceEntryRecord",
    # 维度层
    "Marketplace",
    "Category",
    "Product",
    # 事实层
    "Review",
    "PriceTick",
    "SearchVolume",
    "SupplySignal",
    # AI 分析层
    "ReviewAspect",
    "MarketOpportunity",
    "PricingBand",
    "ProductPosition",
    "Signal",
    # 内部数据层
    "InternalSku",
    "InternalSales",
    "SkuProductMap",
    # 知识层
    "MetricDict",
    "AspectDict",
    # 租户会话层
    "Merchant",
    "Project",
    "Session",
    "Message",
]
