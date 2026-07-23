---
name: qa-testcase-design
description: 用于基于证据设计 QA 测试点和最小有效 XMind Markdown 用例集，应用风险覆盖、等价类、边界、决策表、状态流转、去重和固定层级。适用于测试点、测试用例、P0 用例、XMind Markdown 或完整 QA 产物生成。Testcase design, test points, P0 cases, XMind Markdown, risk coverage and deduplication.
---

# CodeBuddy Skill 适配入口

完整读取并执行仓库根目录的正式 Skill：

skills/qa-testcase-design/SKILL.md

上述文件是本 Skill 的唯一权威工作流正文。

## 执行约束

- 所有规则、脚本、Schema、测试和产物路径均以仓库根目录为基准。
- 不得将 .codebuddy/skills 解析为正式规则仓库根目录。
- 必须按正式 Skill 指定的顺序加载 rules/core 和命中的 rules/profiles。
- 不得在本包装文件中复制、改写或弱化正式 Skill 的规则。
- 不得绕过正式 Skill 中的证据、确认、追踪和产物校验门禁。
- AGENTS.md、正式 Skill 或核心规则与本文件冲突时，以前者为准。
