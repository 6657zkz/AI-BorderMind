# 当前实现状态

> 状态：`implemented` 的判断以当前代码和测试为证据。本文件不描述目标架构，不将路线图、目录骨架或测试 fixture 视为产品能力。

## 已验证范围

### 工程配置

- 后端位于 `backend/`。
- [backend/pyproject.toml](../backend/pyproject.toml) 要求 Python 3.11+，并配置 pytest 从 `backend/tests/` 发现测试。

### 能力目录

[backend/app/domain/capabilities/register.py](../backend/app/domain/capabilities/register.py) 已实现按类型组织的静态能力定义、构建期注册和冻结只读目录：

- `CapabilityRegistry`：显式注册实体、指标、Operator、专家角色、Evidence、任务契约和决策类型。
- `FrozenCapabilityCatalog`：实现 planning 所需的只读目录协议，目录版本为 `catalog-v1`。
- `promotion-response`：包含价格带、毛利边界和促销响应建议的完整静态契约组合。
- 注册阶段拒绝重复 ID 和无效跨定义引用；不执行 Operator、专家或外部 I/O。

定义按 `decision_types/`、`task_contracts/`、`operators/`、`experts/` 和 `evidence/` 分目录保存，统一由 `register.py` 显式装配。

### 能力目录契约

[backend/app/domain/capabilities/contracts.py](../backend/app/domain/capabilities/contracts.py) 已实现纯领域、只读的目录契约：

- `InputRequirement`：任务输入与是否可澄清。
- `OutputField`：任务结构化输出字段。
- `TaskContractDefinition`：任务目的、输入、依赖、允许能力/角色、输出与策略声明。
- `DecisionTypeDefinition`：决策类型的任务蓝图和允许范围。
- `CapabilityCatalog`：planning 读取目录元数据的协议。

### Evidence 纯领域模型

[backend/app/domain/evidence/](../backend/app/domain/evidence/) 已实现运行时 Evidence 的纯领域模型：

- `EvidenceEntry`：记录一次 Operator 结果的来源、结构化 payload、状态、时间、质量标记和稳定 payload digest，并提供深度不可变和快照恢复。
- `EvidencePackage`：按专家角色保存本次授权消费的 Entry ID 子集，不复制 Evidence payload；可使用调用方提供的 Entry 集合执行完整性校验。
- `EvidenceChain`：聚合一个 Run 的 Entry、Package 和 `derived_from` lineage，校验租户/Run/scope/目录版本隔离、唯一性和无环关系；增补操作返回新聚合。

该模块只实现无副作用领域对象、内在不变量和快照，不执行 Operator，不创建 AnalysisRun，不访问数据库或 LLM。

完整模块边界见 [contracts/evidence.md](contracts/evidence.md)。


[backend/app/domain/planning/](../backend/app/domain/planning/) 已实现无网络、无数据库、无框架依赖的规划逻辑：

- `DecisionGraph`、触发上下文、证据需求、实体比较关系及其快照恢复。
- 针对目录版本、决策类型、范围、约束、实体、指标、证据和比较关系的白名单校验。
- `ExecutionPlan`、`PlanNode`、`InputBinding` 及其快照恢复。
- 从决策类型任务蓝图编译计划，检查未知任务/能力、无效依赖、重复任务与依赖环。
- 稳定拓扑排序；无依赖节点可由未来运行器并行处理。
- 受控输入绑定：`graph.scope` → `graph.constraints` → `graph.context_snapshot` → 项目画像 → 直接依赖的已声明输出。
- 结构化结果：`Planned`、`NeedsClarification`、`Rejected`。

完整模块边界见 [contracts/planning.md](contracts/planning.md)。

### 测试证据

从 `backend/` 运行：

```bash
python -m pytest
```

当前共有 17 项测试，覆盖 planning 单元测试以及真实能力目录的注册、冻结和组合编译：

- Graph 校验、目录版本不匹配和未知引用拒绝。
- Graph/Plan 快照往返及深拷贝。
- 稳定 DAG 编译、并行 sibling 节点和上游输出绑定。
- 可澄清与不可澄清输入缺失。
- 未知 Operator 和依赖环拒绝。

## 明确未实现

以下均为 `planned`，不得视为当前功能：

- `CapabilityCatalog` 的动态管理和持久化注册表；测试中的 `InMemoryCatalog` 仅为 [planning fixture](../backend/tests/domain/planning/conftest.py)。
- 项目画像、会话、消息和受控识别。
- API、SSE、认证、应用服务和 `main.py`。
- AnalysisRun/NodeRun 状态机、DAG 调度、重试、恢复、取消和超时。
- 数据库、仓储、迁移、Evidence 持久化、Evidence 读取、租户隔离、权限和审计。
- Operator 执行实现、外部数据接入、专家 LLM/Playbook 执行和业务结论生成。
- 监控信号、复合事件、触发策略和去重/冷却。
- LLM、工作流、后台调度和部署适配器。
- 前端、`planning/text2sql/`、MetricQueryGraph 和任意自由 SQL。

## 解释规则

[architecture.md](architecture.md) 中的模块、目标目录、API 和状态机都是未来设计约束，不是当前文件清单或运行能力。实现任何新范围前，先检查 [roadmap.md](roadmap.md)、相关模块契约和 ADR。
