# 清仓股弹窗权限条件矩阵需求分析

报告模式：纯需求

Schema Version: 2.0.0

Rule Version: 2.11.0

Generated At: 2026-07-18 20:18:36 Asia/Shanghai

## 本次分析范围

覆盖模拟交易和正式交易清仓股弹窗的多入口合并、普通建仓人和跟进人关系矩阵、指定用户集合、股票行与汇总行可见性、策略段隔离、AND/OR、原有权限及可用资金弹窗回归。不修改业务代码，不执行真实页面、接口或 SQL。

## 需求理解

模拟交易与正式交易在核心规则、步骤、Oracle 和风险一致时合并为一个 TC 的两个平级入口分支。普通建仓人 role_type∈{10,20}、普通跟进人 role_type=30，分别覆盖五种关系与四种目标范围；指定用户两类权限分别覆盖包含于、不包含、单用户、多用户、一个命中和全部不命中。配置项存在性只证明控件和选项存在，不能代替股票可见性行为覆盖。

## 规则拆解

- FACT-001：模拟与正式同规则时使用同一 TC 的两个入口分支。
- FACT-002、FACT-003、FACT-004：普通建仓人和跟进人覆盖五种关系、四种目标范围及对应 role_type。
- FACT-005、FACT-011：指定用户覆盖两种关系、单用户、多用户、一个命中和全部不命中。
- FACT-006、FACT-007：112 个 required combination 必须使用行为型步骤验证股票和汇总可见性，配置存在性不计入行为覆盖。
- FACT-008、FACT-009、FACT-010：策略段隔离、AND/OR、原有权限及可用资金回归分别验证。
- FACT-012：重复用户相关行为不在本轮验收范围。

## 证据来源

用户补充确认已保存为 `testcases/clearance-permission-20260718-v2/evidence/user-confirmation.md`；Evidence Hash 为 `sha256:9330d0339667ef83f8e9f1e7bbc9d919f7d84f161361883b69662891bc0d5196`。

## 待确认点

无 blocking、nonblocking 或 suggested 待确认点。

## 风险点

- RISK-001、RISK-002 对应 FACT-007：无权限泄露和汇总越权。
- RISK-003 对应 FACT-008：清仓与清后重建策略段串权。
- RISK-004、RISK-014 对应 FACT-003、FACT-004、FACT-005：角色映射或配置项缺失。
- RISK-005、RISK-006、RISK-007、RISK-008、RISK-009 对应 FACT-002、FACT-003、FACT-004、FACT-006：关系方向、集合命中和目标范围解析错误。
- RISK-010 对应 FACT-005、FACT-011：指定用户多值集合判断错误。
- RISK-011、RISK-012 对应 FACT-009：AND/OR 错误或原有权限被覆盖。
- RISK-013 对应 FACT-010：可用资金弹窗回归受损。

## 需求-Diff-测试点追踪矩阵

