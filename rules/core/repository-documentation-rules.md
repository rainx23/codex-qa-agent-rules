# 仓库目录与版本历史治理规则

本文件是目录 README、CHANGELOG 和版本升级判断的唯一正式规则来源。

## README 适用范围

- 根 README 是仓库总入口；一级功能目录必须有 README：`skills`、`rules`、`scripts`、`tests`、`testcases`、`docs/codex`、`qa-knowledge`。
- 复杂的二级功能目录必须有 README：`rules/core`、`rules/profiles`、`rules/schemas`。
- 每个 README 至少说明目录定位、主要内容、使用入口、维护约束，以及是否含自动生成文件。
- README 不为每个具体 Skill、纯 Fixture 叶子目录、缓存、临时目录、Golden 输出或自动生成目录重复建立入口文件。

## README 更新触发条件

新增、删除或重命名文件/目录，变更目录职责、主要入口、命令、输入输出、生成边界、调用关系、发布前校验或维护注意事项时，必须更新受影响目录 README；新增一级功能目录时必须新增 README。仅更新实际受影响的目录 README 和根 README。

## 版本与 CHANGELOG

- `RULE_VERSION` 是唯一机器版本来源；脚本、Schema、Manifest、README 和其他文件不得维护独立版本号。
- `CHANGELOG.md` 是唯一完整版本历史。目录 README 只能链接它，不能复制完整历史。
- CHANGELOG 必须包含当前 RULE_VERSION 的唯一正式章节；版本格式为 `major.minor.patch`，正式版本日期为 `yyyy-mm-dd`，版本从新到旧排列。
- 历史内容只能来自 Git diff、Commit、tag、GitHub Release、已有版本文件或用户明确确认。证据不足时写明“历史信息不足”或“待补充”，不得根据当前文件状态编造历史版本。

## 版本升级

- Major：不兼容地删除、替换或重命名外部入口，改变核心规则优先级、XMind 层级、Schema/Manifest 或目录结构，或使现有接入方式失效。
- Minor：新增兼容的 Skill、Profile、核心规则、校验脚本、产物能力、目录/版本治理能力或可选 Schema 字段。
- Patch：修复规则判断、脚本、校验遗漏、路径、计数、编码、转换或其他保持兼容的行为问题。

## 小内容修改豁免

只有同时不改变规则行为、使用方式、目录职责、文件入口、命令参数、输入输出、Schema/Manifest、测试结果和 CI/发布门禁，且现有 README 仍准确时，错别字、标点、排版、等义措辞、普通注释和非关键示例文案可不更新 RULE_VERSION、CHANGELOG 或 README。判断依据是行为与使用影响，不是改动行数。

## 完成前门禁

修改规则、Skill、脚本、测试、目录、README、版本或发布内容前，必须先按本规则判断文档与版本影响；需要更新 README、CHANGELOG 或 RULE_VERSION 时不得遗漏。发布前必须运行 `scripts/validate_repository_docs.py`，失败即阻止发布。
