# Agent 工作协议

## 工作前必读顺序

开始设计、实现、审查或回答“当前系统有什么能力”前，按以下顺序阅读：

1. [README.md](README.md)
2. [docs/current-state.md](docs/current-state.md)
3. 与任务相关的 [docs/contracts/](docs/contracts/README.md)
4. [docs/roadmap.md](docs/roadmap.md)
5. [docs/architecture.md](docs/architecture.md) 和相关 [ADR](docs/adr/README.md)
6. 相关代码与测试

模块契约用于快速理解边界；字段级类型、真实行为和当前可用性必须由代码与测试验证。

## 文档权威与状态区分

- **代码和测试**是已实现能力的最终证据。
- `docs/current-state.md` 是当前事实的摘要；若与代码或测试冲突，修正文档，不得假设代码已实现目标设计。
- `docs/contracts/` 描述已实现模块的稳定职责与消费边界；不替代代码的精确字段定义。
- `docs/architecture.md` 仅描述目标架构与长期约束，不能作为当前功能清单。
- `docs/roadmap.md` 是研发顺序与阶段门槛的唯一来源；计划不得写成已实现。
- 已接受的 ADR 约束未来实现，但不会单独证明对应功能已经落地。

所有说明都必须明确区分：

- `implemented`：有对应代码和测试证据。
- `planned`：只存在于架构或路线图中。
- `retired`：不得恢复的旧概念或接口。
- `test-only`：仅用于测试的对象，例如 `InMemoryCatalog` fixture。

不得从目标目录树、旧 Demo、旧路由、注释、架构示例、测试 fixture 或未提交文件推断产品能力已经存在。

## 变更规则

- 新增模块前，确认其属于当前 roadmap 阶段；不要为了凑目录预建空模块。
- 修改已实现模块的公开接口、职责、依赖边界或失败语义时，同步更新对应模块契约和测试。
- 已验证能力或未实现范围改变时，同步更新 `docs/current-state.md`。
- 阶段顺序、范围或验收门槛改变时，同步更新 `docs/roadmap.md`。
- 涉及持久化权威来源、公开 API、能力目录所有权、执行语义、租户/权限、LLM 或数据访问边界的不可逆决定，先新增或更新 ADR。
- 不在 README、current state、architecture、roadmap 和模块契约中复制完整字段清单；使用链接并保持单一职责。
- 每完成一个模块，先运行该模块的测试，再在本地创建一次新提交，并将提交推送到 GitHub 的 `demo-dev` 分支。
- 推送前只提交源代码、测试和必要文档；不得提交 `.env`、凭据、缓存、`__pycache__`、`.pyc` 或本地 Claude 配置。
- `demo-dev` 是当前开发分支；不得使用强制推送，不得修改 `main` 或 `demo`，除非用户明确要求。

## 当前 planning 特别约束

- `DecisionGraph` 是业务语义输入，不是任务清单或工作流。
- `ExecutionPlan` 是唯一可执行 DAG 的编译结果；当前仅实现了其数据模型和编译器。
- `CapabilityCatalog` 是只读协议；当前不存在真实产品能力目录。
- 当前不存在 Run/NodeRun 状态机、调度器、Operator 执行、数据库、API、LLM 或前端。新增这些能力前先检查 roadmap、模块契约和 ADR 要求。
