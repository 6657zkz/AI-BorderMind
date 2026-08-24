from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..project.decision_parameters import DECISION_PARAMETERS
from .contracts import ClarificationNeed, DataRequirement, PlanningError


@dataclass(frozen=True)
class ExpertRoleDefinition:
    id: str
    name: str
    description: str


@dataclass(frozen=True)
class AnalysisTaskDefinition:
    id: str
    name: str
    description: str
    required_outputs: tuple[str, ...]


@dataclass(frozen=True)
class DataCapabilityDefinition:
    id: str
    name: str
    description: str
    operator_id: str


@dataclass(frozen=True)
class DataCapabilityBinding:
    data_capability_id: str
    params: tuple[tuple[str, Any], ...] = ()

    def operator_spec(self) -> str | tuple[str, dict[str, Any]]:
        operator_id = DATA_CAPABILITIES[self.data_capability_id].operator_id
        return operator_id if not self.params else (operator_id, dict(self.params))


@dataclass(frozen=True)
class CapabilityDefinition:
    id: str
    name: str
    description: str
    analysis_task_id: str
    expert_role_id: str
    requires: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    data_bindings: tuple[DataCapabilityBinding, ...] = ()
    data_requirements: tuple[DataRequirement, ...] = ()
    planning_enabled: bool = True

    @property
    def needs_data(self) -> bool:
        return bool(self.data_bindings)

    @property
    def data_capability_ids(self) -> tuple[str, ...]:
        return tuple(binding.data_capability_id for binding in self.data_bindings)

    @property
    def operator_specs(self) -> list[str | tuple[str, dict[str, Any]]]:
        return [binding.operator_spec() for binding in self.data_bindings]


@dataclass(frozen=True)
class DecisionTypeBlueprint:
    id: str
    name: str
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()
    profile_requirements: tuple[ClarificationNeed, ...] = ()


EXPERT_ROLES: dict[str, ExpertRoleDefinition] = {
    "demand_researcher": ExpertRoleDefinition("demand_researcher", "需求趋势研究员", "根据搜索量时序判断需求增长和波动"),
    "competitive_analyst": ExpertRoleDefinition("competitive_analyst", "竞争格局分析师", "分析类目机会评分和竞争结构"),
    "feedback_analyst": ExpertRoleDefinition("feedback_analyst", "差评机会分析师", "从评论根因识别未满足需求"),
    "price_band_analyst": ExpertRoleDefinition("price_band_analyst", "价格带分析师", "分析价格分布、断层和切入区间"),
    "cost_modeler": ExpertRoleDefinition("cost_modeler", "成本建模专家", "计算成本地板和目标毛利下限"),
    "competitor_benchmark": ExpertRoleDefinition("competitor_benchmark", "竞品对标分析师", "对比竞品定位、口碑与价格动向"),
    "selection_score": ExpertRoleDefinition("selection_score", "选品决策整合专家", "整合需求、竞争、价格和评论证据"),
    "pricing_optimizer": ExpertRoleDefinition("pricing_optimizer", "跨境定价策略师", "基于成本和市场证据给出定价建议"),
    "selling_point_analyst": ExpertRoleDefinition("selling_point_analyst", "卖点对比分析师", "识别竞品差异化卖点"),
    "search_gap_analyst": ExpertRoleDefinition("search_gap_analyst", "搜索需求分析师", "识别搜索需求和流量切入点"),
    "strategy_node": ExpertRoleDefinition("strategy_node", "竞争策略整合专家", "整合差评、卖点和流量证据形成打法"),
    "executive_expert": ExpertRoleDefinition("executive_expert", "决策整合专家", "整合分析结论、行动和复核条件"),
}


