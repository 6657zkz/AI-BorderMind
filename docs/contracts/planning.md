# Module Contract: planning

## 状态与代码入口

- 状态：`implemented`
- 公开导出：[backend/app/domain/planning/__init__.py](../../backend/app/domain/planning/__init__.py)
- 实现目录：[backend/app/domain/planning/](../../backend/app/domain/planning/)
- 目录输入协议：[backend/app/domain/capabilities/contracts.py](../../backend/app/domain/capabilities/contracts.py)

该模块是确定性、无副作用的领域内核。它不代表完整的产品规划流程，更不代表 AnalysisRun 执行器已经实现。

## 职责

1. 表达一次请求或事件的不可执行业务语义：`DecisionGraph`。
2. 根据只读 `CapabilityCatalog` 验证 Graph 中的目录版本、决策类型、范围、约束、实体、指标、证据和比较关系。
3. 将已验证的 Graph、项目画像和目录任务蓝图编译为唯一可执行的 `ExecutionPlan` DAG。
4. 为每个节点建立受控输入来源，输出结构化成功、澄清或拒绝结果。
5. 为 Graph 和 Plan 提供深拷贝快照与恢复。

## 非职责

planning 不负责：

- HTTP、SSE、认证、DTO、应用服务、ORM 或数据库。
- LLM 调用、网络请求、文件读取、任意 SQL 或 `text2sql`。
- Operator 执行、专家调用、真实数据查询或业务结论生成。
- AnalysisRun/NodeRun 状态机、DAG 调度、重试、取消、超时、恢复或持久化。
- 提供真实 `CapabilityCatalog`；测试中的内存目录是 `test-only` fixture。

## 公开接口

从 `app.domain.planning` 导入：

| 对象 | 用途 |
| --- | --- |
| `TriggerContext` | 用户、事件或人工触发上下文。 |
| `EvidenceRequirement` | Graph 所需证据及可选关联指标。 |
| `Comparison` | 两个注册实体间的业务比较关系。 |
| `DecisionGraph` | 不可执行的业务语义图。 |
| `InputBinding` | PlanNode 输入的受控来源。 |
| `PlanNode` | DAG 中可由未来运行器调度的节点定义。 |
| `ExecutionPlan` | 唯一可执行 DAG 的不可变定义。 |
| `PlanningIssue` | 不可直接通过用户补充解决的结构化问题。 |
| `ClarificationRequest` | 需要补充的结构化输入字段。 |
| `ValidDecisionGraph` | 已通过目录校验的 Graph 包装。 |
| `Rejected` | 校验或编译失败的结果。 |
| `NeedsClarification` | 等待补充输入的结果。 |
| `Planned` | 成功编译执行计划的结果。 |
| `compile_execution_plan` | 规划模块的主编译入口。 |

### Graph 校验

```python
result = graph.validate(catalog)
```

输入为 `DecisionGraph` 和只读 `CapabilityCatalog`；返回 `ValidDecisionGraph | Rejected`。只有 `ValidDecisionGraph` 可以作为编译器输入。

### 计划编译

```python
outcome = compile_execution_plan(validated_graph, project_profile, catalog)
```

- `validated_graph`：`DecisionGraph.validate()` 的成功结果。
- `project_profile`：只读映射，可提供 Graph 未提供的项目级输入。
- `catalog`：提供决策类型、任务契约和能力白名单的只读目录。
- 返回：`Planned | NeedsClarification | Rejected`。

## 输入绑定与输出

每个任务输入只可按以下优先顺序绑定：

1. `DecisionGraph.scope`
2. `DecisionGraph.constraints`
3. `DecisionGraph.context_snapshot`
4. `project_profile`
5. **直接依赖**任务中已声明的输出字段

不存在隐式跨节点读取。计划节点仅引用选定决策类型蓝图中声明的任务，返回的 `Planned.plan.nodes` 是未来运行模块唯一应消费的任务图。

## 关键不变量

- Graph 的 `catalog_version` 必须与输入 catalog 的 `version` 相同。
- 决策类型必须注册且启用。
- 实体、指标、证据、比较关系、任务、Operator 和专家角色必须已注册且在对应决策/任务契约允许范围内。
- 任务依赖必须属于当前决策类型蓝图；任务不得重复；依赖图不得成环。
- 拓扑序稳定；没有依赖关系的节点可以由未来运行器并行处理。
- 缺失 `clarifiable=True` 的输入返回 `NeedsClarification`；缺失不可澄清输入返回 `Rejected`，不得猜测默认值。
- 模块不会执行节点或改变输入对象。

## 快照与回放

`DecisionGraph` 与 `ExecutionPlan` 均提供 `to_snapshot()` 和 `from_snapshot()`：

- 快照深拷贝可变映射，修改快照不影响原始领域对象。
- 成功计划的 ID 为 `{graph_id}:plan`。
- `ExecutionPlan` 记录 source graph ID、catalog version、项目画像副本、节点和稳定拓扑序。

## 依赖与副作用

允许依赖 Python 标准库和能力目录的只读契约；不得依赖 FastAPI、SQLAlchemy、HTTP/网络 Client、数据库、LLM、`analysis_runs` 或 `planning/text2sql`。模块不执行 I/O、不持有会话、不创建线程。

## 测试证据

- [test_decision_graph.py](../../backend/tests/domain/planning/test_decision_graph.py)：Graph 校验、未知引用、目录版本和快照。
- [test_compiler.py](../../backend/tests/domain/planning/test_compiler.py)：DAG、输入绑定、澄清、拒绝、未知 Operator、依赖环和计划快照。

从 `backend/` 运行：

```bash
python -m pytest
```

## 变更规则

变更公共导出、输入/输出、输入优先级、错误码、依赖约束、计划 ID 或快照语义时，必须更新本契约、相关测试和 [current-state.md](../current-state.md)。若变更会影响未来公开 API、执行语义、能力目录所有权、持久化或 LLM/数据边界，必须同时新增或更新 ADR。
