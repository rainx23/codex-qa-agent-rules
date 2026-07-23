---
name: qa-artifact-validation
description: 用于校验 QA 分析报告、XMind Markdown、XMind Workbook、Manifest、索引、镜像规则树和发布就绪状态。适用于校验、转换、发布、索引及 QA 规则或测试用例产物的最终验收。Artifact validation, XMind validation, manifest, index, workbook conversion and release readiness.
---

# CodeBuddy Skill 适配入口

完整读取并执行仓库根目录的正式 Skill：

@${CODEBUDDY_SKILL_DIR}/../../../skills/qa-artifact-validation/SKILL.md

上述文件是本 Skill 的唯一权威工作流正文。

## 执行约束

- 所有规则、脚本、Schema、测试和产物路径均以仓库根目录为基准。
- 不得将 .codebuddy/skills 解析为正式规则仓库根目录。
- 必须按正式 Skill 指定的顺序加载 rules/core 和命中的 rules/profiles。
- 不得在本包装文件中复制、改写或弱化正式 Skill 的规则。
- 不得绕过正式 Skill 中的证据、确认、追踪和产物校验门禁。
- AGENTS.md、正式 Skill 或核心规则与本文件冲突时，以前者为准。
