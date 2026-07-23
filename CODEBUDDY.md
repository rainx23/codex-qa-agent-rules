# CodeBuddy QA 测试分析总入口

@AGENTS.md

## 唯一权威规则入口

开始任何任务前，必须完整读取仓库根目录的 `AGENTS.md`。

`AGENTS.md` 是本仓库角色边界、任务路由、规则优先级、输出模式和全局门禁的唯一权威入口。本文件仅用于 CodeBuddy 适配，不复制、不改写、不弱化正式 QA 规则。

## 任务执行

1. 根据 `AGENTS.md` 判断当前任务类型和执行边界。
2. 按 `AGENTS.md` 的任务路由读取仓库根目录 `skills/` 下对应的 `SKILL.md`。
3. 按原 Skill 指定顺序读取 `rules/core/` 和命中的 `rules/profiles/`。
4. 所有规则、脚本、Schema、测试和产物路径均以仓库根目录为基准。
5. 执行脚本时继续使用仓库根目录的 `scripts/`，不得在 `.codebuddy/` 下复制脚本、Schema 或正式规则。
6. CodeBuddy 包装 Skill 与原始 Skill 冲突时，始终以根目录 `AGENTS.md`、`skills/` 和 `rules/` 为准。

## CodeBuddy Skill

CodeBuddy 原生 Skill 入口位于：

`.codebuddy/skills/`

这些文件只负责把任务路由到根目录 `skills/` 中的正式 Skill，不保存第二份正式工作流正文。

## 修改与校验

修改规则、Skill、脚本、测试、目录、README、版本或发布内容时，必须先读取：

`rules/core/repository-documentation-rules.md`

日常业务产物使用：

`python scripts/validate_task.py --manifest <current-manifest>`

修改规则、Skill、Schema、脚本、测试、版本、CHANGELOG、目录或 CI 时使用：

`python scripts/validate_release.py`