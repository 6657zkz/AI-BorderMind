# Module Contract: evidence

## 状态与代码入口

- 状态：`implemented`（纯领域模型）
- 公开入口：[backend/app/domain/evidence/__init__.py](../../backend/app/domain/evidence/__init__.py)
- 实现目录：[backend/app/domain/evidence/](../../backend/app/domain/evidence/)
- 测试目录：[backend/tests/domain/evidence/](../../backend/tests/domain/evidence/)

该模块表达运行时证据记录、专家消费授权和 Run 级证据聚合。它不是 EvidenceDefinition 的静态能力目录；静态类型仍由 [capabilities](capabilities.md) 提供。

## 职责

1. 将一次 Operator 结果表示为不可变的 `EvidenceEntry`。
2. 记录产生 Entry 的 Operator 调用标识、契约版本和输入摘要。
3. 将结构化 JSON payload 深度冻结，并生成稳定的 SHA-256 payload digest。
4. 用只保存 Entry ID 的 `EvidencePackage` 表达一个专家角色本次被授权消费的证据子集。
5. 用 `EvidenceChain` 聚合一个 Run 的全部 Entry、Package 和 Entry 间 `derived_from` lineage。
6. 提供对象级快照恢复，并在恢复时重新验证结构、不变量和 payload 完整性。

## 非职责

本模块不负责：

- 执行 Operator、访问网络/文件/数据库或调用 LLM。
- 创建或管理 `AnalysisRun`、`NodeRun`、调度、重试、恢复或状态迁移。
- 持久化、Repository、查询、缓存、审计存储或数据源适配器。
- 根据当前时间执行过期清理或状态迁移。
- 根据能力目录决定 Operator 是否允许产生某种 Evidence。
- 决定专家授权策略、权限、脱敏、截断或 Prompt 内容。

## 公开接口

从 `app.domain.evidence` 导入：

| 对象 | 用途 |
| --- | --- |
| `EvidenceSource` | 一次 Operator 调用的来源快照。 |
| `EvidenceStatus` | `produced`、`verified`、`rejected` 三种受控 Entry 状态。 |
| `EvidenceEntry` | 一次 Operator 结果对应的不可变证据记录。 |
| `EvidencePackage` | 一个专家角色本次可消费的 Entry ID 集合和授权快照。 |
| `EvidenceRelation` | 两个 Entry 之间的来源关系。 |
| `EvidenceRelationType` | 当前唯一的 `derived_from` 关系类型。 |
| `EvidenceChain` | 一个 Run 的 Entry、Package 和 lineage 聚合。 |
| `EvidenceIssue` | 一个结构化校验问题。 |
| `EvidenceValidationError` | 领域对象不变量错误。 |
| `EvidenceSnapshotError` | 快照结构、版本或 digest 错误。 |

### Entry

```python
entry = EvidenceEntry(
    entry_id="entry-1",
    tenant_id="tenant-1",
    run_id="run-1",
    scope_id="scope-1",
    catalog_version="catalog-v1",
    evidence_type_id="market-price-band",
    source=source,
    payload={"p50": 42.5},
    status=EvidenceStatus.PRODUCED,
    observed_at=observed_at,
    recorded_at=recorded_at,
)
```

- `payload` 顶层必须是 JSON object；嵌套 object 转为只读 mapping，数组转为 tuple。
- `payload_digest` 由稳定 JSON 序列化后计算，不接受调用方指定。
- 所有标识和 `EvidenceSource` 字段必须是非空字符串；`input_digest` 必须是小写 SHA-256 十六进制字符串。
- 时间必须带时区并规范化为 UTC；`observed_at <= recorded_at`，`expires_at`（如有）必须晚于 `observed_at`。
- 只有状态为 `verified` 的 Entry 才能满足 Package 的消费校验。

### Package

```python
package = EvidencePackage(
    package_id="package-1",
    tenant_id="tenant-1",
    run_id="run-1",
    scope_id="scope-1",
    catalog_version="catalog-v1",
    expert_role_id="pricing-expert",
    entry_ids=("entry-1",),
    allowed_evidence_type_ids=frozenset({"market-price-band"}),
    required_evidence_type_ids=frozenset({"market-price-band"}),
    authorized_at=authorized_at,
    authorization_snapshot={"policy": "pricing-v1"},
)
package.validate_entries(entries)
```

