from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .decision_graph import DecisionGraph
    from .execution_plan import ExecutionPlan


@dataclass(frozen=True)
class PlanningIssue:
    """描述不可通过用户补充直接解决的规划校验问题。

    Args:
        code: 稳定的机器可读问题码，供 API 映射与测试断言。
        path: 出错字段在 Graph、目录或任务契约中的定位路径。
        message: 面向日志或未来协议层的可读问题描述。
        related_catalog_id: 关联的目录对象 ID；与目录无关时为 None。
    """

    code: str
    path: str
    message: str
    related_catalog_id: str | None = None


@dataclass(frozen=True)
class ClarificationRequest:
    """描述需要用户补充的已声明输入字段。

    Args:
        key: 需要补充的字段名。
        reason_code: 请求原因的机器可读代码。
        decision_type_id: 该字段所属的决策类型 ID。
        task_id: 被该字段阻塞的任务 ID；决策级澄清时为 None。
        accepted_value_shape: API/前端可展示的值形状提示。
        blocks_all_planning: True 表示该字段缺失时整份计划均不能生成。
    """

    key: str
    reason_code: str
    decision_type_id: str
    task_id: str | None
    accepted_value_shape: str | None
    blocks_all_planning: bool


@dataclass(frozen=True)
class ValidDecisionGraph:
    """封装已经通过目录校验、可进入编译阶段的业务图。

    Args:
        graph: 与当前能力目录版本和白名单一致的 DecisionGraph。
    """

    graph: DecisionGraph


@dataclass(frozen=True)
class Rejected:
    """表示规划因结构或目录错误而不能继续。

    Args:
        issues: 所有已发现且不可直接通过用户澄清解决的问题。
    """

    issues: tuple[PlanningIssue, ...]


@dataclass(frozen=True)
class NeedsClarification:
    """表示规划暂停，等待用户补充所列字段。

    Args:
        requests: 需要由用户或上层服务补充的结构化字段请求。
    """

    requests: tuple[ClarificationRequest, ...]


@dataclass(frozen=True)
class Planned:
    """表示已成功生成可由运行模块消费的执行计划。

    Args:
        plan: 已通过依赖、能力和输入绑定检查的 ExecutionPlan。
    """

    plan: ExecutionPlan


ValidationResult = ValidDecisionGraph | Rejected
PlanningOutcome = Planned | NeedsClarification | Rejected
