from __future__ import annotations

from app.domain.capabilities.contracts import CapabilityCatalog

from .decision_graph import DecisionGraph
from .outcomes import PlanningIssue, Rejected, ValidDecisionGraph, ValidationResult


def validate_decision_graph(graph: DecisionGraph, catalog: CapabilityCatalog) -> ValidationResult:
    """校验 DecisionGraph 的目录版本、白名单引用和决策类型允许范围。

    Args:
        graph: 待校验的业务语义图；该函数不会修改它。
        catalog: 提供已注册对象和版本信息的只读能力目录。

    Returns:
        所有校验通过时返回 ValidDecisionGraph；否则返回按检查顺序收集问题的 Rejected。
    """
    # 收集全部问题，避免调用方修复一个错误后才发现下一个错误。
    issues: list[PlanningIssue] = []

    if graph.catalog_version != catalog.version:
        issues.append(
            PlanningIssue(
                code="catalog_version_mismatch",
                path="catalog_version",
                message="DecisionGraph catalog version does not match the supplied catalog.",
                related_catalog_id=catalog.version,
            )
        )

    # 决策类型决定 Graph 允许出现哪些上下文、证据和比较关系。
    decision_type = catalog.get_decision_type(graph.decision_type_id)
    if decision_type is None:
        issues.append(
            PlanningIssue(
                code="unknown_decision_type",
                path="decision_type_id",
                message="DecisionGraph references an unregistered decision type.",
                related_catalog_id=graph.decision_type_id,
            )
        )
        return Rejected(tuple(issues))

    if not decision_type.enabled:
        issues.append(
            PlanningIssue(
                code="disabled_decision_type",
                path="decision_type_id",
                message="DecisionGraph references a disabled decision type.",
                related_catalog_id=graph.decision_type_id,
            )
        )

    # 允许范围由必需和可选上下文字段的并集构成。
    allowed_context_keys = decision_type.required_context_keys | decision_type.optional_context_keys
    for key in sorted(graph.scope):
        if key not in allowed_context_keys:
            issues.append(
                PlanningIssue(
                    code="disallowed_scope_key",
                    path=f"scope.{key}",
                    message="Scope key is not allowed by the selected decision type.",
                    related_catalog_id=key,
                )
            )

    for key in sorted(graph.constraints):
        if key not in decision_type.allowed_constraint_keys:
            issues.append(
                PlanningIssue(
                    code="disallowed_constraint_key",
                    path=f"constraints.{key}",
                    message="Constraint key is not allowed by the selected decision type.",
                    related_catalog_id=key,
                )
            )

    for entity_id in sorted(graph.entity_references):
        if not catalog.has_entity(entity_id):
            issues.append(
                PlanningIssue(
                    code="unknown_entity",
                    path="entity_references",
                    message="DecisionGraph references an unregistered entity.",
                    related_catalog_id=entity_id,
                )
            )

    for metric_id in sorted(graph.metric_references):
        if not catalog.has_metric(metric_id):
            issues.append(
                PlanningIssue(
                    code="unknown_metric",
                    path="metric_references",
                    message="DecisionGraph references an unregistered metric.",
                    related_catalog_id=metric_id,
                )
            )

    for index, requirement in enumerate(graph.required_evidence):
        if not catalog.has_evidence(requirement.evidence_id):
            issues.append(
                PlanningIssue(
                    code="unknown_evidence",
                    path=f"required_evidence[{index}].evidence_id",
                    message="DecisionGraph references unregistered evidence.",
                    related_catalog_id=requirement.evidence_id,
                )
            )
        elif requirement.evidence_id not in decision_type.allowed_evidence_ids:
            issues.append(
                PlanningIssue(
                    code="disallowed_evidence",
                    path=f"required_evidence[{index}].evidence_id",
                    message="Evidence is not allowed by the selected decision type.",
                    related_catalog_id=requirement.evidence_id,
                )
            )
        if requirement.metric_id is not None and not catalog.has_metric(requirement.metric_id):
            issues.append(
                PlanningIssue(
                    code="unknown_evidence_metric",
                    path=f"required_evidence[{index}].metric_id",
                    message="Evidence requirement references an unregistered metric.",
                    related_catalog_id=requirement.metric_id,
                )
            )

    for index, comparison in enumerate(graph.comparisons):
        if comparison.kind not in decision_type.allowed_comparison_kinds:
            issues.append(
                PlanningIssue(
                    code="disallowed_comparison_kind",
                    path=f"comparisons[{index}].kind",
                    message="Comparison kind is not allowed by the selected decision type.",
                    related_catalog_id=comparison.kind,
                )
            )
        for side, entity_id in (("left_entity_id", comparison.left_entity_id), ("right_entity_id", comparison.right_entity_id)):
            if not catalog.has_entity(entity_id):
                issues.append(
                    PlanningIssue(
                        code="unknown_comparison_entity",
                        path=f"comparisons[{index}].{side}",
                        message="Comparison references an unregistered entity.",
                        related_catalog_id=entity_id,
                    )
                )

    return Rejected(tuple(issues)) if issues else ValidDecisionGraph(graph)
