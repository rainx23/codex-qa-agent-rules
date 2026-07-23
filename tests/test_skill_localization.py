from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillLocalizationTests(unittest.TestCase):
    def test_all_skills_keep_machine_identifiers_and_use_chinese_descriptions(self):
        skills_root = ROOT / "skills"
        skill_dirs = sorted(path for path in skills_root.iterdir() if path.is_dir())
        self.assertEqual(6, len(skill_dirs))
        for skill_dir in skill_dirs:
            skill_file = skill_dir / "SKILL.md"
            text = skill_file.read_text(encoding="utf-8")
            self.assertRegex(text, r"^---\nname: [a-z0-9-]+\ndescription: .+\n---\n")
            frontmatter = text.split("---\n", 2)[1]
            values = dict(
                line.split(":", 1) for line in frontmatter.splitlines() if ":" in line
            )
            self.assertEqual(skill_dir.name, values["name"].strip())
            self.assertRegex(values["description"], r"[\u4e00-\u9fff]")
            self.assertRegex(values["description"], r"[A-Za-z]")
            self.assertRegex(text, r"[\u4e00-\u9fff]")

            agent = (skill_dir / "agents" / "openai.yaml").read_text(encoding="utf-8")
            self.assertIn("interface:", agent)
            for field in ("display_name:", "short_description:", "default_prompt:"):
                self.assertRegex(agent, rf"(?m)^\s*{re.escape(field)}\s*\S")
            self.assertIn(f"${skill_dir.name}", agent)

    def test_chinese_and_english_trigger_words_are_retained(self):
        expected = {
            "qa-requirement-analysis": (("需求", "分析"), ("Requirement analysis", "Markdown")),
            "qa-diff-impact-analysis": (("Diff", "影响"), ("Diff impact analysis", "commit")),
            "qa-testcase-design": (("测试用例", "XMind"), ("Testcase design", "XMind Markdown")),
            "qa-artifact-validation": (("校验", "产物"), ("Artifact validation", "manifest")),
            "qa-knowledge-management": (("知识", "DDL"), ("Knowledge management", "DDL")),
            "qa-api-automation": (("接口自动化", "参数化"), ("API automation", "parameterization")),
        }
        for name, (chinese_words, english_words) in expected.items():
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            description = text.split("description: ", 1)[1].split("\n", 1)[0]
            self.assertTrue(any(word in description for word in chinese_words), name)
            self.assertTrue(any(word in description for word in english_words), name)


if __name__ == "__main__":
    unittest.main()
