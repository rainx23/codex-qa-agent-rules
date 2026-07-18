from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import compute_core_deduplication_key, validate_testcase_model


MODELS = ROOT / "tests" / "fixtures" / "models"


class EntryBranchDeduplicationTests(unittest.TestCase):
    def load(self, name: str = "testcase-model-multi-entry.json") -> dict:
        return json.loads((MODELS / name).read_text(encoding="utf-8"))

    def factors(self, **overrides: str) -> dict[str, str]:
        values = {
            "business_object": "清仓股股票行",
            "trigger_condition": "配置权限后打开清仓股弹窗",
            "core_action": "查询权限命中股票",
            "core_assertion": "命中股票可见且不命中股票不可见",
            "risk_semantics": "无权限数据泄露",
            "data_source": "清仓股权限查询",
            "permission_rule": "同一权限规则",
            "calculation_basis": "股票行可见性",
            "exception_handling": "同一异常处理",
        }
        values.update(overrides)
        return values

    def add_core(self, case: dict, **overrides: str) -> None:
        factors = self.factors(**overrides)
        case["core_deduplication_factors"] = factors
        case["core_deduplication_key"] = compute_core_deduplication_key(factors)
        for branch in case.get("entry_branches", []):
            branch["steps"] = [f"打开{branch['entry_name']}并准备权限命中与不命中股票"]

    def test_one_tc_with_two_real_entry_branches_passes(self):
        data = self.load()
        self.add_core(data["cases"][0])
        self.assertEqual([], validate_testcase_model(data))

    def test_entry_only_split_fails(self):
        data = self.load("testcase-model.json")
        first = data["cases"][0]
        self.add_core(first)
        second = copy.deepcopy(first)
        second["tc_id"] = "TC002"
        second["steps"] = ["打开正式交易清仓股弹窗并准备权限命中与不命中股票"]
        data["cases"] = [first, second]
        errors = validate_testcase_model(data)
        self.assertTrue(any("DUPLICATE_TC_SPLIT_BY_ENTRY_ONLY" in item for item in errors))
        self.assertTrue(any("IDENTICAL_RULE_NOT_MERGED_TO_ENTRY_BRANCHES" in item for item in errors))

    def test_different_oracle_allows_split(self):
        data = self.load("testcase-model.json")
        first = data["cases"][0]
        self.add_core(first, core_assertion="股票行不可见")
        second = copy.deepcopy(first)
        second["tc_id"] = "TC002"
        self.add_core(second, core_assertion="接口返回明确错误码")
        data["cases"] = [first, second]
        self.assertEqual([], validate_testcase_model(data))

    def test_different_data_source_allows_split(self):
        data = self.load("testcase-model.json")
        first = data["cases"][0]
        self.add_core(first, data_source="模拟交易独立查询链路")
        second = copy.deepcopy(first)
        second["tc_id"] = "TC002"
        self.add_core(second, data_source="正式交易独立查询链路")
        data["cases"] = [first, second]
        self.assertEqual([], validate_testcase_model(data))

    def test_different_exception_handling_allows_split(self):
        data = self.load("testcase-model.json")
        first = data["cases"][0]
        self.add_core(first, exception_handling="超时后重试")
        second = copy.deepcopy(first)
        second["tc_id"] = "TC002"
        self.add_core(second, exception_handling="超时后直接报错")
        data["cases"] = [first, second]
        self.assertEqual([], validate_testcase_model(data))

    def test_tampered_core_key_fails(self):
        data = self.load()
        self.add_core(data["cases"][0])
        data["cases"][0]["core_deduplication_key"] = "sha256:" + "0" * 64
        self.assertTrue(any("确定性计算结果不一致" in item for item in validate_testcase_model(data)))


if __name__ == "__main__":
    unittest.main()
