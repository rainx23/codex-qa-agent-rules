---
name: qa-diff-impact-analysis
description: 用于分析 Git Diff、Commit、范围、分支、工作区变更、公共逻辑、调用链、接口、SQL、配置、迁移和测试覆盖，输出 QA 影响、风险与回归范围。适用于 Commit 分析、Diff 评审、变更影响和需求到实现的覆盖检查。Diff impact analysis, commit review, change impact, regression scope and requirement coverage.
---

# QA Diff 影响分析（QA Diff Impact Analysis）

将本 Skill 的根目录解析为当前 `SKILL.md` 向上两级的仓库根目录。

## 规则加载

1. 完整读取 `../../rules/core/evidence-rules.md`。
2. 完整读取 `../../rules/core/confirmation-gate.md`。
3. 完整读取 `../../rules/core/analysis-report-contract.md`。
4. 完整读取 `../../rules/core/traceability-rules.md`。
5. 完整读取 `../../rules/core/structured-model-contract.md`。
6. 读取与变更匹配的 `../../rules/profiles` 文件。
7. 已存在 Requirement Analysis Model 时继承它作为需求基线。

## 执行流程

1. 校验仓库、分支、工作区、暂存区、Commit 对象、父提交和精确对比表达式。
2. 单个 Commit 对比其第一个父提交；两个 Commit 或显式 `old..new`、`old...new` 按用户表达式执行。说明合并父提交、gray 单分支提测、浅克隆缺口和空 Diff。
3. 获取 name-status、stat 和相关补丁，区分业务变更与非业务变更、公共变更与本地变更。
4. 处理重命名、删除、二进制、锁文件、生成文件、纯格式变更、迁移、回填、Feature Flag、gray 配置、定时任务以及消息生产者/消费者。
5. 按以下顺序分析：接口契约、SQL 与数据定义、权限与安全、公共逻辑、状态流转、迁移、配置与灰度发布、页面核心逻辑、局部展示、文档。
6. 按符号、路由、SQL ID、配置键、消息主题和字段搜索直接及间接调用方，检查上下游兼容性与已有自动化测试。
7. 建立变更到业务的影响链，并生成符合 `../../rules/schemas/diff-impact.schema.json` 的 Diff Impact Model。存在 Requirement Analysis Model 时，以其基于事实的验收标准作为覆盖基线。
8. 没有需求基线时，输出纯 Diff 契约：对比范围、变更文件、核心改动、疑似风险、明确的疑似缺陷结论、测试点和回归范围；不强制要求追踪矩阵。
9. 有需求模型时，切换为联合契约，输出需求理解、Diff 理解、追踪矩阵、风险和具备完整双侧证据的疑似缺陷。

对于仅文档、注释、日志文案、格式、锁文件或无语义重命名变更，不生成业务测试用例。

## 接口自动化影响

接口变更必须识别 URL、HTTP method、Header、Body 类型、请求参数新增/删除/重命名/类型/默认值/必填性/单值多值、Groovy 分支、SQL 动态条件、参数绑定、分页和排序变化，并输出自动化 create/update/none/blocked、受影响参数/分支、现有覆盖和建议组合；证据不足标记 unknown，不凭名称补全。需要产物时交接给 `../qa-api-automation/SKILL.md`。
