from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_testcase_index import validate_index

HEADER = (
    "# 测试分析输出索引\n\n"
    "| 生成时间 | 来源类型 | 分析范围 | 规则版本 | 版本关系 | 校验状态 | 报告 | XMind Markdown | Workbook | Manifest | 备注 |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)


class TestcaseIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "RULE_VERSION").write_text("2.9.0\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("rules\n", encoding="utf-8")
        self.testcases = self.root / "testcases"
        self.testcases.mkdir()
        self.index = self.testcases / "index.md"

    def tearDown(self):
        self.temp.cleanup()

    def artifact(self, name: str, artifact_id: str, status: str = "passed") -> tuple[Path, list[str]]:
        directory = self.testcases / name
        directory.mkdir()
        paths: list[str] = []
        for filename in ("report.md", "case.xmind.md", "case.xmind"):
            path = directory / filename
            path.write_text("artifact\n", encoding="utf-8")
            paths.append(path.relative_to(self.root).as_posix())
        manifest = directory / "manifest.json"
        manifest.write_text(json.dumps({"artifact_id": artifact_id, "validation_status": status}), encoding="utf-8")
        paths.append(manifest.relative_to(self.root).as_posix())
        return manifest, paths

    def row(self, artifact_id: str, paths: list[str], status: str = "已校验") -> str:
        return (
            f"| 2026-07-18 00:00:00 | unit | REQ | 2.9.0 | 新增 | {status} | "
            f"{paths[0]} | {paths[1]} | {paths[2]} | {paths[3]} | artifact_id={artifact_id}; cases=1 |\n"
        )

    def test_passed_manifest_is_uniquely_registered(self):
        _, paths = self.artifact("a", "A")
        self.index.write_text(HEADER + self.row("A", paths), encoding="utf-8")
        self.assertEqual([], validate_index(self.index))

    def test_passed_manifest_missing_from_index_fails(self):
        self.artifact("a", "A")
        self.index.write_text(HEADER, encoding="utf-8")
        self.assertTrue(any("PASSED_MANIFEST_NOT_UNIQUELY_INDEXED" in error for error in validate_index(self.index)))

    def test_duplicate_artifact_id_and_manifest_path_fail(self):
        _, paths = self.artifact("a", "A")
        duplicate = self.row("A", paths) + self.row("A", paths)
        self.index.write_text(HEADER + duplicate, encoding="utf-8")
        errors = validate_index(self.index)
        self.assertTrue(any("artifact_id 重复" in error for error in errors))
        self.assertTrue(any("Manifest 重复" in error for error in errors))

    def test_passed_row_missing_formal_file_fails(self):
        _, paths = self.artifact("a", "A")
        paths[0] = "testcases/a/missing-report.md"
        self.index.write_text(HEADER + self.row("A", paths), encoding="utf-8")
        self.assertTrue(any("文件不存在" in error for error in validate_index(self.index)))

    def test_pending_manifest_does_not_require_registration(self):
        self.artifact("pending", "P", status="pending")
        self.index.write_text(HEADER, encoding="utf-8")
        self.assertEqual([], validate_index(self.index))


if __name__ == "__main__":
    unittest.main()
