from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validate_repository_docs import validate_codebuddy_adapter


class CodeBuddyAdapterValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="qa-codebuddy-adapter-"
        )
        self.root = Path(self.temporary_directory.name)
        self._create_valid_repository()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    def _create_valid_repository(self) -> None:
        self._write(
            self.root / "CODEBUDDY.md",
            "\n".join(
                [
                    "# CodeBuddy QA 测试分析总入口",
                    "",
                    "完整读取 AGENTS.md。",
                    "",
                    "原生包装入口位于 .codebuddy/skills/。",
                    "",
                    "发布前运行 scripts/validate_release.py。",
                    "",
                ]
            ),
        )

        for skill_name in ("qa-alpha", "qa-beta"):
            description = f"{skill_name} description"

            self._write(
                self.root / "skills" / skill_name / "SKILL.md",
                "\n".join(
                    [
                        "---",
                        f"name: {skill_name}",
                        f"description: {description}",
                        "---",
                        "",
                        f"# {skill_name}",
                        "",
                    ]
                ),
            )

            self._write(
                self.root / ".codebuddy" / "skills" / skill_name / "SKILL.md",
                "\n".join(
                    [
                        "---",
                        f"name: {skill_name}",
                        f"description: {description}",
                        "---",
                        "",
                        "# CodeBuddy Skill 适配入口",
                        "",
                        "完整读取并执行仓库根目录的正式 Skill：",
                        "",
                        f"skills/{skill_name}/SKILL.md",
                        "",
                        "上述文件是本 Skill 的唯一权威工作流正文。",
                        "",
                    ]
                ),
            )

    def test_current_repository_adapter_is_valid(self) -> None:
        self.assertEqual(validate_codebuddy_adapter(ROOT), [])

    def test_valid_adapter_passes(self) -> None:
        self.assertEqual(validate_codebuddy_adapter(self.root), [])

    def test_missing_wrapper_is_rejected(self) -> None:
        wrapper = (
            self.root
            / ".codebuddy"
            / "skills"
            / "qa-beta"
            / "SKILL.md"
        )
        wrapper.unlink()

        errors = validate_codebuddy_adapter(self.root)

        self.assertTrue(
            any("CodeBuddy Skill 包装清单与正式 Skill 不一致" in error for error in errors)
        )

    def test_description_mismatch_is_rejected(self) -> None:
        wrapper = (
            self.root
            / ".codebuddy"
            / "skills"
            / "qa-alpha"
            / "SKILL.md"
        )
        text = wrapper.read_text(encoding="utf-8")
        wrapper.write_text(
            text.replace(
                "description: qa-alpha description",
                "description: changed description",
            ),
            encoding="utf-8",
            newline="\n",
        )

        errors = validate_codebuddy_adapter(self.root)

        self.assertIn(
            "CodeBuddy Skill description 与正式 Skill 不一致：qa-alpha",
            errors,
        )

    def test_wrong_official_skill_reference_is_rejected(self) -> None:
        wrapper = (
            self.root
            / ".codebuddy"
            / "skills"
            / "qa-alpha"
            / "SKILL.md"
        )
        text = wrapper.read_text(encoding="utf-8")
        wrapper.write_text(
            text.replace(
                "skills/qa-alpha/SKILL.md",
                "skills/qa-other/SKILL.md",
            ),
            encoding="utf-8",
            newline="\n",
        )

        errors = validate_codebuddy_adapter(self.root)

        self.assertTrue(
            any("CodeBuddy Skill 未引用正式 Skill" in error for error in errors)
        )

    def test_missing_codebuddy_entry_is_rejected(self) -> None:
        (self.root / "CODEBUDDY.md").unlink()

        errors = validate_codebuddy_adapter(self.root)

        self.assertIn("缺少 CodeBuddy 总入口 CODEBUDDY.md", errors)


if __name__ == "__main__":
    unittest.main()