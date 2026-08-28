# Architecture Decision Records

ADR 记录影响长期兼容性、所有权或安全边界的架构决定。它们约束未来实现，但不会单独证明功能已经实现；当前事实仍以 [../current-state.md](../current-state.md) 和代码/测试为准。

## 状态

- `Proposed`：待讨论，不能作为约束。
- `Accepted`：已接受，后续设计和实现必须遵守。
- `Superseded`：已被后续 ADR 替代。
- `Rejected`：已明确不采用。

## 命名与模板

文件使用 `ADR-NNNN-short-name.md`。每份 ADR 应包含：标题、状态、日期、背景、决策、影响、替代关系、相关代码和文档。

## 何时需要 ADR

以下不可逆变更必须记录 ADR：持久化权威来源、公开 API、能力目录所有权、执行语义、租户/权限模型、LLM 或数据访问边界，以及旧领域/API 名称的退役或兼容策略。

普通函数拆分、局部数据结构、测试组织和可逆实现细节不需要 ADR。

## 索引

- [ADR-0001：AnalysisRun 命名与旧研究执行链退役](ADR-0001-analysis-run-naming.md) — `Accepted`，目标命名和兼容边界。