ANALYSIS_TASKS: dict[str, AnalysisTaskDefinition] = {
    "demand_trend_analysis": AnalysisTaskDefinition("demand_trend_analysis", "需求趋势分析", "判断类目搜索量趋势和波动", ("demand_growth", "trend_confidence")),
    "competition_landscape_analysis": AnalysisTaskDefinition("competition_landscape_analysis", "竞争格局分析", "判断机会评分、竞争结构和进入壁垒", ("competition_level", "competition_drivers")),
    "review_pain_point_analysis": AnalysisTaskDefinition("review_pain_point_analysis", "评论痛点分析", "识别高频差评根因和未满足需求", ("negative_review_share", "pain_points")),
    "market_price_band_analysis": AnalysisTaskDefinition("market_price_band_analysis", "市场价格带分析", "计算价格分位和机会区间", ("price_band", "price_gap")),
    "cost_floor_analysis": AnalysisTaskDefinition("cost_floor_analysis", "成本地板分析", "计算 SKU 成本结构和毛利底线", ("cost_floor", "margin_constraints")),
    "competitor_benchmark_analysis": AnalysisTaskDefinition("competitor_benchmark_analysis", "竞品对标分析", "比较竞品优劣、价格和排名动向", ("competitor_benchmark",)),
    "product_selection_recommendation": AnalysisTaskDefinition("product_selection_recommendation", "选品建议", "整合市场证据形成进入建议", ("selection_recommendation", "selection_score")),
    "pricing_recommendation": AnalysisTaskDefinition("pricing_recommendation", "定价建议", "形成推荐价格、价格区间和风险", ("pricing_recommendation", "recommended_price", "price_range")),
    "selling_point_gap_analysis": AnalysisTaskDefinition("selling_point_gap_analysis", "卖点缺口分析", "从竞品优劣识别差异化卖点", ("selling_point_gaps",)),
    "search_gap_analysis": AnalysisTaskDefinition("search_gap_analysis", "搜索需求空白分析", "从搜索趋势识别流量切入机会", ("search_gaps",)),
    "competitive_strategy_recommendation": AnalysisTaskDefinition("competitive_strategy_recommendation", "竞争打法建议", "整合卖点、评论和流量形成打法", ("competitive_strategy",)),
    "decision_summary": AnalysisTaskDefinition("decision_summary", "决策整合", "收敛结论、行动、风险和复核条件", ("decision_summary", "actions", "risks")),
}


DATA_CAPABILITIES: dict[str, DataCapabilityDefinition] = {
    "search_volume_trend": DataCapabilityDefinition("search_volume_trend", "搜索量趋势查询", "查询类目搜索量时序和增长率", "search_volume_trend"),
    "market_opportunity": DataCapabilityDefinition("market_opportunity", "市场机会查询", "查询市场机会评分和驱动因素", "market_opportunity"),
    "aspect_complaint_share": DataCapabilityDefinition("aspect_complaint_share", "评论痛点查询", "统计评论方面词负面占比", "aspect_complaint_share"),
    "price_percentile": DataCapabilityDefinition("price_percentile", "价格分位数查询", "计算竞品价格分布", "price_percentile"),
    "pricing_band": DataCapabilityDefinition("pricing_band", "价格带查询", "查询价格带和建议窗口", "pricing_band"),
    "competitor_price_history": DataCapabilityDefinition("competitor_price_history", "竞品价格历史查询", "查询竞品价格和排名变化", "competitor_price_history"),
    "product_position": DataCapabilityDefinition("product_position", "竞品定位查询", "查询竞品优劣定位", "product_position"),
    "review_sentiment": DataCapabilityDefinition("review_sentiment", "评论情感查询", "查询评论情感和证据", "review_sentiment"),
    "supply_signal_query": DataCapabilityDefinition("supply_signal_query", "供应链信号查询", "查询运费、汇率等成本信号", "supply_signal_query"),
    "internal_sku_query": DataCapabilityDefinition("internal_sku_query", "内部 SKU 查询", "查询成本、佣金和目标毛利", "internal_sku_query"),
}


