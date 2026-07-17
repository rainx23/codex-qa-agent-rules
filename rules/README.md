# Rules

仓库的正式规则来源目录。

## 目录定位

按通用核心规则、业务 Profile 和生成 Schema 组织规则契约。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `core/` | 跨场景的正式规则 | 是 |
| `profiles/` | 业务场景专项规则 | 是 |
| `schemas/` | JSON Schema 契约 | 否，自动生成 |

## 使用入口

- 从 `AGENTS.md` 路由到 `core/` 或 `profiles/`；Schema 由 `scripts/generate_schemas.py` 生成和校验。

## 维护约束

- 改变规则职责或调用关系时更新受影响子目录 README、根 README 和测试。
- 不直接手工编辑 `schemas/` 下的生成文件。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。
