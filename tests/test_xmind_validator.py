from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_validation import ValidationError, validate_markdown_text
from validate_xmind_md import main as validate_cli

VALID = (ROOT / "tests/fixtures/valid_case_xmind.md").read_text(encoding="utf-8")


class XMindValidatorTests(unittest.TestCase):
    def assert_invalid(self, text: str, token: str) -> None:
        with self.assertRaisesRegex(ValidationError, token):
            validate_markdown_text(text)

    def test_01_valid_markdown(self):
        outline = validate_markdown_text(VALID)
        self.assertEqual("客户查询结果", outline.root.title)
        self.assertEqual(["TC001", "TC002"], [node.title for node in outline.tc_nodes])

    def test_02_multiple_roots(self):
        self.assert_invalid(VALID + "- 第二根\n", "根节点必须唯一")

    def test_03_tc_gap(self):
        self.assert_invalid(VALID.replace("TC002", "TC003"), "全局连续")

    def test_04_tc_duplicate(self):
        self.assert_invalid(VALID.replace("TC002", "TC001"), "全局连续|重复")

    def test_05_illegal_dimension(self):
        self.assert_invalid(VALID.replace("功能测试", "随意测试"), "非法测试维度")

    def test_06_tab_indentation(self):
        self.assert_invalid(VALID.replace("    - 功能测试", "\t- 功能测试"), "Tab")

    def test_07_non_four_space_indentation(self):
        self.assert_invalid(VALID.replace("    - 功能测试", "  - 功能测试"), "4 空格")

    def test_08_level_jump(self):
        self.assert_invalid(VALID.replace("    - 功能测试", "        - 功能测试"), "一次最多增加一级")

    def test_09_label_node(self):
        self.assert_invalid(VALID.replace("条件过滤", "测试点：条件过滤"), "标签式节点")

    def test_10_fuzzy_expectation(self):
        self.assert_invalid(VALID.replace("返回集合仅包含该客户编号对应记录", "返回结果正确"), "模糊断言")

    def test_confirmed_rule_placeholder_is_a_fuzzy_expectation(self):
        self.assert_invalid(
            VALID.replace("返回集合仅包含该客户编号对应记录", "按已确认规则处理"),
            "模糊断言",
        )

    def test_vague_existing_rule_and_baseline_assertions_are_rejected(self):
        expected = "返回集合仅包含该客户编号对应记录"
        self.assert_invalid(VALID.replace(expected, "各统计项按现有统计口径一致"), "VAGUE_EXISTING_RULE_ASSERTION")
        self.assert_invalid(VALID.replace(expected, "其他功能不受影响"), "VAGUE_BASELINE_ASSERTION")

    def test_vague_relation_oracles_are_rejected(self):
        expected = "返回集合仅包含该客户编号对应记录"
        for vague in (
            "按关系判断", "按关系得到可观察结果", "根据关系判断可见性",
            "根据对应关系处理", "关系生效", "权限结果正确", "按配置结果展示",
        ):
            with self.subTest(vague=vague):
                self.assert_invalid(VALID.replace(expected, vague), "VAGUE_RELATION_ORACLE")

    def test_explicit_relation_oracle_is_allowed(self):
        expected = "返回集合仅包含该客户编号对应记录"
        text = VALID.replace(expected, "任一角色属于目标集合时股票可见；全部角色均不属于目标集合时股票不可见")
        self.assertEqual(2, len(validate_markdown_text(text).tc_nodes))

    def test_explicit_baseline_and_field_oracle_are_allowed(self):
        step = "输入已确认的客户编号并查询"
        expected = "返回集合仅包含该客户编号对应记录"
        text = VALID.replace(step, "使用同一账号和查询条件记录变更前基线后重新查询").replace(
            expected, "变更前后行数、可见范围和金额逐项一致"
        )
        self.assertEqual(2, len(validate_markdown_text(text).tc_nodes))

    def test_11_semantic_duplicate_fields(self):
        text = """- 字段校验
    - 功能测试
        - 字段设置入口
            - TC001
                - 姓名必填
                    - 姓名留空后提交
                        - 阻止提交并标识必填
        - 另一个字段入口
            - TC002
                - 手机号必填
                    - 手机号留空后提交
                        - 阻止提交并标识必填
"""
        self.assert_invalid(text, "同规则重复用例")

    def test_12_unconfirmed_rule_is_not_fixed_across_nodes(self):
        text = VALID.replace("条件过滤", "未知状态待确认").replace(
            "返回集合仅包含该客户编号对应记录", "默认过滤未知状态"
        )
        self.assert_invalid(text, "未确认口径")

    def test_fixed_hierarchy_rejects_extra_group(self):
        text = VALID.replace(
            "            - TC001",
            "            - 额外分组\n                - TC001",
            1,
        )
        self.assert_invalid(text, "公共入口下只能包含 TC|层级")

    def test_local_file_rejects_table_json_and_code_fence(self):
        for prefix in ("| 表格 |\n", "{\"key\": 1}\n", "~~~text\n"):
            self.assert_invalid(prefix + VALID, "禁止代码块、表格、JSON")

    def test_tc_number_is_exactly_three_digits(self):
        self.assertEqual("TC001", validate_markdown_text(VALID).tc_nodes[0].title)
        self.assert_invalid(VALID.replace("TC001", "TC01"), "严格为 TC 加三位数字")
        self.assert_invalid(VALID.replace("TC001", "TC0001"), "严格为 TC 加三位数字")

    def test_normal_status_is_observable_but_vague_normal_is_rejected(self):
        expected = "返回集合仅包含该客户编号对应记录"
        observable = VALID.replace(expected, "任务状态由处理中变更为正常")
        self.assertEqual(2, len(validate_markdown_text(observable).tc_nodes))
        self.assert_invalid(VALID.replace(expected, "页面正常"), "模糊断言")
        self.assertEqual(2, len(validate_markdown_text(VALID.replace(expected, "状态值为 NORMAL")).tc_nodes))

    def test_permission_and_data_source_context_prevent_false_duplicate_error(self):
        text = """- 上下文差异
    - 权限测试
        - 权限入口
            - TC001
                - 正式环境有权限查询
                    - 使用数据源A并以有权限用户查询
                        - 返回有权限范围内记录
            - TC002
                - 模拟环境无权限查询
                    - 使用数据源B并以无权限用户查询
                        - 拒绝返回越权记录
"""
        self.assertEqual([], validate_markdown_text(text).warnings)

    def test_suspected_duplicate_is_warning_and_strict_promotes_failure(self):
        text = """- 字段校验
    - 功能测试
        - 字段设置入口
            - TC001
                - 姓名必填
                    - 姓名留空后提交
                        - 阻止提交并标识必填
        - 另一个字段入口
            - TC002
                - 手机号必填校验
                    - 手机号留空以后提交
                        - 阻止提交并在字段旁标识必填
"""
        outline = validate_markdown_text(text)
        self.assertTrue(any("疑似重复" in warning for warning in outline.warnings))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "warning_xmind.md"
            path.write_text(text, encoding="utf-8")
            self.assertEqual(0, validate_cli([str(path)]))
            self.assertEqual(1, validate_cli([str(path), "--strict"]))

    def test_multi_entry_grouped_structure_is_valid_and_keeps_single_tc(self):
        path = ROOT / "tests/fixtures/multi_entry_valid_xmind.md"
        outline = validate_markdown_text(path.read_text(encoding="utf-8"), path)
        self.assertEqual(["TC001"], [node.title for node in outline.tc_nodes])
        self.assertEqual(3, len(outline.tc_nodes[0].children[0].children))

    def test_multi_entry_direct_structure_is_valid(self):
        path = ROOT / "tests/fixtures/multi_entry_direct_valid_xmind.md"
        outline = validate_markdown_text(path.read_text(encoding="utf-8"), path)
        self.assertEqual(1, len(outline.tc_nodes))

    def test_multi_entry_structure_boundaries_fail(self):
        for name, token in (
            ("multi_entry_mixed_invalid_xmind.md", "层级必须严格|入口必须是独立"),
            ("multi_entry_single_branch_invalid_xmind.md", "至少需要两个入口"),
            ("multi_entry_joined_line_invalid_xmind.md", "拼接在同一步骤"),
        ):
            self.assert_invalid(
                (ROOT / "tests/fixtures" / name).read_text(encoding="utf-8"),
                token,
            )

    def test_regular_combination_operation_is_not_multi_entry_error(self):
        text = VALID.replace("输入已确认的客户编号并查询", "输入股票代码和交易日期后查询")
        self.assertEqual(2, len(validate_markdown_text(text).tc_nodes))

    def test_semantic_compaction_symbols_are_valid_without_length_gate(self):
        step = "输入已确认的客户编号并查询"
        expected = "返回集合仅包含该客户编号对应记录"
        compact = VALID.replace(step, "查询 role_type=30 AND enabled_flag=1 的记录").replace(
            expected, "role_type∈{10,20,30} 的目标记录状态由未配置→已配置"
        )
        self.assertEqual(2, len(validate_markdown_text(compact).tc_nodes))

        long_but_complete = VALID.replace(
            step,
            "对已确认客户编号执行查询并保留业务对象、核心条件和操作主体" * 30,
        )
        self.assertEqual(2, len(validate_markdown_text(long_but_complete).tc_nodes))

    def test_truncation_markers_are_rejected(self):
        step = "输入已确认的客户编号并查询"
        self.assert_invalid(VALID.replace(step, "输入客户编号..."), "截断或省略")
        self.assert_invalid(VALID.replace(step, "输入客户编号……"), "截断或省略")

    def test_ambiguous_and_or_warns_but_parenthesized_expression_passes(self):
        step = "输入已确认的客户编号并查询"
        ambiguous = validate_markdown_text(VALID.replace(step, "按 A AND B OR C 查询"))
        self.assertTrue(any("AND/OR" in warning and "括号" in warning for warning in ambiguous.warnings))
        explicit = validate_markdown_text(VALID.replace(step, "按 (A AND B) OR C 查询"))
        self.assertFalse(any("AND/OR" in warning for warning in explicit.warnings))


if __name__ == "__main__":
    unittest.main()
