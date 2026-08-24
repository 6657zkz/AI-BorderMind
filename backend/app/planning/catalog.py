from __future__ import annotations

from dataclasses import dataclass

from .contracts import ClarificationNeed, DataRequirement


@dataclass(frozen=True)
class Capability:
    id: str
    requires: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    data_requirements: tuple[DataRequirement, ...] = ()


@dataclass(frozen=True)
class GoalBlueprint:
    id: str
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()
    profile_requirements: tuple[ClarificationNeed, ...] = ()


CAPABILITIES: dict[str, Capability] = {
    "demand_researcher": Capability(
        id="demand_researcher",
        produces=("demand_growth",),
        data_requirements=(DataRequirement(metric_id="demand_growth", min_sample_size=1, max_age_hours=168),),
    ),
    "competitive_analyst": Capability(
        id="competitive_analyst",
        produces=("competition_level",),
        data_requirements=(DataRequirement(metric_id="competition_level", min_sample_size=1, max_age_hours=168),),
    ),
    "feedback_analyst": Capability(
        id="feedback_analyst",
        produces=("negative_review_share",),
        data_requirements=(DataRequirement(metric_id="negative_review_share", min_sample_size=1, max_age_hours=720),),
    ),
    "price_band_analyst": Capability(
        id="price_band_analyst",
        produces=("price_band",),
        data_requirements=(DataRequirement(metric_id="price_band", min_sample_size=1, max_age_hours=168),),
    ),
    "cost_modeler": Capability(
        id="cost_modeler",
        produces=("cost_floor",),
        data_requirements=(DataRequirement(metric_id="cost_floor", min_sample_size=1, max_age_hours=168),),
    ),
    "competitor_benchmark": Capability(
        id="competitor_benchmark",
        produces=("competitor_benchmark",),
        data_requirements=(DataRequirement(metric_id="competitor_benchmark", min_sample_size=1, max_age_hours=168),),
    ),
    "selection_score": Capability(
        id="selection_score",
        requires=("demand_researcher", "competitive_analyst", "price_band_analyst", "feedback_analyst"),
        produces=("selection_recommendation",),
    ),
    "pricing_optimizer": Capability(
        id="pricing_optimizer",
        requires=("cost_modeler", "price_band_analyst", "competitor_benchmark"),
        produces=("pricing_recommendation",),
    ),
    "executive_expert": Capability(
        id="executive_expert",
        produces=("decision_summary",),
    ),
}

GOALS: dict[str, GoalBlueprint] = {
    "product_selection": GoalBlueprint(
        id="product_selection",
        required_capabilities=(
            "demand_researcher",
            "competitive_analyst",
            "price_band_analyst",
            "feedback_analyst",
            "selection_score",
        ),
    ),
    "pricing_strategy": GoalBlueprint(
        id="pricing_strategy",
        required_capabilities=(
            "cost_modeler",
            "price_band_analyst",
            "competitor_benchmark",
            "pricing_optimizer",
        ),
        profile_requirements=(
            ClarificationNeed(
                field_id="target_margin",
                question="你的目标毛利率是多少？",
                required_for=["pricing_optimizer"],
                options=["20%", "30%", "40%"],
            ),
        ),
    ),
}

KNOWN_METRICS = {
    "demand_growth",
    "competition_level",
    "negative_review_share",
    "price_band",
    "cost_floor",
    "target_margin",
}

KNOWN_ENTITIES = {"market", "category", "product", "competitor", "internal_sku", "supply_signal"}
