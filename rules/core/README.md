# 核心规则

跨业务场景复用的正式 QA 规则。

## 目录定位

定义证据、确认门禁、产物治理、结构化模型和仓库治理等通用约束。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `repository-documentation-rules.md` | README 与版本历史治理 | 是 |
| `runtime-efficiency-rules.md` | 日常生成链的最小加载、失败即停止、重试预算和确定性产物门禁 | 是 |
| `conversation-delivery-contract.md` | 聊天框 Confirmation、文件用途、状态模板和确定性摘要契约 | 是 |
| `structured-model-contract.md` | Requirement/Risk/Testcase 交接、测试分类维度与业务条件维度边界、主辅维度契约 | 是 |
| `*-contract.md`、`*-rules.md` | 通用规则和契约 | 是 |

## 使用入口

- 由 `AGENTS.md`、各 Skill 和发布检查清单按任务路由加载。

## 维护约束

- 改动规则行为必须更新测试、CHANGELOG 和 RULE_VERSION，并评估根 README。
- 不将完整规则复制到 AGENTS、Skill 或检查清单；它们只引用正式规则文件。
- 本目录不含自动生成文件。
- blocking Confirmation 解除后必须恢复原始任务并自动完成未结束的正式产物链；XMind 采用无固定字数门禁的语义精简规则。
- 新任务采用一次授权、两阶段执行和集中确认：confirmation_only 只保存 Checkpoint/Evidence，确认后自动续跑；历史 pending Manifest 保持兼容。
- 明确枚举需求必须先建立条件矩阵；配置存在性不计为行为覆盖，多入口同规则使用不含入口名的核心去重键合并；2 至 5 个入口逐入口写步骤和预期，不少于 6 个同规则入口使用一个或多个完整适用入口范围。

版本与完整变更历史统一见 [CHANGELOG.md](../../CHANGELOG.md)。
