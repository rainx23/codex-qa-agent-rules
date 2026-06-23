# Codex QA Agent Rules

一套面向 Codex 的测试分析规则模板，用于把需求、禅道内容、OpenSpec、Git diff 或 commit 变更转成结构化测试分析、测试点、回归范围和可导入 XMind 的测试用例。

它适合 QA、测试架构师或研发团队在提测评审、需求评审、回归范围判断时使用，重点是让 Codex 按固定测试方法工作：不编造、不越界改业务代码、先确认不明确规则、输出本地可沉淀的测试产物。

## 能力概览

- 禅道 / OpenSpec / 手动需求分析
- Git diff / commit 测试影响分析
- 需求与 diff 联动校验
- 测试点、风险点、待确认点、回归范围输出
- XMind Markdown 测试用例生成
- Markdown 用例自动转换为 `.xmind` 文件
- 本地输出索引维护
- 同规则多模块用例合并
- 相同入口公共节点分组，降低 XMind 视觉疲劳
- 短文本用例风格，自动去重并补充高风险场景

## 目录结构

```text
.
├── AGENTS.md
├── docs/
│   └── codex/
│       ├── code-diff-review-rules.md
│       ├── qa-requirement-analysis-rules.md
│       └── xmind-case-rules.md
├── scripts/
│   └── md_to_xmind.py
└── testcases/
    ├── diff/
    │   ├── reports/
    │   └── xmind/
    ├── zentao/
    │   ├── reports/
    │   └── xmind/
    └── index.md
```

## 快速使用

把本仓库内容复制到目标项目根目录，确保目标项目根目录存在：

```text
AGENTS.md
docs/codex/
scripts/md_to_xmind.py
testcases/
```

然后在 Codex 中直接提出测试分析任务，例如：

```text
按禅道用例规则分析下面需求，并输出到本地：
<粘贴需求正文>
```

或：

```text
分析 commit abc123 的测试影响，生成完整用例
```

或：

```text
对比 old_commit..new_commit，输出回归范围和 XMind 用例
```

## 输出产物

默认“完整输出”会生成：

- 分析报告：`testcases/zentao/reports/` 或 `testcases/diff/reports/`
- XMind Markdown 用例：`testcases/zentao/xmind/` 或 `testcases/diff/xmind/`
- XMind Workbook：同目录下的 `.xmind` 文件
- 输出索引：`testcases/index.md`

`.xmind` 文件命名会和 Markdown 文件区分：

- Markdown：`xxx_xmind_yyyyMMdd_HHmmss.md`
- XMind：`xxx_workbook_yyyyMMdd_HHmmss.xmind`

## XMind 转换脚本

脚本不依赖第三方库，使用 Python 标准库生成 XMind 2020+ 可识别的 `.xmind` 压缩包结构。

手动转换命令：

```bash
python scripts/md_to_xmind.py testcases/zentao/xmind/example_xmind_20260623_120000.md
```

转换后会生成：

```text
testcases/zentao/xmind/example_workbook_20260623_120000.xmind
```

脚本会校验 Markdown 必须是 `-` 层级结构，并使用 4 个空格缩进。

## 规则说明

### AGENTS.md

总入口规则。定义 Codex 的默认测试专家角色、工作边界、输出模式、本地索引和触发规则。

### qa-requirement-analysis-rules.md

用于禅道需求、OpenSpec、手动粘贴需求、产品方案规则分析。

核心要求：

- 信息不足先抛待确认点
- 用户确认前不生成最终 XMind 用例
- 不虚构 SQL、字段、接口、页面入口
- 输出分析报告和本地文件路径

### code-diff-review-rules.md

用于 Git diff、commit 分析、gray 单分支提测场景。

核心要求：

- 单 commit 默认对比父提交
- 双 commit 按用户给定范围分析
- diff 为空或 commit 不存在必须说明
- 结合需求规则判断实现覆盖、偏差和回归风险

### xmind-case-rules.md

用于生成可导入 XMind 的 Markdown 用例和 `.xmind` 文件。

核心要求：

- 只有一个业务根节点
- 一级节点使用固定测试维度
- 相同入口抽公共节点
- TC 编号连续
- 每个 TC 只验证一个核心点
- 操作和预期使用短文本
- 删除重复、低价值用例
- 补充高风险边界场景
- 生成 Markdown 后转换 `.xmind`

## 推荐工作流

1. 用户提供需求、OpenSpec、diff 或 commit。
2. Codex 先解析规则和影响范围。
3. 如有不明确口径，先输出待确认点并暂停最终用例。
4. 用户确认或选择跳过。
5. Codex 生成分析报告、XMind Markdown 用例和 `.xmind` 文件。
6. Codex 更新 `testcases/index.md`。

## 示例提示词

```text
按禅道用例规则分析下面需求，并输出到本地：
...
```

```text
分析最新 commit 的测试影响，生成完整输出
```

```text
基于这个需求和 diff 联动分析，输出风险点、回归范围和 XMind 用例
```

```text
只列 P0 核心用例
```

## 注意事项

- 默认只做测试分析，不修改业务代码。
- 规则不明确时必须先向用户确认。
- 用户回复“跳过 / 不用管 / 继续生成 / 按默认处理”后，才允许继续生成最终用例。
- 被跳过的问题仍会记录到分析报告的待确认点中。
- 证据不足时只输出风险和待确认点，不生成确定性预期。

## 环境要求

- Python 3.10+，用于 Markdown 转 `.xmind`
- Codex 或支持 `AGENTS.md` 的 AI coding agent

## License

如需开源发布，建议在仓库中补充 `LICENSE` 文件。

