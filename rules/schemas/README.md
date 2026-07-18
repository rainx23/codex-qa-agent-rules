# Schema 契约

由可执行契约源码生成的 JSON Schema 文件。

## 目录定位

提供结构化模型和 Manifest 的机器可读校验契约。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `*.schema.json` | 结构化模型 Schema | 否，自动生成 |
| `testcase-value-assessment.schema.json` | 独立、可选的 Testcase Value Assessment Model 契约 | 否，由 `scripts/qa_contracts.py` 统一生成 |

## 使用入口

- 运行 `python scripts/generate_schemas.py --check` 检查生成漂移。
- 运行 `python scripts/validate_schemas.py` 校验 Schema 内容。

## 维护约束

- Schema 是自动生成文件，禁止手工编辑；应修改 `scripts/qa_contracts.py` 后重新生成。
- Testcase Value Assessment Model 不写入 Testcase Model、XMind 或 Manifest，也不是旧产物的必填项。
- 改动契约必须同步更新测试、Manifest 示例、CHANGELOG 和 RULE_VERSION。

版本与完整变更历史统一见 [CHANGELOG.md](../../CHANGELOG.md)。
