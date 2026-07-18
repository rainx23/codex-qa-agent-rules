# Testcases

可追踪、可版本化的测试分析产物和 Manifest 示例。

## 目录定位

保存测试报告、XMind、索引和 Manifest；历史产物不得被新产物覆盖。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `manifest.example.json` | Manifest 格式示例 | 是 |
| `index.md` | 产物索引 | 是，由脚本更新 |
| `diff/`、`zentao/` | 按来源分类的产物 | 是 |

## 使用入口

- 使用 `scripts/build_testcase_index.py` 更新索引，并用 `scripts/validate_formal_artifacts.py` 扫描校验全部 passed 正式产物。

## 维护约束

- 不为 `reports/`、`xmind/` 等产物叶子目录添加 README。
- 新产物、索引或 Manifest 契约变更时更新本 README 和相关规则；禁止覆盖历史文件。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。
