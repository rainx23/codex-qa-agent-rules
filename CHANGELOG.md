# 版本历史

本文档记录影响规则行为、目录结构、使用方式、脚本能力、校验结果或产物契约的版本变化。

版本号唯一来源为根目录 [RULE_VERSION](RULE_VERSION)。历史信息只能依据 Git diff、提交、tag、Release、已有版本文件或用户确认补充；无法确认时必须明确标记，不得编造。

## [Unreleased]

## [2.17.0] - 2026-07-23

### Added

- 新增 CodeBuddy 兼容入口 `CODEBUDDY.md`，引导 CodeBuddy 继续使用根目录 `AGENTS.md`、正式 QA Skills、规则和校验脚本。
- 新增 `.codebuddy/skills/` 原生 Skill 包装层，使 CodeBuddy 可以发现和路由现有 6 个 QA Skills。
- 新增 `.codebuddy/README.md`，明确适配层的目录定位、使用入口和维护约束。
- 新增 CodeBuddy 适配自动化测试，覆盖入口缺失、包装清单漂移、描述不一致和错误正式 Skill 引用。

### Changed

- CodeBuddy 包装 Skill 仅引用根目录正式 `skills/*/SKILL.md`，不复制规则正文，避免形成 Codex 与 CodeBuddy 两套规则。
- 现有 Codex 使用方式、QA 工作流、规则路径、Schema、脚本和测试产物结构保持不变。
- 仓库文档校验器新增 CodeBuddy 适配门禁，校验总入口、包装 Skill 清单、Frontmatter 描述和正式 Skill 引用一致性。
- 将当前 active 正式测试产物重新校验并同步到 RULE_VERSION 2.17.0；保留已被替代产物的原始历史版本。
- CodeBuddy 总入口改为通过 `@AGENTS.md` 显式导入正式全局规则，包装 Skill 改为使用 `${CODEBUDDY_SKILL_DIR}` 和 `@file` 加载根目录正式 Skill。
- 更新 Codex 与 CodeBuddy 使用示例，新增需求预审提示词，明确正式需求用例任务的一次授权、集中确认和阻塞解除后自动续跑机制。
- 更新 README FAQ，移除已不适用的独立排序测试说明，并补充测试维度按证据生成、用例去重、Diff 比较和日常/发布校验说明。

## [2.16.0] - 2026-07-23

### Removed

- 移除未使用的 OpenSpec 需求来源支持；当前正式历史产物未使用 `openspec`，无需迁移。
- 保留 Markdown、`pasted_text`、`requirement`、禅道、截图及其他既有来源，不修改正式 QA 工作流、Evidence 机制或历史 Git 提交。

## [2.15.0] - 2026-07-22

### Added

- 新增仅由明确需求预审意图触发的 `pre_review`，复用 Requirement Analysis/Evidence/Fact/Confirmation，并禁止生成或自动续跑正式测试产物。
- 新增 `qa-knowledge-management` 的显式 `extract_candidate` 模式、只提示一次的候选提取邀请以及 candidate-only Schema；默认任务不自动检索、提取或持久化知识。

### Changed

- 文档统一为“6 个 QA Skills / 4 个核心交付链 Skills”，仓库文档校验器从实际 `skills/*/SKILL.md` 派生清单并与根 README 比对。

### Fixed

- `extract_candidate` 独立复验 completed 正式模型、Confirmation Summary 与 resolved Confirmation 来源，提示上下文支持用户简短回复“提取”；混合“需求评审并生成用例”继续进入 delivery。
- 知识候选请求在正向匹配前识别“不要/无需/暂不/先不/别提取”等明确否定意图，候选提示上下文中的否定短回复不再误触发提取。

## [2.14.0] - 2026-07-22

### Added

- 新增“一次授权、两阶段执行、集中确认、确认后自动续跑”的 `confirmation_only` Requirement Checkpoint、批量 Confirmation 回复状态迁移和确定性聊天渲染器。
- 新增 `validate_task.py` 当前业务产物快速校验与 `validate_release.py` 规则发布全量校验入口。

### Changed

- 新任务发现 blocking 后停止 Risk/Testcase/XMind/Manifest 下游生成，但继续完整扫描剩余需求并一次性返回全部确认问题；历史 pending Manifest 和 passed 正式产物保持兼容。

### Fixed

- 自动续跑同时要求 blocking、核心跳过和未解决核心 Fact 计数归零，且更新后的 Requirement Analysis Model 校验通过；仅回答 Confirmation 而未同步核心 Fact 时继续停留在 `confirmation_only`。
- `confirmation_only` 重复渲染时只展开仍为 pending 的 Confirmation，并用已处理 ID 摘要代替 resolved/skipped 问题全文。

## [2.13.0] - 2026-07-22

### Added

- 新增八类 `test_dimension_assessment`、`condition_matrix_applicability`、`scope_dispositions` 与 Testcase `secondary_dimensions` 的兼容 Schema 和确定性交叉校验。
- 新增对话“测试维度覆盖”固定章节及维度完整性、范围排除证据、主辅维度和单主维度复核错误码。

### Changed

