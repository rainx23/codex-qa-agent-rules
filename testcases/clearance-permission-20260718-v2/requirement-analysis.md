# 清仓股弹窗权限条件矩阵需求分析

报告模式：纯需求

Schema Version: 2.0.0

Rule Version: 2.12.0

Generated At: 2026-07-22 11:08:47 Asia/Shanghai

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
- FACT-013：继承旧版已确认的包含于任一满足、完全包含于全部满足语义。
- FACT-014：不包含关系命中则可见、未命中则不可见；多用户任一命中可见、全部未命中不可见。

## 证据来源

来源类型：pasted_text、user_confirmation。旧版需求原文证据 `testcases/clearance-permission-20260718/evidence/user-requirement.md` 与 V2 用户补充证据 `testcases/clearance-permission-20260718-v2/evidence/user-confirmation.md` 同时保留；前者确认包含于任一满足、完全包含于全部满足，后者确认矩阵范围，但二者原证据未给出不包含关系真值表；本轮 CONF-001 增量确认已补齐。

## 待确认点

- CONF-001 FACT-014 severity=blocking status=resolved：已确认不包含关系命中则可见、未命中则不可见；多用户任一命中可见、全部未命中不可见。
- CONF-002 FACT-015 severity=nonblocking status=pending：SQL 对账缺少表结构和稳定行标识字段；不阻塞测试设计，SQL验证保持 blocked。

## 风险点

- RISK-001、RISK-002 对应 FACT-007：无权限泄露和汇总越权。
- RISK-003 对应 FACT-008：清仓与清后重建策略段串权。
- RISK-004、RISK-014 对应 FACT-003、FACT-004、FACT-005：角色映射或配置项缺失。
- RISK-005、RISK-006、RISK-007、RISK-008、RISK-009 对应 FACT-002、FACT-003、FACT-004、FACT-006：关系方向、集合命中和目标范围解析错误。
- RISK-010 对应 FACT-005、FACT-011：指定用户多值集合判断错误。
- RISK-011、RISK-012 对应 FACT-009：AND/OR 错误或原有权限被覆盖。
- RISK-013 对应 FACT-010：可用资金弹窗回归受损。
- RISK-015 对应 FACT-014、CONF-001：不包含关系方向错误风险已覆盖。

## 测试维度扫描

| 测试维度 | 状态 | 主要风险 | 对应 TC | 原因或阻塞 |
| --- | --- | --- | --- | --- |
| 功能测试 | 不适用 | 无独立流程风险 | 无 | 核心 Oracle 为权限可见集合 |
| 数据测试 | 已覆盖 | 汇总越权 | TC003 | 作为权限主维度用例的辅助维度 |
| 异常测试 | 不适用 | 无 | 无 | 未提供独立异常处理规则 |
| 权限测试 | 已覆盖 | 可见性、关系、目标范围、AND/OR | TC001-TC019、TC022-TC023 | 权限矩阵主链路 |
| 导出测试 | 不适用 | 无 | 无 | 两个弹窗未包含导出对象 |
| 兼容性测试 | 不适用 | 无 | 无 | 未提供设备、浏览器或协议兼容变更 |
| 回归测试 | 已覆盖 | 原有权限与关联弹窗受损 | TC020、TC021 | 两条用例以回归为主要 Oracle |
| SQL验证 | blocked | 数据对账 | 无 | FACT-015 / CONF-002：缺少表结构和稳定行标识字段 |

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

- RISK-001 至 RISK-015 共保留 23 个正式 TC、42 个入口分支；112 个生成组合完整登记，112 个均有确定性行为定位。
- RISK-005 至 RISK-010 的关系、目标范围和指定用户集合保留独立失败定位，没有按入口机械拆分 TC。

## P0 重点

P0 TC 为 TC001-TC004、TC006-TC019、TC022-TC023，共 20 个；覆盖 12 个 P0 Risk。

## 回归范围

核心回归覆盖股票行、汇总行、策略段、角色映射、全部关系/目标/指定用户行为和 AND/OR；关联回归覆盖配置完整性与原有权限；冒烟回归覆盖可用资金弹窗字段基线。

## 历史知识命中

本轮继承旧版需求 Evidence 中已确认的“包含于任一满足”和“完全包含于全部满足”语义；“不包含”关系由本轮 CONF-001 用户确认补齐。未使用无来源历史知识推导新的权限行为。

## 数据影响分析

权限过滤、汇总统计和用户集合判断涉及业务数据，但当前缺少完整 DDL、查询 SQL、接口契约和可执行测试数据。

## 数据验证结论

状态为 blocked；未生成或执行 SQL，不把结构字段推导为过滤、去重或保存行为。

## 验证 SQL 计划

待完整 DDL 与查询链路补齐后再生成只读 SQL；本轮不连接数据库。

## 风险覆盖与路径

Requirement Analysis Model 与正式 Risk/Testcase Model 保留完整追踪；CONF-001 已解决，正式 XMind Markdown、Workbook 和 Manifest 已生成。
