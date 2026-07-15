from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from md_to_xmind import convert_file, iter_inputs
from qa_validation import ValidationError, validate_xmind_archive


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.source = self.directory / "sample_xmind_20260715.md"
        self.source.write_text(
            (ROOT / "tests/fixtures/valid_case_xmind.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_20_conversion_success_and_failure(self):
        output = convert_file(self.source)
        result = validate_xmind_archive(output, "客户查询结果", 2, 13)
        self.assertEqual({"root": "客户查询结果", "tc_count": 2, "node_count": 13}, result)

        invalid = self.directory / "invalid_xmind_20260715.md"
        invalid.write_text("- 根\n        - 功能测试\n", encoding="utf-8")
        with self.assertRaises(ValidationError):
            convert_file(invalid)
        self.assertFalse(invalid.with_name("invalid_workbook_20260715.xmind").exists())

    def test_golden_topic_order(self):
        output = convert_file(self.source)
        with zipfile.ZipFile(output) as archive:
            content = json.loads(archive.read("content.json"))
        titles = []
        def walk(topic):
            titles.append(topic["title"])
            for child in topic.get("children", {}).get("attached", []):
                walk(child)
        walk(content[0]["rootTopic"])
        golden = json.loads((ROOT / "tests/golden/valid_case_topics.json").read_text(encoding="utf-8"))
        self.assertEqual(golden, titles)

    def test_existing_output_requires_overwrite(self):
        output = convert_file(self.source)
        with self.assertRaises(FileExistsError):
            convert_file(self.source)
        self.assertEqual(output, convert_file(self.source, overwrite=True))

    def test_batch_filters_reports_and_index(self):
        (self.directory / "index.md").write_text("# index", encoding="utf-8")
        (self.directory / "analysis_report.md").write_text("# report", encoding="utf-8")
        another = self.directory / "other_xmind.md"
        another.write_text(self.source.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual([another, self.source], list(iter_inputs([self.directory])))

    def test_utf8_bom_is_supported(self):
        content = self.source.read_text(encoding="utf-8")
        self.source.write_text(content, encoding="utf-8-sig")
        self.assertTrue(convert_file(self.source).is_file())


if __name__ == "__main__":
    unittest.main()

