---
name: qa-diff-impact-analysis
description: 用于分析 Git Diff、Commit、范围、分支、工作区变更、公共逻辑、调用链、接口、SQL、配置、迁移和测试覆盖，输出 QA 影响、风险与回归范围。适用于 Commit 分析、Diff 评审、变更影响和需求到实现的覆盖检查。Diff impact analysis, commit review, change impact, regression scope and requirement coverage.
---

# CodeBuddy Skill 适配入口

完整读取并执行仓库根目录的正式 Skill：

skills/qa-diff-impact-analysis/SKILL.md

上述文件是本 Skill 的唯一权威工作流正文。

## 执行约束

- 所有规则、脚本、Schema、测试和产物路径均以仓库根目录为基准。
- 不得将 .codebuddy/skills 解析为正式规则仓库根目录。
- 必须按正式 Skill 指定的顺序加载 rules/core 和命中的 rules/profiles。
- 不得在本包装文件中复制、改写或弱化正式 Skill 的规则。
- 不得绕过正式 Skill 中的证据、确认、追踪和产物校验门禁。
- AGENTS.md、正式 Skill 或核心规则与本文件冲突时，以前者为准。