- 当前规则版本的 passed requirement/combined 正式用例产物无条件要求八类 `test_dimension_assessment`；旧版本历史、pending/failed 与无 Requirement 的纯 diff 产物继续兼容。

### Fixed

- Evidence `excerpt` 改为按物理行闭区间精确匹配，并补充 CRLF/LF、BOM、空行、偏移、越界和缺失快照回归。
- 分析报告新增 FACT/RISK/CONF 主摘要重复门禁，并禁止 passed 报告残留草稿 TC/用例措辞。
- 对话摘要测试运行目录迁移到系统临时目录，异常退出也不再向固定 Fixture 目录遗留随机文件夹。

## [2.12.0] - 2026-07-22

### Added

- 新增不少于 6 个同规则入口的全局 `shared_entry_scope` 模型、固定 XMind 范围树和模型/XMind 追踪校验。
- 新增多入口阈值、完整入口展开、简称拒绝及全局范围 TC 引用一致性回归测试。

### Changed

- 规则版本从 2.11.0 升级到 2.12.0；2 至 5 个入口继续逐入口写操作步骤和预期，不少于 6 个同规则入口改为全局适用入口范围加 TC 公共步骤。
- 模拟交易、正式交易等范围都必须逐项列出完整入口，禁止“上述入口”“同上”“等入口”、省略号或外部入口清单代替。

### Fixed

- 修复大量同规则入口重复复制步骤和预期导致用例树冗长，同时又可能因简称遗漏正式交易真实入口的问题。

## [2.11.0] - 2026-07-18

### Added

- 新增枚举条件矩阵、required/excluded combination、行为型 `condition_coverage` 与稳定错误码门禁。
- 新增不含纯入口名称的 `core_deduplication_key`，以及正式产物统一扫描校验入口。
- 新增统一对话交付契约、Confirmation 聊天摘要、文件名称与固定用途展示，以及 passed/pending/failed 三种回复模板。
- 新增确定性 `render_delivery_summary.py` 与 `validate_delivery_summary.py`，从 Manifest 和结构化模型读取路径、数量、版本和状态并校验摘要一致性。
- 新增 47 项对话摘要回归测试，覆盖当前清仓权限 passed Manifest、临时 pending/failed Fixture、跨平台路径和无 ANSI 输出。

### Changed

- 规则版本从 2.10.0 升级到 2.11.0；配置存在性与配置行为覆盖分离，多入口同规则 TC 强制合并为平级入口分支。
- 权限组合覆盖按关系、目标范围、命中状态和指定用户数据形态确定性校验；CI 不再硬编码单一业务产物目录。
- 三个 QA Skill 接入对话交付契约；产物校验后使用渲染器生成最终聊天回复主体，并分开显示 `validation_status` 与 `sql_status`。

### Fixed

- 修复 XMind 按主维度分组时把合法的全局连续 TC 集合误判为必须按树遍历顺序递增，以及权限/分页需求被机械归入单一主维度的问题。

- 修复模拟/正式入口名称进入唯一键导致等价 TC 被拆分，以及明确枚举只生成配置项存在性用例而遗漏真实行为组合的问题。
- 修复 required combinations 自身漏项无法发现、多个组合共用同一超长步骤以及模糊关系 Oracle 可通过的问题；增加分组笛卡尔积复算和 branch/step/expected 定位，并在关系证据不足时保持 pending。

## [2.10.0] - 2026-07-18

### Added

- 新增 Workbook 完整树无损复验、索引与合法 Manifest 强一致校验，以及 Ubuntu/Windows、Python 3.10/3.12 的产物治理兼容矩阵。
- 新增真正可计算的 Testcase Value Assessment 模型组和 Golden 输出，并在评分前校验全部引用模型与跨模型链接。

### Changed

- 规则版本从 2.9.0 升级到 2.10.0；Manifest 组合来源 Hash 统一使用文本换行/BOM 归一化、二进制原始字节和规范化相对路径。
- 正式 CI 接入当前真实 Manifest、模型、Workbook、index 及临时 Workbook 复验。

### Fixed

- 阻止结构或容量 Evidence 推导自动去重等额外业务行为，阻止模糊统计口径和无基线回归断言。
- 修复 `insufficient_inputs` 产生低价值或简化建议的问题。

## [2.9.0] - 2026-07-18

### Added

- 新增证据精确定位、Acceptance/Risk 派生证据、confirmed 链路和字段结构不能推导业务行为的通用校验与回归测试。
- 新增 `validate_testcase_index.py` 和 `verify_xmind.py` 正式入口，校验 passed Manifest 唯一登记及 XMind 无损转换。

### Changed

- 规则版本从 2.8.0 升级到 2.9.0；Manifest 的测试设计状态与 SQL 状态正式分离，允许完整产物使用 `passed + sql_status=blocked`。
- XMind 模糊断言扩展到“按已确认规则处理”等占位表达，并继续保持无硬长度门禁、无损语义精简和混合逻辑括号规则。

### Fixed

- 修复机械复用首行证据、无关 Risk/Acceptance 证据、字段存在越权扩写行为用例，以及 passed Manifest 漏登或重复登记仍可完成的问题。

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
