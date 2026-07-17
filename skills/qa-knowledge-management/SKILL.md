---
name: qa-knowledge-management
description: 用于检索、起草、比较、校验并在明确确认后持久化脱敏历史业务知识、DDL、逻辑、指标、数据验证决策和只读 SQL 计划；全程不连接数据库。Knowledge management, historical QA knowledge, DDL comparison, data validation and read-only SQL governance.
---

# QA 知识管理（QA Knowledge Management）

将本 Skill 的根目录解析为当前 `SKILL.md` 向上两级的仓库根目录。

## 规则加载

1. 读取 `../../rules/core/evidence-rules.md`、`../../rules/core/analysis-report-contract.md`、`../../rules/core/structured-model-contract.md` 和 `../../rules/core/sql-coding-standards.md`。
2. 解析 `rules-repository.json`：integrated 仓库使用业务项目的 `qa-knowledge/`；standalone 仓库使用 `qa-knowledge/examples/` 中的脱敏夹具。
3. 优先只加载索引，再读取最小相关的 active 命中及 current/history 文件；默认不加载完整知识树。

## 模式

- `search`：提取需求、域、入口、表、字段、逻辑、指标和 Diff 标识符；查询索引并返回 active/candidate/conflicting/superseded/deprecated/missing 证据，同时说明路径和适用性风险。
- `draft`：解析完整粘贴 DDL 或局部字段，计算原始/规范化哈希，比较已有知识并生成仅供评审的变更草稿；不得写入正式知识。
- `persist`：仅在用户明确确认后写入。保持 current/history 分离、ID、哈希、supersedes 和索引稳定；不得持久化推断事实、凭据，也不得用 partial schema 覆盖完整 schema。
- `compare`：比较新旧 DDL、逻辑、公式、过滤、连接、时间、精度和例外，报告新增/删除/变更/不受影响的行为及回归范围。
- `validate`：执行知识、Schema、引用、哈希、active 版本、supersedes 环、索引漂移和敏感信息检查。

## 数据验证与 SQL

1. 将 `data_validation_required` 设置为 `required`、`optional`、`not_required` 或 `blocked`，同时填写原因和缺失信息。
2. 指标准确性默认使用 `sql`；只有存在明确的基线/目标、字段、过滤、时间、容差和证据时才使用 `cross_source_reconciliation`；两者都需要时使用 `mixed`。
3. 只生成只读 SQL。`SQLV###` 和 `REC###` 是可被多个 TC 复用的引用；XMind 引用 ID，不嵌入大段 SQL。
4. 静态检查通过后 SQL 可以处于 `generated` 或 `reviewed`；没有用户执行结果时不得标记为 `executed`、`passed` 或 `failed`。

完整 DDL 只有在原文明确包含的键、分区、分桶、索引、Engine 和 Properties 均稳定解析后才能标记 `complete`；任一显式结构无法提取即降级。integrated 仓库缺少 `rules-repository.json.sql_defaults.author` 时输出迁移错误并停止，不读取系统用户名、不使用旧姓名、不静默回退，也不自动修改业务配置。

本 Skill 永不连接数据库、执行 SQL、保存凭据，也不会将历史知识提升为高于当前用户确认需求的事实。
