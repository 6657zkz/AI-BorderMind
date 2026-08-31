# Module Contract: capabilities

## 状态与代码入口

- 状态：`implemented`
- 公开入口：[backend/app/domain/capabilities/__init__.py](../../backend/app/domain/capabilities/__init__.py)
- 统一注册入口：[backend/app/domain/capabilities/register.py](../../backend/app/domain/capabilities/register.py)
- 定义目录：[backend/app/domain/capabilities/](../../backend/app/domain/capabilities/)

## 职责

1. 定义 planning 所需的实体、指标、Operator、专家角色和 Evidence 静态元数据。
2. 在构建期通过 `CapabilityRegistry` 收集各类型定义并检查重复 ID 与跨定义引用。
3. 通过 `build_capability_catalog()` 生成固定版本的 `FrozenCapabilityCatalog`。
4. 向 planning 提供只读 `CapabilityCatalog` 查询协议实现。

## 非职责

本模块不负责运行时动态注册、注销或替换能力，不执行 Operator、专家、LLM、网络请求、数据库访问、Evidence 持久化、触发策略或 AnalysisRun。

## 组织方式

能力按类型分目录；一个具体能力对应一个定义文件。定义文件只导出不可变定义对象或无副作用构建函数。所有装配集中在 `register.py`，通过显式 `registry.register_xxx(...)` 注册；不自动扫描目录，不由定义文件修改全局注册器。

## 生命周期与版本

`CapabilityRegistry` 仅用于构建期，`freeze()` 后得到 `FrozenCapabilityCatalog`。冻结目录不暴露注册方法，内部索引不可变，构建器后续修改不影响已生成目录。总入口当前使用显式版本 `catalog-v1`；任何改变目录语义的变更都应升级版本。

## 测试证据

- [test_register.py](../../backend/tests/domain/capabilities/test_register.py)：默认目录、重复注册、冻结隔离、跨引用校验和只读边界。
- [test_real_catalog.py](../../backend/tests/domain/planning/test_real_catalog.py)：真实 `promotion-response` 目录与 planning 编译器组合。

从 `backend/` 运行：

```bash
python -m pytest
```

## 变更规则

新增或修改定义模型、注册方法、冻结语义、目录版本或公开查询接口时，必须同步更新本契约和测试。新增触发策略、持久化目录所有权、公开 API 或执行语义时，先按 ADR 规则记录决定。
