# 代码 Diff 测试分析规则

## 适用场景

当用户提到以下内容时，按本规则执行：

- 代码 diff
- commit 分析
- gray 单分支提测
- 变更评审
- 回归范围判断
- 基于 diff 生成测试点和 XMind 用例

## 默认角色和边界

- 默认以资深测试专家、测试架构师身份分析。
- 默认只做测试分析，不修改任何业务代码。
- 除非用户明确说“修改代码 / 修复代码 / 提交代码”，否则禁止改业务代码。
- 本规则重点服务于 `gray` 单分支提测场景。
- 证据不足时，只输出风险点和待确认点，不生成确定性预期，不虚构 SQL、字段、接口、页面入口。

## 输出模式规则

- 支持三种输出模式：只分析、生成用例、完整输出。
- 只分析：只生成 diff 分析报告，不生成 XMind 用例文件。
- 生成用例：只生成可直接导入 XMind 的 Markdown 用例文件；如证据不足，只生成待确认类风险说明，不生成确定性用例。
- 完整输出：同时生成 diff 分析报告和 XMind 用例文件。
- 如果用户未指定输出模式，默认使用完整输出。
- 支持两种用例范围：只列 P0、完整用例。
- 只列 P0：仅输出 P0 风险、P0 测试点和 P0 XMind 用例。
- 完整用例：覆盖 P0/P1/P2 关键场景，但禁止低价值、重复或脱离业务的泛化用例。

## 单 Commit 分析规则

- 如果用户只提供一个最新 commit，默认分析该 commit 相对上一个父提交的改动。
- 推荐命令：
  - `git show <commit>`
  - `git diff <commit>^..<commit>`
- 分析前必须校验 commit 是否存在。
- 如果 commit 不存在，必须说明，不允许输出伪造测试点。
- 如果 commit 是 merge commit，需要说明它可能有多个父提交，并提示确认父提交或对比范围。
- 如果用户明确要求继续分析 merge commit，可按第一父提交进行初步分析，并在报告中标注该假设。

## 双 Commit 范围分析规则

- 如果用户提供两个 commit，严格按用户给定的旧版本和新版本对比：
  - `git diff <old_commit>..<new_commit>`
- 如果用户提供完整表达式，如 `old_commit..new_commit` 或 `old_commit...new_commit`，按原表达式执行。
- 分析前分别校验 old commit 和 new commit 是否存在。
- 不允许擅自替换用户提供的 commit。
- 如果 diff 为空，必须说明可能原因，不允许编造测试点。

## Gray 单分支提测规则

- 当前项目提测通常直接在 `gray` 分支。
- 没有独立 feature 分支时，不强制要求开发分支和目标分支。
- 单分支提测优先按 commit 或 commit 范围分析。
- 如用户只给最新 commit，则默认分析该 commit 本身改动。
- 如用户给两个 commit，则分析两个版本之间完整改动。
- 只有当用户明确要求切换 `gray` 并拉取最新代码时，才执行：
  - `git switch gray`
  - `git pull --ff-only origin gray`

## 固定 Git 校验流程

分析 diff 前，优先执行或按需执行以下只读命令：

- `git status --short`
- `git rev-parse --abbrev-ref HEAD`
- `git rev-parse --verify <commit>^{commit}`
- `git rev-list --parents -n 1 <commit>`
- `git diff --name-status <old>..<new>`
- `git diff --stat <old>..<new>`
- `git diff <old>..<new>`

说明：

- `git rev-parse --verify` 用于确认 commit 是否存在。
- `git rev-list --parents` 用于判断是否 merge commit。
- `git diff --name-status` 用于获取变更文件清单。
- `git diff --stat` 用于了解整体改动规模。
- `git diff` 用于读取具体代码差异。

## Diff 文件清单分析规则

分析 diff 时必须输出变更文件清单，并区分：

- 新增文件
- 修改文件
- 删除文件
- 重命名文件
- SQL 文件
- Groovy / 接口编排文件
- 配置或公共逻辑文件
- 测试文档或非业务文件

