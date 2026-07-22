from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import validate_testcase_model
from qa_validation import ValidationError, shared_entry_scope_details, validate_markdown_text


VALID_MARKDOWN = """- 股票展示规则
    - 适用入口（以下全部TC均需逐项执行）
        - 模拟交易
            - 汇总卡片
                - 建加仓股弹窗
                - 清仓股弹窗
                - 雷达股弹窗
        - 正式交易
            - 汇总卡片
                - 建加仓股弹窗
                - 清仓股弹窗
                - 雷达股弹窗
    - 功能测试
        - 股票展示弹窗
            - TC001
                - 表外股票置灰
                    - 加载不在选股表内的股票
                        - 股票名称、代码及标签置灰
"""


class SharedEntryScopeTests(unittest.TestCase):
    def model(self) -> dict:
        data = json.loads((ROOT / "tests/fixtures/models/testcase-model.json").read_text(encoding="utf-8"))
        data["cases"] = [data["cases"][0]]
        data["cases"][0]["shared_entry_scope_id"] = "SCOPE-001"
        data["shared_entry_scope"] = {
            "scope_id": "SCOPE-001",
            "scope_title": "适用入口（以下全部TC均需逐项执行）",
            "applies_to_tc_ids": ["TC001"],
            "groups": [
                {
                    "group_name": "模拟交易",
                    "subgroups": [
                        {
                            "subgroup_name": "汇总卡片",
                            "entries": [
                                {"entry_name": "建加仓股弹窗"},
                                {"entry_name": "清仓股弹窗"},
                                {"entry_name": "雷达股弹窗"},
                            ],
                        }
                    ],
                },
                {
                    "group_name": "正式交易",
                    "subgroups": [
                        {
                            "subgroup_name": "汇总卡片",
                            "entries": [
                                {"entry_name": "建加仓股弹窗"},
                                {"entry_name": "清仓股弹窗"},
                                {"entry_name": "雷达股弹窗"},
                            ],
                        }
                    ],
                },
            ],
        }
        return data

    def test_six_fully_expanded_entries_with_shared_steps_pass(self):
        outline = validate_markdown_text(VALID_MARKDOWN)
        self.assertEqual([], validate_testcase_model(self.model()))
        scope = shared_entry_scope_details(outline)
        self.assertEqual("适用入口（以下全部TC均需逐项执行）", scope["scope_title"])
        self.assertEqual(6, sum(len(subgroup["entries"]) for group in scope["groups"] for subgroup in group["subgroups"]))

    def test_five_entries_must_use_independent_entry_branches(self):
        data = self.model()
        data["shared_entry_scope"]["groups"][1]["subgroups"][0]["entries"].pop()
        errors = validate_testcase_model(data)
        self.assertTrue(any("SHARED_ENTRY_SCOPE_REQUIRES_SIX_OR_MORE" in item for item in errors))

    def test_six_entry_branches_must_switch_to_shared_scope(self):
        data = json.loads((ROOT / "tests/fixtures/models/testcase-model-multi-entry.json").read_text(encoding="utf-8"))
        case = data["cases"][0]
        source = case["entry_branches"][0]
        case["entry_branches"] = []
        for index in range(1, 7):
            branch = copy.deepcopy(source)
            branch["branch_id"] = f"TC001-B{index:02d}"
            branch["entry_name"] = f"真实业务弹窗{index}"
            branch["steps"] = [f"打开真实业务弹窗{index}并查询目标股票"]
            case["entry_branches"].append(branch)
        data["branch_count"] = 6
        errors = validate_testcase_model(data)
        self.assertTrue(any("SIX_OR_MORE_ENTRIES_REQUIRE_SHARED_SCOPE" in item for item in errors))

    def test_abbreviated_formal_entries_are_rejected(self):
        text = VALID_MARKDOWN.replace("                - 雷达股弹窗\n    - 功能测试", "                - 上述3个入口\n    - 功能测试")
        with self.assertRaisesRegex(ValidationError, "入口必须完整展开"):
            validate_markdown_text(text)

    def test_model_abbreviated_entries_are_rejected(self):
        data = self.model()
        data["shared_entry_scope"]["groups"][1]["subgroups"][0]["entries"][2]["entry_name"] = "上述3个入口"
        errors = validate_testcase_model(data)
        self.assertTrue(any("SHARED_ENTRY_SCOPE_ABBREVIATED" in item for item in errors))

    def test_scope_tc_mapping_must_be_exact(self):
        data = self.model()
        data["shared_entry_scope"]["applies_to_tc_ids"] = ["TC002"]
        errors = validate_testcase_model(data)
        self.assertTrue(any("SHARED_ENTRY_SCOPE_TC_MISMATCH" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