CAPABILITIES: dict[str, CapabilityDefinition] = {
    "demand_researcher": CapabilityDefinition(
        id="demand_researcher", name="需求趋势分析", description="分析类目搜索量/需求端趋势", analysis_task_id="demand_trend_analysis", expert_role_id="demand_researcher",
        produces=("demand_growth",), data_bindings=(DataCapabilityBinding("search_volume_trend"),),
        data_requirements=(DataRequirement(metric_id="demand_growth", min_sample_size=1, max_age_hours=168),),
    ),
    "competitive_analyst": CapabilityDefinition(
        id="competitive_analyst", name="竞争格局分析", description="梳理类目竞争结构和机会评分", analysis_task_id="competition_landscape_analysis", expert_role_id="competitive_analyst",
        produces=("competition_level",), data_bindings=(DataCapabilityBinding("market_opportunity"), DataCapabilityBinding("product_position")),
        data_requirements=(DataRequirement(metric_id="competition_level", min_sample_size=1, max_age_hours=168),),
    ),
    "feedback_analyst": CapabilityDefinition(
        id="feedback_analyst", name="评论痛点分析", description="分析差评根因和未满足需求", analysis_task_id="review_pain_point_analysis", expert_role_id="feedback_analyst",
        produces=("negative_review_share",), data_bindings=(DataCapabilityBinding("aspect_complaint_share"), DataCapabilityBinding("review_sentiment")),
        data_requirements=(DataRequirement(metric_id="negative_review_share", min_sample_size=1, max_age_hours=720),),
    ),
    "price_band_analyst": CapabilityDefinition(
        id="price_band_analyst", name="市场价格带分析", description="分析竞品价格分位、价格带和断层", analysis_task_id="market_price_band_analysis", expert_role_id="price_band_analyst",
        produces=("price_band",), data_bindings=(DataCapabilityBinding("price_percentile"), DataCapabilityBinding("pricing_band")),
        data_requirements=(DataRequirement(metric_id="price_band", min_sample_size=1, max_age_hours=168),),
    ),
    "cost_modeler": CapabilityDefinition(
        id="cost_modeler", name="成本地板分析", description="核算 SKU 成本、运费和汇率影响", analysis_task_id="cost_floor_analysis", expert_role_id="cost_modeler",
        produces=("cost_floor",), data_bindings=(
            DataCapabilityBinding("internal_sku_query"),
            DataCapabilityBinding("supply_signal_query", (("signal_type", "freight_index"),)),
            DataCapabilityBinding("supply_signal_query", (("signal_type", "fx_rate"),)),
        ), data_requirements=(DataRequirement(metric_id="cost_floor", min_sample_size=1, max_age_hours=168),),
    ),
    "competitor_benchmark": CapabilityDefinition(
        id="competitor_benchmark", name="竞品对标分析", description="对标竞品优劣、评论和价格排名动向", analysis_task_id="competitor_benchmark_analysis", expert_role_id="competitor_benchmark",
        produces=("competitor_benchmark",), data_bindings=(DataCapabilityBinding("product_position"), DataCapabilityBinding("review_sentiment"), DataCapabilityBinding("competitor_price_history")),
        data_requirements=(DataRequirement(metric_id="competitor_benchmark", min_sample_size=1, max_age_hours=168),),
    ),
    "selection_score": CapabilityDefinition(
        id="selection_score", name="选品建议", description="整合需求、竞争、价格和评论形成选品建议", analysis_task_id="product_selection_recommendation", expert_role_id="selection_score",
        requires=("demand_researcher", "competitive_analyst", "price_band_analyst", "feedback_analyst"), produces=("selection_recommendation",),
    ),
    "pricing_optimizer": CapabilityDefinition(
        id="pricing_optimizer", name="定价建议", description="整合成本、价格带和竞品证据形成定价建议", analysis_task_id="pricing_recommendation", expert_role_id="pricing_optimizer",
        requires=("cost_modeler", "price_band_analyst", "competitor_benchmark"), produces=("pricing_recommendation",),
        data_bindings=(DataCapabilityBinding("pricing_band"), DataCapabilityBinding("price_percentile"), DataCapabilityBinding("internal_sku_query")),
    ),
    "selling_point_analyst": CapabilityDefinition(
        id="selling_point_analyst", name="卖点缺口分析", description="比较竞品卖点和差评", analysis_task_id="selling_point_gap_analysis", expert_role_id="selling_point_analyst",
        produces=("selling_point_gaps",), data_bindings=(DataCapabilityBinding("product_position"), DataCapabilityBinding("review_sentiment")), planning_enabled=False,
    ),
    "search_gap_analyst": CapabilityDefinition(
        id="search_gap_analyst", name="搜索需求空白分析", description="当前仅有类目级搜索趋势，暂不进入新规划主链", analysis_task_id="search_gap_analysis", expert_role_id="search_gap_analyst",
        produces=("search_gaps",), data_bindings=(DataCapabilityBinding("search_volume_trend"),), planning_enabled=False,
    ),
    "strategy_node": CapabilityDefinition(
        id="strategy_node", name="竞争打法建议", description="当前缺少关键词级数据契约，暂不进入新规划主链", analysis_task_id="competitive_strategy_recommendation", expert_role_id="strategy_node",
        requires=("feedback_analyst", "selling_point_analyst", "search_gap_analyst"), produces=("competitive_strategy",), planning_enabled=False,
    ),
    "executive_expert": CapabilityDefinition(
        id="executive_expert", name="决策整合", description="整合各项分析结论、行动和风险", analysis_task_id="decision_summary", expert_role_id="executive_expert",
        produces=("decision_summary",),
    ),
}


