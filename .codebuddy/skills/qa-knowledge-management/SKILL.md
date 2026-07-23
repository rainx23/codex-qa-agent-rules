---
name: qa-knowledge-management
description: 用于检索、起草、比较、校验并在明确确认后持久化脱敏历史业务知识、DDL、逻辑、指标、数据验证决策和只读 SQL 计划；全程不连接数据库。Knowledge management, historical QA knowledge, DDL comparison, data validation and read-only SQL governance.
---

# CodeBuddy Skill 适配入口

完整读取并执行仓库根目录的正式 Skill：

skills/qa-knowledge-management/SKILL.md

上述文件是本 Skill 的唯一权威工作流正文。

## 执行约束

- 所有规则、脚本、Schema、测试和产物路径均以仓库根目录为基准。
- 不得将 .codebuddy/skills 解析为正式规则仓库根目录。
- 必须按正式 Skill 指定的顺序加载 rules/core 和命中的 rules/profiles。
- 不得在本包装文件中复制、改写或弱化正式 Skill 的规则。
- 不得绕过正式 Skill 中的证据、确认、追踪和产物校验门禁。
- AGENTS.md、正式 Skill 或核心规则与本文件冲突时，以前者为准。
