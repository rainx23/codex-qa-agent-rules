from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_repository_docs import REQUIRED_README_DIRECTORIES, validate_repository, validate_skill_catalog


def create_repository(root: Path) -> None:
    (root / "RULE_VERSION").write_text("2.4.0\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(
        "# 版本历史\n\nRULE_VERSION 是唯一版本来源。\n\n"
        "## [2.4.0] - 2026-07-17\n\n### Added\n\n- Test.\n\n"
        "## [2.3.0] - 日期待确认\n\n### Baseline\n",
        encoding="utf-8",
    )
    rule = root / "rules/core/repository-documentation-rules.md"
    rule.parent.mkdir(parents=True, exist_ok=True)
    rule.write_text("小内容修改豁免\n不得根据当前文件状态编造历史版本\n历史信息不足\n", encoding="utf-8")
    for relative in REQUIRED_README_DIRECTORIES:
        path = root / relative / "README.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        extra = "\n自动生成\n" if relative == "rules/schemas" else ""
        path.write_text("# Test\n\n## 目录定位\n\nTest.\n\n## 维护约束\n\nTest.\n" + extra, encoding="utf-8")

    (root / ".codebuddy/skills").mkdir(parents=True, exist_ok=True)
    (root / "CODEBUDDY.md").write_text(
        "# CodeBuddy\n\n"
        "读取 AGENTS.md。\n\n"
        "包装入口位于 .codebuddy/skills/。\n\n"
        "发布前运行 scripts/validate_release.py。\n",
        encoding="utf-8",
    )


class RepositoryDocumentationTests(unittest.TestCase):
    def validate_fixture(self, mutate=None) -> list[str]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            create_repository(root)
            if mutate:
                mutate(root)
            return validate_repository(root)

    def test_valid_repository_passes(self):
        self.assertEqual([], self.validate_fixture())

    def test_missing_readme_fails(self):
        self.assertTrue(any("skills 缺少 README.md" in item for item in self.validate_fixture(lambda root: (root / "skills/README.md").unlink())))

    def test_empty_readme_fails(self):
        self.assertTrue(any("README.md 为空" in item for item in self.validate_fixture(lambda root: (root / "tests/README.md").write_text("", encoding="utf-8"))))

    def test_missing_changelog_fails(self):
        self.assertTrue(any("缺少 CHANGELOG.md" in item for item in self.validate_fixture(lambda root: (root / "CHANGELOG.md").unlink())))

    def test_missing_current_version_fails(self):
        self.assertTrue(any("缺少当前 RULE_VERSION" in item for item in self.validate_fixture(lambda root: (root / "CHANGELOG.md").write_text("RULE_VERSION\n## [2.3.0] - 2026-07-16\n", encoding="utf-8"))))

    def test_duplicate_version_fails(self):
        self.assertTrue(any("重复版本" in item for item in self.validate_fixture(lambda root: (root / "CHANGELOG.md").write_text((root / "CHANGELOG.md").read_text(encoding="utf-8") + "\n## [2.4.0] - 2026-07-16\n", encoding="utf-8"))))

    def test_invalid_version_format_fails(self):
        self.assertTrue(any("版本标题或日期格式错误" in item for item in self.validate_fixture(lambda root: (root / "CHANGELOG.md").write_text("RULE_VERSION\n## [2.4] - 2026-07-17\n", encoding="utf-8"))))

    def test_invalid_date_fails(self):
        self.assertTrue(any("日期不是" in item for item in self.validate_fixture(lambda root: (root / "CHANGELOG.md").write_text("RULE_VERSION\n## [2.4.0] - 2026/07/17\n", encoding="utf-8"))))

    def test_version_order_fails(self):
        self.assertTrue(any("未按从新到旧排序" in item for item in self.validate_fixture(lambda root: (root / "CHANGELOG.md").write_text("RULE_VERSION\n## [2.3.0] - 2026-07-16\n## [2.4.0] - 2026-07-17\n", encoding="utf-8"))))

    def test_readme_history_fails(self):
        self.assertTrue(any("独立完整版本历史" in item for item in self.validate_fixture(lambda root: (root / "skills/README.md").write_text("## 目录定位\n## 维护约束\n## [2.4.0]\n", encoding="utf-8"))))

    def test_schema_generation_boundary_is_required(self):
        self.assertTrue(any("自动生成" in item for item in self.validate_fixture(lambda root: (root / "rules/schemas/README.md").write_text("## 目录定位\n## 维护约束\n", encoding="utf-8"))))

    def test_governance_rule_contains_exemption_and_history_guards(self):
        self.assertTrue(any("缺少规则" in item for item in self.validate_fixture(lambda root: (root / "rules/core/repository-documentation-rules.md").write_text("", encoding="utf-8"))))

    def test_root_readme_skill_catalog_matches_actual_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("qa-one", "qa-two"):
                path = root / "skills" / name / "SKILL.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
            (root / "README.md").write_text(
                "# Test\n\n## 2 个 QA Skills\n\n"
                "- [one](skills/qa-one/SKILL.md)\n- [two](skills/qa-two/SKILL.md)\n",
                encoding="utf-8",
            )
            self.assertEqual([], validate_skill_catalog(root))
            (root / "README.md").write_text(
                "# Test\n\n## 2 个 QA Skills\n\n- [one](skills/qa-one/SKILL.md)\n",
                encoding="utf-8",
            )
            self.assertTrue(any("清单与实际" in item for item in validate_skill_catalog(root)))


if __name__ == "__main__":
    unittest.main()