| 需求点ID | 需求证据 | 风险ID | 测试点或TC |
| --- | --- | --- | --- |
| REQ001 | FACT-001、FACT-007 | RISK-001 | TC001 |
| REQ005 | FACT-001、FACT-007 | RISK-001 | TC001 |
| REQ001 | FACT-001、FACT-008 | RISK-003 | TC002 |
| REQ006 | FACT-001、FACT-008 | RISK-003 | TC002 |
| REQ001 | FACT-001、FACT-007 | RISK-002 | TC003 |
| REQ005 | FACT-001、FACT-007 | RISK-002 | TC003 |
| REQ002 | FACT-003、FACT-004 | RISK-004 | TC004 |
| REQ003 | FACT-003、FACT-004 | RISK-004 | TC004 |
| REQ002 | FACT-003、FACT-004、FACT-005 | RISK-014 | TC005 |
| REQ003 | FACT-003、FACT-004、FACT-005 | RISK-014 | TC005 |
| REQ004 | FACT-003、FACT-004、FACT-005 | RISK-014 | TC005 |
| REQ002 | FACT-002、FACT-003、FACT-007 | RISK-005、RISK-009 | TC006 |
| REQ005 | FACT-002、FACT-003、FACT-007 | RISK-005、RISK-009 | TC006 |
| REQ002 | FACT-002、FACT-003、FACT-007 | RISK-005、RISK-009 | TC007 |
| REQ005 | FACT-002、FACT-003、FACT-007 | RISK-005、RISK-009 | TC007 |
| REQ002 | FACT-002、FACT-003、FACT-007 | RISK-006、RISK-009 | TC008 |
| REQ005 | FACT-002、FACT-003、FACT-007 | RISK-006、RISK-009 | TC008 |
| REQ002 | FACT-002、FACT-003、FACT-007 | RISK-007、RISK-009 | TC009 |
| REQ005 | FACT-002、FACT-003、FACT-007 | RISK-007、RISK-009 | TC009 |
| REQ002 | FACT-002、FACT-003、FACT-007 | RISK-008、RISK-009 | TC010 |
| REQ005 | FACT-002、FACT-003、FACT-007 | RISK-008、RISK-009 | TC010 |
| REQ003 | FACT-002、FACT-004、FACT-007 | RISK-005、RISK-009 | TC011 |
| REQ005 | FACT-002、FACT-004、FACT-007 | RISK-005、RISK-009 | TC011 |
| REQ003 | FACT-002、FACT-004、FACT-007 | RISK-005、RISK-009 | TC012 |
| REQ005 | FACT-002、FACT-004、FACT-007 | RISK-005、RISK-009 | TC012 |
| REQ003 | FACT-002、FACT-004、FACT-007 | RISK-006、RISK-009 | TC013 |
| REQ005 | FACT-002、FACT-004、FACT-007 | RISK-006、RISK-009 | TC013 |
| REQ003 | FACT-002、FACT-004、FACT-007 | RISK-007、RISK-009 | TC014 |
| REQ005 | FACT-002、FACT-004、FACT-007 | RISK-007、RISK-009 | TC014 |
| REQ003 | FACT-002、FACT-004、FACT-007 | RISK-008、RISK-009 | TC015 |
| REQ005 | FACT-002、FACT-004、FACT-007 | RISK-008、RISK-009 | TC015 |
| REQ004 | FACT-005、FACT-011、FACT-007 | RISK-010 | TC016 |
| REQ005 | FACT-005、FACT-011、FACT-007 | RISK-010 | TC016 |
| REQ004 | FACT-005、FACT-011、FACT-007 | RISK-010 | TC017 |
| REQ005 | FACT-005、FACT-011、FACT-007 | RISK-010 | TC017 |
| REQ004 | FACT-005、FACT-011、FACT-007 | RISK-010 | TC018 |
| REQ005 | FACT-005、FACT-011、FACT-007 | RISK-010 | TC018 |
| REQ004 | FACT-005、FACT-011、FACT-007 | RISK-010 | TC019 |
| REQ005 | FACT-005、FACT-011、FACT-007 | RISK-010 | TC019 |
| REQ007 | FACT-009 | RISK-012 | TC020 |
| REQ008 | FACT-010 | RISK-013 | TC021 |
| REQ007 | FACT-009 | RISK-011 | TC022 |
| REQ007 | FACT-009 | RISK-011 | TC023 |

## 测试点摘要

- RISK-001 至 RISK-014 共映射 23 个 TC、42 个入口分支和 112 个行为组合。
- RISK-005 至 RISK-010 的关系、目标范围和指定用户集合保留独立失败定位，没有按入口机械拆分 TC。

## P0 重点

P0 TC 为 TC001-TC004、TC006-TC019、TC022-TC023，共 20 个；覆盖 11 个 P0 Risk。

## 回归范围

核心回归覆盖股票行、汇总行、策略段、角色映射、全部关系/目标/指定用户行为和 AND/OR；关联回归覆盖配置完整性与原有权限；冒烟回归覆盖可用资金弹窗字段基线。

## 历史知识命中

未使用历史知识推导新权限行为；本轮用户补充是当前事实来源。

## 数据影响分析

权限过滤、汇总统计和用户集合判断涉及业务数据，但当前缺少完整 DDL、查询 SQL、接口契约和可执行测试数据。

## 数据验证结论

状态为 blocked；未生成或执行 SQL，不把结构字段推导为过滤、去重或保存行为。

## 验证 SQL 计划

待完整 DDL 与查询链路补齐后再生成只读 SQL；本轮不连接数据库。

## 风险覆盖与路径

Requirement Analysis Model、Risk Coverage Matrix、Testcase Model、XMind Markdown、Workbook 和 Manifest 均保存在本替代版本目录并由统一正式产物扫描入口复验。


