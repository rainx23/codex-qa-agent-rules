# 版本历史

本文档记录影响规则行为、目录结构、使用方式、脚本能力、校验结果或产物契约的版本变化。

版本号唯一来源为根目录 [RULE_VERSION](RULE_VERSION)。历史信息只能依据 Git diff、提交、tag、Release、已有版本文件或用户确认补充；无法确认时必须明确标记，不得编造。

## [Unreleased]

### Added

### Changed

### Fixed

## [2.8.0] - 2026-07-18

### Added

- 新增 blocking Confirmation 解除后的完整状态迁移与原始任务自动续跑契约，覆盖 Confirmation 证据、关联 Fact、风险、验收标准、Risk Matrix、Testcase Model 和正式产物链。
- 新增 XMind 无损语义精简规则与校验测试，允许明确的比较、集合、逻辑和状态迁移符号；拒绝截断标记，并提示未加括号的混合 AND/OR。

### Changed

- 规则版本从 2.7.0 升级到 2.8.0；需求、用例与产物 Skill 在 blocking 归零后自动完成原始任务，不要求用户重复发送继续指令。
- 完整交付明确要求 Requirement Analysis Model、Risk Coverage Matrix、Testcase Model、XMind Markdown、Workbook、Manifest 和索引全部通过正式复验。

### Fixed

- 修复只更新需求报告和 XMind Markdown、未同步 JSON 模型与正式产物的问题。
- 明确 XMind 不使用固定字符上限，不因节点较长失败或告警，也不自动改写用户文本。

## [2.7.0] - 2026-07-17

### Added

- 新增独立、可选的 Testcase Value Assessment Model、生成式 JSON Schema 和七维确定性评分能力。
- 新增 P0 Risk 与历史缺陷回归保护、持久化结果全字段重算校验，以及路径、模型 ID、归一化 Hash 和 TC 完整性校验。
- `validate_testcase_quality.py` 新增可选 `--value-assessment`，稳定输出 error、warning、suggestion 和评分摘要。

### Changed

- 规则版本从 2.6.0 升级到 2.7.0；测试用例设计与产物校验 Skill 增加可选 Assessment 职责边界。
- 阶段一 warning 和 suggestion 保持非阻塞；Assessment 不影响 XMind 层级、Manifest 计数、Testcase Model、Execution Model 或既有交付流程。

## [2.6.0] - 2026-07-17

### Added

- Evidence Reference 真实来源、路径、哈希、时间和状态门禁。
- Schema 2.0.0、Missing Fact blocking Confirmation、Pending 草稿产物契约和 Execution Instance 证据契约。
- DDL 完整消费检查、SQL Identifier 真实来源校验、Risk/Diff 双向一致性校验和 API 健康断言白名单。

### Changed

- 规则版本从 2.5.0 升级到 2.6.0；结构化模型 Schema 从 1.0.0 升级到 2.0.0。
- SQL author 继续唯一读取 `rules-repository.json.sql_defaults.author`，默认配置仍为 `Rainx`。

### Fixed

- 阻止不存在或失真的 Evidence、Missing Fact、Pending Workbook、DDL nullable 推断、虚假报告 ID 和执行证据绕过正式校验。

### Removed

## [2.5.0] - 2026-07-17

### Added

- 新增真实 Requirement、Diff、Risk、Testcase 模型联合校验器 `scripts/validate_models.py`。
- 新增结构化疑似缺陷、风险处置状态、SQL 标识证据、Testcase 执行辅助字段与 API 参数健康断言范围契约。
- 新增统一 Evidence Reference、可选 Testcase Execution Instance，以及来源文件哈希变化后的 stale/reconfirm 校验。
- 新增 `tests/fixtures/anti_hallucination/` 八类独立反幻觉夹具、Golden 结果和 CI 统一回归入口。

### Changed

- 阻塞待确认点强制保持 pending，未分类待确认点不再默认为 nonblocking。
- 收紧 confirmed Fact、DDL complete/partial、P0/P1/P2 覆盖、步骤预期、模糊断言和 SQL 路径规则。
- SQL author 改由 `rules-repository.json.sql_defaults.author` 配置，默认 `Rainx`。
- 调整禅道证据优先级和权限相关场景的默认判断。
- Diff Impact 的 `impact_chains`、`risks`、`suspected_defects` 全面强类型化，并增加引用 ID 的存在性与双向交叉校验。
- Testcase 独立维护分支数和执行实例数；执行实例不计入 `case_count`，无实际执行证据时仅允许 `not_run`。
- Complete DDL 增加主键、唯一键、Duplicate/Aggregate Key、分区、分桶、索引、Engine、Properties 的完整解析门禁。

### Fixed

- 修复 inference 可伪装 confirmed、DDL 解析警告仍标记 complete、阻塞问题仍可 passed、风险静默丢失和 SQL 顶层空映射绕过校验的问题。
- 明确 `content.code=0` 与 `content.msg=OK` 仅证明参数组合健康，不代表业务响应数据正确。
- integrated 仓库缺少 `sql_defaults.author` 时改为明确迁移失败，禁止旧姓名、系统用户名和静默回退。

## [2.4.0] - 2026-07-17

### Added

- 新增功能目录 README 治理规则与统一的版本历史文件。
- 新增 `scripts/validate_repository_docs.py`，校验目录 README、CHANGELOG 与 RULE_VERSION 的一致性。
- 新增对应单元测试，并将文档治理校验接入 CI 发布门禁。

### Changed

- 根 README 和 AGENTS 增加目录导航、文档影响判断及版本维护入口。
- Schema、Manifest 示例和相关 Golden 数据更新为规则版本 2.4.0。

## [2.3.0] - 2026-07-10

### Baseline

- 以可验证的 2.3.0 仓库状态作为版本历史基线。
- 更早版本的具体变更缺少可验证依据，待通过 Commit、tag、Release 或用户确认补充。
