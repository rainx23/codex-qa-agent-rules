from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from zentao_requirement_sections import select_zentao_acceptance_basis

FIXTURES = ROOT / "tests/fixtures/zentao"


class ZentaoProfileTests(unittest.TestCase):
    def load(self, name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    def test_first_and_third_parts_consistent(self):
        result = select_zentao_acceptance_basis(self.load("consistent.md"))
        self.assertEqual("product-plan", result.basis_kind)
        self.assertIn("精确匹配", result.acceptance_basis)
        self.assertFalse(result.blocking)

    def test_ordinary_difference_uses_third_part(self):
        result = select_zentao_acceptance_basis(self.load("background_differs.md"))
        self.assertIn("客户名称模糊搜索", result.background)
        self.assertIn("客户编号精确匹配", result.acceptance_basis)
        self.assertFalse(result.blocking)

    def test_goal_deviation_is_a_risk_not_an_automatic_block(self):
        result = select_zentao_acceptance_basis(self.load("goal_deviation.md"))
        self.assertTrue(any("业务目标偏差风险" in risk for risk in result.risks))
        self.assertFalse(result.blocking)

    def test_internal_product_conflict_blocks(self):
        result = select_zentao_acceptance_basis(self.load("product_conflict.md"))
        self.assertTrue(result.blocking)
        self.assertTrue(any("相反口径" in question for question in result.questions))

    def test_missing_third_part_uses_explicit_alternative(self):
        result = select_zentao_acceptance_basis(self.load("missing_with_alternative.md"))
        self.assertEqual("alternative-rule", result.basis_kind)
        self.assertIn("精确匹配", result.acceptance_basis)
        self.assertFalse(result.blocking)

    def test_missing_third_part_and_core_rules_blocks(self):
        result = select_zentao_acceptance_basis(self.load("missing_core.md"))
        self.assertEqual("missing", result.basis_kind)
        self.assertTrue(result.blocking)

    def test_user_requested_first_part_has_highest_priority(self):
        result = select_zentao_acceptance_basis(self.load("user_scope.md"), requested_scope="第一部分")
        self.assertEqual("user-specified", result.basis_kind)
        self.assertIn("历史问题", result.acceptance_basis)

    def test_chinese_numeric_and_parenthesized_product_titles(self):
        titles = (
            "三、产品实现方案、规则",
            "3、产品实现方案、规则",
            "三. 产品实现方案、规则",
            "3. 产品实现方案、规则",
            "三．产品实现方案、规则",
            "3．产品实现方案、规则",
            "（三）产品实现方案、规则",
            "(三) 产品实现方案、规则",
            "（3）产品实现方案、规则",
            "(3) 产品实现方案、规则",
            "三 产品实现方案、规则",
            "3 产品实现方案、规则",
        )
        for title in titles:
            result = select_zentao_acceptance_basis(f"# 一、需求背景\n\n目标。\n\n# {title}\n\n- 规则：精确匹配\n")
            self.assertEqual("product-plan", result.basis_kind, title)

    def test_near_product_title_is_supported(self):
        result = select_zentao_acceptance_basis(self.load("near_title.md"))
        self.assertEqual("product-plan", result.basis_kind)
        self.assertIn("精确匹配", result.acceptance_basis)


if __name__ == "__main__":
    unittest.main()
