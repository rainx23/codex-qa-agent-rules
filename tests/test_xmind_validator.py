from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_validation import ValidationError, validate_markdown_text

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


if __name__ == "__main__":
    unittest.main()