DECISION_TYPES: dict[str, DecisionTypeBlueprint] = {
    "product_selection": DecisionTypeBlueprint(
        id="product_selection", name="选品决策",
        required_capabilities=("demand_researcher", "competitive_analyst", "price_band_analyst", "feedback_analyst", "selection_score"),
    ),
    "pricing_strategy": DecisionTypeBlueprint(
        id="pricing_strategy", name="定价决策",
        required_capabilities=("cost_modeler", "price_band_analyst", "competitor_benchmark", "pricing_optimizer"),
        profile_requirements=(ClarificationNeed(field_id="target_margin", question="你的目标毛利率是多少？", required_for=["pricing_optimizer"], options=["20%", "30%", "40%"]),),
    ),
    "competitive_strategy": DecisionTypeBlueprint(
        id="competitive_strategy", name="竞争打法决策",
        required_capabilities=("feedback_analyst", "selling_point_analyst", "search_gap_analyst", "strategy_node"),
    ),
}


KNOWN_METRICS = {
    "demand_growth", "competition_level", "negative_review_share", "price_band", "cost_floor", "target_margin",
}
KNOWN_ENTITIES = {"market", "category", "product", "competitor", "internal_sku", "supply_signal"}


# 兼容旧规划器名称；两者指向同一份不可变目录，不再维护独立规则。
GOALS = DECISION_TYPES


def get_capability(capability_id: str) -> CapabilityDefinition:
    try:
        return CAPABILITIES[capability_id]
    except KeyError as exc:
        raise PlanningError(f"未注册能力: {capability_id}") from exc


def get_legacy_capability_for_role(role_id: str) -> CapabilityDefinition:
    matches = [capability for capability in CAPABILITIES.values() if capability.expert_role_id == role_id]
    if len(matches) != 1:
        raise PlanningError(f"角色 {role_id} 没有唯一的兼容能力绑定")
    return matches[0]


def catalog_entries(*, include_legacy: bool = False) -> list[dict[str, str]]:
    return [
        {"role": capability.expert_role_id, "capability": capability.id, "name": capability.name, "desc": capability.description}
        for capability in CAPABILITIES.values()
        if include_legacy or capability.planning_enabled
    ]


def validate_catalog(*, persona_roles: Iterable[str], operator_ids: Iterable[str]) -> list[str]:
    known_persona_roles = set(persona_roles)
    known_operator_ids = set(operator_ids)
    errors: list[str] = []

    for capability in CAPABILITIES.values():
        if capability.analysis_task_id not in ANALYSIS_TASKS:
            errors.append(f"能力 {capability.id} 引用了未注册分析任务 {capability.analysis_task_id}")
        task = ANALYSIS_TASKS[capability.analysis_task_id]
        if not set(capability.produces) <= set(task.required_outputs):
            errors.append(f"能力 {capability.id} 的输出未包含在分析任务 {capability.analysis_task_id} 契约中")
        if capability.expert_role_id not in EXPERT_ROLES:
            errors.append(f"能力 {capability.id} 引用了未注册专家角色 {capability.expert_role_id}")
        if capability.expert_role_id not in known_persona_roles:
            errors.append(f"能力 {capability.id} 缺少 persona 实现 {capability.expert_role_id}")
        for dependency in capability.requires:
            if dependency not in CAPABILITIES:
                errors.append(f"能力 {capability.id} 依赖未注册能力 {dependency}")
        for binding in capability.data_bindings:
            data_capability = DATA_CAPABILITIES.get(binding.data_capability_id)
            if data_capability is None:
                errors.append(f"能力 {capability.id} 引用了未注册数据能力 {binding.data_capability_id}")
            elif data_capability.operator_id not in known_operator_ids:
                errors.append(f"数据能力 {data_capability.id} 缺少 Operator 实现 {data_capability.operator_id}")

    catalog_roles = {capability.expert_role_id for capability in CAPABILITIES.values()}
    for role_id in known_persona_roles - catalog_roles:
        errors.append(f"persona {role_id} 未被能力目录注册")

    for decision_type in DECISION_TYPES.values():
        for capability_id in decision_type.required_capabilities + decision_type.optional_capabilities:
            if capability_id not in CAPABILITIES:
                errors.append(f"决策类型 {decision_type.id} 引用了未注册能力 {capability_id}")
        for requirement in decision_type.profile_requirements:
            if requirement.field_id not in DECISION_PARAMETERS:
                errors.append(f"决策类型 {decision_type.id} 引用了未注册决策参数 {requirement.field_id}")

    return errors
