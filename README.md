# AI-BorderMind

AI-BorderMind 是一个面向跨境经营决策的受控分析系统。当前工作区实现了后端的**纯规划领域内核和静态能力目录**，不是可部署的完整产品，也没有可用的 HTTP 服务或前端。

## 当前可验证能力

- 能力目录的只读协议、构建期注册器、冻结目录及 `promotion-response` 静态定义组合。
- `DecisionGraph` 的白名单校验和可回放快照。
- `ExecutionPlan` 的确定性 DAG 编译、输入绑定、依赖环检测和快照。
- `EvidenceEntry`、`EvidencePackage` 和 `EvidenceChain` 的纯领域模型、引用完整性、Run 边界隔离、lineage 校验及快照恢复。

在 `backend/` 中验证：

```bash
python -m pytest
```

## 当前未实现

真实能力目录的动态管理、应用服务、HTTP/SSE、数据库、AnalysisRun 调度与恢复、Operator 执行、证据持久化与读取、Evidence 生命周期服务、LLM、监控和前端均尚未实现。当前 Evidence 模块只提供纯领域模型，不代表证据已经由真实 Operator 产生或持久化；测试中的内存目录仅为 fixture，不是产品注册表。

## 文档入口

- [文档索引](docs/README.md)
- [当前实现状态](docs/current-state.md)
- [目标架构](docs/architecture.md)
- [研发路线图](docs/roadmap.md)
- [模块契约](docs/contracts/README.md)
- [架构决策记录](docs/adr/README.md)
- [Agent 工作协议](CLAUDE.md)

> 不得从目标架构、目标目录树、Demo、旧代码、测试 fixture 或文档示例推断某项产品能力已经实现；实现状态必须以代码和测试为准。
