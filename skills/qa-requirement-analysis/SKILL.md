---
name: qa-requirement-analysis
description: 用于分析禅道、OpenSpec、Markdown、截图或粘贴文本中的 QA 需求，建立基于证据的事实、待确认门禁、风险、验收标准和回归范围。适用于需求分析、新需求评审以及 Diff 分析前的需求基线建立。Requirement analysis, Zentao, OpenSpec, acceptance baseline, QA risk and regression scope.
---

# QA 需求分析（QA Requirement Analysis）

将本 Skill 的根目录解析为当前 `SKILL.md` 向上两级的仓库根目录。

## 规则加载

1. 完整读取 `../../rules/core/evidence-rules.md`。
2. 完整读取 `../../rules/core/confirmation-gate.md`。
3. 完整读取 `../../rules/core/analysis-report-contract.md`。
4. 完整读取 `../../rules/core/traceability-rules.md`。
5. 完整读取 `../../rules/core/structured-model-contract.md`。
6. 对禅道或同类分段需求，读取 `../../rules/profiles/zentao.md`，并以第三部分产品规则作为默认验收依据。
7. 仅读取与需求匹配的其他 `../../rules/profiles` 文件。
8. 用户要求生成最终用例时，将结构化结果交给 `../qa-testcase-design/SKILL.md`。

## 执行流程

1. 确认每个需求来源均可读取，并说明本次分析范围。
2. 分析禅道需求时，区分第一部分业务背景与第三部分产品实现规则；优先采用用户确认的范围，不把普通背景与计划差异直接判定为阻塞冲突。
3. 提取业务目标、系统或页面入口、角色、主流程、字段规则、数据定义、验收标准、异常行为和明确排除项。
4. 建立事实表，区分确定事实、冲突事实、推断事实和缺失事实；每个核心结论都必须附允许的证据来源标签。
5. 应用确认门禁：只询问阻塞类待确认点；非阻塞类和建议确认类继续保留在报告中，不阻断已确定的分析。
6. 建立并校验 `../../rules/schemas/requirement-analysis.schema.json` 约束的 Requirement Analysis Model。报告与模型必须来自同一组事实；验收标准引用已确认事实 ID，冲突事实引用对应确认点。
7. 只有需求输入时，输出纯需求分析契约：分析范围、需求理解、规则拆解、证据、待确认点、风险、测试点摘要和回归范围；不强制要求疑似缺陷章节。
8. 存在 Diff 证据时，将 Requirement Analysis Model 交给 Diff Skill，并在设计用例前切换到联合分析契约。
9. 定稿前必须调用 `qa-knowledge-management` 的 `search` 模式。记录 active/candidate/conflicting/superseded 命中，历史知识不得直接视为当前确认事实。
10. 填充数据影响与验证决策：`data_validation_required`、原因、推荐方式、SQL 生成状态、指标定义缺口和阻塞问题。指标准确性默认采用 SQL，除非用户提供明确且可信的对账依据。
11. 用户粘贴完整 DDL 时，解析草稿并与知识库比较规范化哈希；只提供少量字段时标记为 partial，不创建或覆盖完整表 DDL。

本 Skill 不渲染 XMind；不得把模板、代码行为或推断升级为需求事实。