`EvidencePackage` 只保存 Entry ID，不复制 Entry payload，也不查询 Chain、能力目录或数据库。`validate_entries()` 使用调用方提供的 Entry 集合，验证引用存在、租户/Run/scope/catalog 版本一致、Evidence 类型被允许、Entry 已验证、记录时间不晚于授权时间、授权时尚未过期，以及 required 类型完整。

`required_evidence_type_ids` 必须是 `allowed_evidence_type_ids` 的子集。Package 自身只保存本次授权快照；授权决策和专家角色是否应被安排由未来运行/应用层负责。

### Chain

```python
chain = EvidenceChain(
    chain_id="chain-1",
    tenant_id="tenant-1",
    run_id="run-1",
    scope_id="scope-1",
    catalog_version="catalog-v1",
    scope_snapshot={"market": "US"},
)
chain = chain.add_entry(entry)
chain = chain.add_package(package)
chain = chain.add_relation(
    EvidenceRelation(
        EvidenceRelationType.DERIVED_FROM,
        subject_entry_id="entry-2",
        object_entry_id="entry-1",
    )
)
```

Chain 保证：

- Entry ID、Package ID 和关系三元组在当前聚合内唯一。
- 同一专家角色在一个 Chain 中最多一个 Package。
- 所有 Entry 和 Package 的 tenant、run、scope、catalog version 必须与 Chain 一致。
- Package 引用的 Entry 必须存在并通过 Package 完整性校验。
- 关系端点必须存在，不允许自环、重复关系或 lineage 环。
- `add_entry()`、`add_package()`、`add_relation()` 均返回新 Chain，不修改原对象；并行分支和汇聚关系均可表达。

## 快照与回放

三个聚合对象及其嵌套对象均提供 `to_snapshot()` / `from_snapshot()`：

- Entry 使用 `evidence-entry-v1`，Source 使用 `evidence-source-v1`。
- Package 使用 `evidence-package-v1`，快照只保存 Entry ID。
- Chain 使用 `evidence-chain-v1`，每个 Entry 的 payload 只在 `entries` 中出现一次。
- 快照使用普通 dict/list、字符串状态和 UTC ISO-8601 时间，不泄漏 mapping proxy 或 tuple。
- Chain 的 Entry、Package、Relation 以稳定 ID/关系键排序；集合字段以稳定排序列表保存。
- 恢复会重新执行对象不变量；Entry 的 payload digest 不匹配时抛出 `EvidenceSnapshotError`，不会静默修复。
- 快照输出是独立副本；修改快照或输入快照不会改变领域对象。

结构错误、空标识、无效 JSON、时间顺序、上下文隔离、未知引用、重复对象、关系环和 digest 不匹配均通过 `EvidenceValidationError` 或其 `EvidenceSnapshotError` 子类报告，包含稳定 `code`、`path` 和可读 `message`。

## 依赖与副作用

允许依赖 Python 标准库以及 Evidence 自身的 `entry.py`、`package.py`。禁止依赖 capabilities 的具体目录对象、`FrozenCapabilityCatalog`、AnalysisRun/NodeRun、ORM、数据库、网络 Client、LLM、API 或基础设施适配器。模块不执行 I/O、不创建线程、不读取系统时间来改变证据状态。

运行时 `evidence_type_id` 只保存稳定字符串，与 capabilities 中的 `EvidenceDefinition.evidence_id` 通过值约定衔接，不建立反向代码依赖。

## 测试证据

- [test_entry.py](../../backend/tests/domain/evidence/test_entry.py)：Entry 来源、状态、JSON 约束、深度不可变、digest、时间和快照。
- [test_package.py](../../backend/tests/domain/evidence/test_package.py)：引用子集、授权集合、状态、时间、上下文和完整性校验。
- [test_chain.py](../../backend/tests/domain/evidence/test_chain.py)：不可变增补、聚合隔离、唯一性、Package 引用、并行/汇聚 lineage、环检测和快照。

从 `backend/` 运行：

```bash
python -m pytest tests/domain/evidence
python -m pytest
```

## 后续范围

Evidence 持久化权威来源、Repository、生命周期服务、读取策略、脱敏、截断、权限、审计和 AnalysisRun/NodeRun 集成仍为 `planned`，不由当前三个纯领域对象单独证明已经实现。

## 变更规则

修改公开字段、Entry 可消费状态、Package 引用/授权语义、Chain 隔离或 lineage 规则、快照 schema 或错误码时，必须同步更新本契约和测试。涉及持久化权威来源、公开 API、权限、脱敏、执行语义或 LLM/数据访问边界时，按 ADR 规则记录决定。
