# CodeBuddy 适配层

## 目录定位

本目录保存 CodeBuddy 对当前 QA 规则仓库的原生适配入口。

正式 QA 规则、工作流、Schema、脚本和测试仍保存在仓库根目录的 `AGENTS.md`、`skills/`、`rules/`、`scripts/` 和 `tests/` 中。本目录不得成为第二份正式规则来源。

## 主要内容

- `skills/`：CodeBuddy 原生 Skill 包装入口。
- 各包装 Skill 只引用根目录对应的正式 `skills/*/SKILL.md`。
- 本目录不保存核心规则、业务 Profile、Schema、校验脚本或测试产物。

## 使用入口

CodeBuddy 开始任务时先读取仓库根目录：

`CODEBUDDY.md`

`CODEBUDDY.md` 通过以下 CodeBuddy 文件导入语法加载：

`@AGENTS.md`

根目录 `AGENTS.md` 仍是角色边界、任务路由、规则优先级和全局门禁的唯一权威来源。

命中具体 QA 任务后，再通过本目录的包装 Skill 进入根目录正式 Skill。

## 维护约束

- 不得在本目录复制根目录 Skill 的完整工作流正文。
- 不得复制 `rules/core`、`rules/profiles`、`rules/schemas` 或 `scripts`。
- 修改正式规则和现有 Skill 时，只修改根目录唯一正文。
- 新增、删除或重命名正式 Skill 时，需要同步调整对应的 CodeBuddy 包装 Skill。
- 包装 Skill 的名称、描述和目标路径必须与正式 Skill 保持一致。
- CodeBuddy 适配入口不得降低证据、确认、追踪、用例质量和产物校验门禁。

## 自动生成文件

本目录当前不包含自动生成文件。所有包装 Skill 均为人工维护的轻量适配入口。