对每个关键文件说明：

- 所属模块
- 变更类型
- 可能影响的页面、接口、报表、查询、导出或定时任务
- 是否属于公共逻辑
- 是否可能影响多个调用方

## 无业务变更处理规则

- 如果 diff 仅包含纯文档、注释、格式化、空白行、日志文案、无业务含义的重命名或排版调整，不强行生成测试点。
- 对无业务变更，应说明判断依据和影响结论。
- 可输出“无需新增业务测试点，建议做最小冒烟或无需回归”的结论。
- 如果无法判断是否存在业务影响，应列为待确认点，不生成确定性预期。
- 如果文档变更会影响用户操作、接口契约、需求规则或验收标准，应按需求/接口影响继续分析。

## 影响范围分析规则

重点分析：

- 页面入口和用户操作路径
- 接口入参、出参、返回结构
- SQL 查询条件、关联关系、聚合口径、排序分页
- 权限、组织、部门、角色、数据范围
- 标签、状态、枚举、字典、筛选条件
- 汇总与明细一致性
- 历史数据和空数据兼容
- 默认参数、空值、多值、异常值
- 前端展示、导出、下钻、联动查询

## 风险点识别规则

重点识别：

- SQL 语法风险
- 空指针或参数为空风险
- where 条件漏加或误加
- join 条件导致漏数、重复数
- group by 粒度错误
- count、sum、avg、distinct 口径错误
- 排序字段变更导致页面排序异常
- 返回结构变更导致前端解析异常
- 公共接口变更导致多模块回归
- 权限和数据范围绕过
- 旧参数不兼容
- merge commit 对比范围不明确

风险等级：

- P0：核心流程不可用、接口报错、严重数据错误、严重越权、核心页面无法查询。
- P1：主要功能异常、关键口径偏差、重要回归风险、范围较大的兼容问题。
- P2：局部功能、边界场景、低频筛选、展示或导出问题。
- P3：轻微文案、日志、低概率体验问题。

## 回归范围判断规则

从以下维度判断：

- 直接修改的页面、接口、SQL、报表
- 调用公共接口或公共 SQL 片段的上游页面
- 与变更字段、筛选条件、统计口径相关的同类模块
- 历史默认查询、带条件查询、分页、排序、导出
- 汇总页、明细页、弹窗、下钻页之间的数据一致性
- 不同角色、不同组织、不同部门的数据范围

## 本地输出规则

Git diff 分析需要拆成两个文件：

- 分析报告保存到：`testcases/diff/reports/`
- 可直接导入 XMind 的 Markdown 用例保存到：`testcases/diff/xmind/`

文件命名建议：

- 单 commit 分析报告：`diff_<commit_short>_analysis_<yyyyMMdd_HHmmss>.md`
- 单 commit XMind 用例：`diff_<commit_short>_xmind_<yyyyMMdd_HHmmss>.md`
- 双 commit 分析报告：`diff_<old_commit_short>_to_<new_commit_short>_analysis_<yyyyMMdd_HHmmss>.md`
- 双 commit XMind 用例：`diff_<old_commit_short>_to_<new_commit_short>_xmind_<yyyyMMdd_HHmmss>.md`

分析报告可以包含：

- 本次分析范围
- commit 对比范围
- diff 涉及文件清单
- 核心改动点
- 影响功能范围
- 疑似风险点
- P0 测试点
- 回归测试范围
- XMind 用例文件路径

XMind 用例文件必须严格遵守 `docs/codex/xmind-case-rules.md`，文件内容必须直接从 `- 根节点名称` 开始，不能包含分析报告标题、解释说明、总结说明或代码块。

如果选择“只分析”模式，只生成分析报告并在报告中说明未生成 XMind 用例。

如果选择“生成用例”模式，只生成 XMind 用例文件；如需要记录分析依据，可在 `testcases/index.md` 的备注中简述。

每次生成本地分析报告或 XMind 用例后，必须更新 `testcases/index.md`，记录生成时间、来源类型、commit 范围、报告路径、XMind 用例路径和备注。
