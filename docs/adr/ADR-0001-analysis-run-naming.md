# ADR-0001：AnalysisRun 命名与旧研究执行链退役

- 状态：Accepted
- 日期：2026-08-28

## 背景

目标架构需要一个可恢复、可审计、由 `DecisionGraph` 和 `ExecutionPlan` 驱动的分析运行记录。旧的 `research_runs`、`research_service` 和固定品类进入 DTO 名称会把未来执行链限制为 Demo 式研究流程，并与领域中立的决策运行模型冲突。

当前工作区尚未实现 API、服务或运行器；本 ADR 仅记录未来实现必须遵守的命名和兼容约束，不作为任何模块已经落地的证明。

## 决策

- `analysis_runs` 是未来运行领域和 API 的规范名称。
- `AnalysisRunService` 是未来应用层的规范服务名称。
- `research_runs`、`research_service` 和固定品类进入 DTO 退役，不得作为新实现或并行执行链恢复。
- 如未来存在真实的旧外部 HTTP 协议兼容需求，兼容层仅可位于 `api/chat_compat.py`，并必须转换到同一个 `AnalysisRunService` 和执行链。
- 兼容层不得维护独立的计划、状态机、任务依赖或 Operator 调用路径。

## 影响

- 后续路线图中创建运行模块时使用 `domain/analysis_runs/`、`api/analysis_runs.py` 和 `service/analysis_run_service.py`。
- 任何旧名称仅可在已确认的协议适配层中出现，且需要对应测试证明转换语义。
- `planning` 的现有 `ExecutionPlan` 将被未来 AnalysisRun 运行器消费，但当前没有运行器。

## 相关文档

- [目标架构](../architecture.md)
- [路线图](../roadmap.md)
- [当前实现状态](../current-state.md)
