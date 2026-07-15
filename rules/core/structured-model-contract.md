# 结构化模型交接契约

结构化模型用于 Skills 内部交接和自动校验，不改变分析报告或固定 XMind Markdown 层级。可复用模型保存到版本化产物目录；只用于单次执行的模型保存到临时目录并在完成后清理。

## 单一来源

- 执行契约、枚举和跨字段规则只维护在 `scripts/qa_contracts.py`。
- `rules/schemas/*.schema.json` 由 `scripts/generate_schemas.py` 生成，不手工维护。
- 运行时使用标准库执行同一契约生成的必填、类型、枚举、正则、唯一性和跨模型 ID 校验，不依赖 `jsonschema`，避免 Schema 只生成不执行。
- `RULE_VERSION` 是规则版本唯一来源，Manifest 不得自行填写其他版本。

## 交接顺序

1. 需求 Skill 生成 Requirement Analysis Model，并从同一分析结果渲染需求报告。
2. Diff Skill 接收可选 Requirement Analysis Model，生成 Diff Impact Model；存在需求模型时以其验收标准判断覆盖。
3. 用例 Skill 接收需求模型、可选 Diff 模型和历史缺陷，先生成 Risk Coverage Matrix，再生成 Testcase Model。
4. Testcase Model 渲染固定 XMind Markdown；模型字段不得成为新的 XMind 节点。
5. 产物 Skill 依次校验报告、分析模型、风险矩阵、用例模型、Markdown、Workbook、Manifest 和索引。

报告与模型必须来自同一分析结果，不得在事实、待确认点、风险、模式或计数上互相矛盾。Risk Coverage Matrix 同时保存主 `business_entry` 和用于合并场景的 `business_entries` 覆盖入口列表。需求点、Diff 变更、风险和 TC 的 ID 必须双向一致；所有 P0 风险必须映射 TC；模型 TC 与 Markdown TC 集合、测试点和预期必须一致。
