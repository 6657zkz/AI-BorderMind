# 文档索引

本文档目录将当前事实、长期架构、开发顺序、模块契约和架构决定分开维护。不得从未提交代码、旧 Demo 路由、目标目录树、测试 fixture 或日期草稿推断已交付能力。

## 权威层级

1. **代码和测试**：当前已实现能力的最终证据。
2. **[current-state.md](current-state.md)**：当前提交中经代码和测试验证的能力与非能力。
3. **[contracts/](contracts/README.md)**：已实现模块的职责、稳定接口和依赖边界。
4. **[architecture.md](architecture.md)**：目标系统、领域契约、依赖方向和安全约束。
5. **[roadmap.md](roadmap.md)**：唯一的阶段顺序、范围和验收门槛。
6. **[adr/](adr/README.md)**：已接受的不可逆边界决定。

当前代码与目标架构不一致时，视为目标尚未落地或当前偏差，不得把任一方自动当作另一方的实现证明。

## 文档职责

| 文档 | 受众 | 负责内容 |
| --- | --- | --- |
| [../README.md](../README.md) | 使用者、开发者、Agent | 项目入口、当前公共范围、验证命令和简要限制 |
| [current-state.md](current-state.md) | 开发者、评审、Agent | 当前代码和测试已验证的能力与非能力 |
| [architecture.md](architecture.md) | 架构维护者、Agent | 目标系统、领域契约、依赖方向和安全约束 |
| [roadmap.md](roadmap.md) | 产品、开发者、Agent | 唯一的阶段顺序、范围和验收门槛 |
| [contracts/](contracts/README.md) | 模块消费者、开发者、Agent | 已实现模块的职责、公开接口、依赖与非职责 |
| [adr/](adr/README.md) | 架构维护者 | 已接受的不可逆架构决定 |
| [../CLAUDE.md](../CLAUDE.md) | 编码 Agent | 必读顺序、工作协议与状态区分规则 |

## 更新原则

- 只有代码和测试都存在的能力才能写入 `current-state.md` 和标记为 `implemented`。
- 新模块先由 roadmap 确认阶段；实现后再创建模块契约文档。
- 接口或模块边界变化更新模块契约；不可逆架构决定更新 ADR。
- 不为尚未存在的模块创建详细伪契约；在 architecture/roadmap 中标为 `planned` 即可。
