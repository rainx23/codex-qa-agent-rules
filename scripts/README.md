# Scripts

仓库的离线生成、转换、索引与静态校验工具。

## 目录定位

脚本负责规则契约生成与校验，不连接数据库或执行用户业务 SQL。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `qa_contracts.py` | Schema 与 Manifest 的可执行契约源 | 是 |
| `generate_schemas.py` | 生成或检查 Schema | 是 |
| `validate_*.py` | 静态校验门禁 | 是 |

## 使用入口

- 发布前命令见 `docs/codex/rule-validation-checklist.md`。

## 维护约束

- 新增、删除或改变脚本命令、输入输出时，更新本 README、检查清单、CI 静态契约和测试。
- 生成脚本不得在校验模式中修改文件。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。
