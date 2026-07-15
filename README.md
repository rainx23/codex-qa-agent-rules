# Codex QA Agent Rules

面向禅道、OpenSpec、Markdown、截图、Git Diff 和 commit 的证据驱动测试分析规则集。根目录是当前项目运行副本，codex-qa-agent-rules 是可复用模板；规则、Skills、脚本和测试必须同步，历史索引行可以按项目保留差异。

## 架构

- AGENTS.md：角色边界、优先级、任务路由和全局门禁。
- rules/core：证据、确认门禁、用例质量、追踪和产物治理的唯一正文。
- rules/profiles：Web、API、SQL 数据、金融交易、权限安全和非功能专项规则。
- skills：需求分析、Diff 影响、用例设计、产物校验四个可触发工作流。
- docs/codex：旧路径兼容入口，不复制正式规则。
- scripts：报告、Markdown、Workbook、Manifest、索引和编码治理工具。
- tests：真实 Fixtures、Golden 结果和规则契约回归。

规则优先级为：用户本轮要求 > AGENTS 全局边界 > 当前 Skill > 核心规则 > Profile > 示例。

## 工作流

1. 需求 Skill 建立结构化事实、验收基准和待确认分级。
2. Diff Skill 校验范围、分析调用链并对照需求覆盖。
3. 用例 Skill 建立风险矩阵，生成最小有效用例集和固定 XMind Markdown。
4. 产物 Skill 校验报告、Markdown、Workbook、Manifest 和索引。
5. 任一步失败时保留证据并停止完成声明。

只有阻塞类问题暂停最终用例；非阻塞类和建议确认类继续已明确部分。跳过的问题仍保留，假设不得升级为事实。

## 常用命令

    python scripts/validate_analysis_report.py path/to/report.md --xmind-md path/to/case_xmind_yyyymmdd.md
    python scripts/validate_xmind_md.py path/to/case_xmind_yyyymmdd.md
    python scripts/validate_testcase_quality.py path/to/case_xmind_yyyymmdd.md --traceability-report path/to/report.md
    python scripts/md_to_xmind.py path/to/case_xmind_yyyymmdd.md
    python scripts/md_to_xmind.py testcases/zentao/xmind
    python scripts/validate_manifest.py path/to/manifest.json
    python scripts/build_testcase_index.py testcases/index.md path/to/manifest.json
    python scripts/repair_text_encoding.py testcases/index.md --check
    python scripts/validate_skill_contracts.py skills
    python -m unittest discover -s tests -v

本地 XMind Markdown 必须使用单根、固定维度、两种固定层级之一、4 空格和全局连续 TC 编号，不包含代码块、表格、JSON、说明或标签式节点。转换时默认拒绝覆盖，并自动复验压缩包。

## 产物和版本

完整产物包括报告、XMind Markdown、Workbook、Manifest 和索引。Manifest 结构见 rules/schemas/artifact-manifest.schema.json；使用新增、补充、替代、废弃描述版本关系，不覆盖历史文件。索引使用 UTF-8，artifact_id 唯一。

## Skills

每个 Skill 包含必需的 name 和 description frontmatter，以及 agents/openai.yaml。Skill 内引用以 Skill 目录为基准，使用 ../../rules 和 ../../scripts 到达仓库资源。

## 复用和扩展

复制 AGENTS.md、rules、skills、docs/codex、scripts、tests 和 testcases 结构到目标项目。新增 Profile 时只维护领域特有规则，并从相关 Skill 按证据路由；不得复制核心规则正文。

## 发布前验收

执行 docs/codex/rule-validation-checklist.md 中的命令，确认 Skill 校验、Python 语法、全部测试、无效样例拦截、历史样例转换、Workbook 复验、Manifest、索引和双目录哈希全部通过。Python 3.10+；运行时脚本只使用标准库。
