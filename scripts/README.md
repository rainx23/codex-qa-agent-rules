# Scripts

仓库的离线生成、转换、索引与静态校验工具。

## 目录定位

脚本负责规则契约生成与校验，不连接数据库或执行用户业务 SQL。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `qa_contracts.py` | Schema 与 Manifest 的可执行契约源 | 是 |
| `generate_schemas.py` | 生成或检查 Schema | 是 |
| `validate_*.py` | 静态校验门禁 | 是 |
| `validate_models.py` | 校验本次实际生成模型、跨模型引用、测试维度评估及可访问证据文件的哈希新鲜度；`--strict` 可提升维度 review warning | 是 |
| `validate_testcase_quality.py` | 校验 XMind Markdown，并按需编排和展示 Testcase Value Assessment 结果 | 是 |
| `validate_testcase_index.py` | 完整校验 passed Manifest，并逐字段核对正式索引的唯一登记 | 是 |
| `validate_formal_artifacts.py` | 扫描全部 passed 正式 Manifest，并统一复验模型、Markdown、Workbook 与索引 | 是 |
| `render_delivery_summary.py` | 从 Manifest 和结构化模型确定性渲染中文聊天交付摘要 | 是 |
| `validate_delivery_summary.py` | 校验摘要固定章节、状态、路径、数量和 Confirmation 一致性 | 是 |
| `verify_xmind.py` | 对照 Markdown 递归复验 Workbook 完整树，同时保留根节点、TC 数和节点总数摘要 | 是 |

## 使用入口

- 发布前命令见 `docs/codex/rule-validation-checklist.md`。
- `validate_schemas.py` 校验仓库契约和固定 Fixture；`validate_models.py` 校验本次真实模型；`validate_manifest.py` 最终复验全链路产物。
- `validate_evidence.py` 按物理行闭区间精确比对文本 `excerpt`，只归一换行并移除开头 BOM；`validate_analysis_report.py` 校验主摘要 ID 唯一性，并禁止 passed 正式报告残留草稿用例措辞。
- 可选用法：`python scripts/validate_testcase_quality.py path/to/case_xmind.md --value-assessment path/to/testcase-value-assessment.json`。该 CLI 只负责编排和稳定展示；评分内核、路径/Hash 校验和持久化重算均位于 `qa_contracts.py`。
- Testcase Value Assessment 的 warning 和 suggestion 在阶段一非阻塞；只有 Assessment error 使该命令返回非零退出码。未传参数时不搜索默认 Assessment。
- XMind 校验拒绝 `...`/`……` 截断标记，并对未加括号的混合 `AND/OR` 输出 warning；不设置任何节点长度 error 或 warning。
- 正式产物在更新索引后运行 `python scripts/validate_formal_artifacts.py`；单个 Workbook 可使用 `python scripts/verify_xmind.py path/to/case.xmind --markdown path/to/case.xmind.md` 复验。
- 最终聊天交付使用 `python scripts/render_delivery_summary.py --manifest path/to/manifest.json --check`；可选 `--output` 保存副本，独立文件使用 `validate_delivery_summary.py --manifest ... --summary ...` 校验。完整用例摘要固定展示八类测试维度覆盖。
- 来源组合 Hash 统一由 `file_hash_utils.py` 处理：文本换行和 UTF-8 BOM 归一，二进制保持原始字节，规范化相对路径参与组合 Hash。
- 外部工作区的 Manifest 仍从规则仓库读取 `RULE_VERSION`，但来源、证据和正式产物相对路径从 Manifest 所在工作区解析；绝对路径、`..` 和 resolve 后越界仍被拒绝。
- integrated 业务仓库缺少 `rules-repository.json.sql_defaults.author` 时，`validate_repository_mode.py` 输出显式迁移错误；脚本不会自动修改业务配置。

## 维护约束

- 新增、删除或改变脚本命令、输入输出时，更新本 README、检查清单、CI 静态契约和测试。
- 生成脚本不得在校验模式中修改文件。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。
