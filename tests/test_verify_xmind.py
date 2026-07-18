from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from md_to_xmind import convert_file
from verify_xmind import main as verify_main

MARKDOWN = ROOT / "tests/fixtures/valid_case_xmind.md"
CURRENT_MARKDOWN = ROOT / "testcases/clearance-permission-20260718/clearance-permission.xmind.md"


class VerifyXMindTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workbook = Path(self.temp.name) / "case.xmind"
        convert_file(MARKDOWN, self.workbook)

    def tearDown(self):
        self.temp.cleanup()

    def topics(self, topic: dict) -> list[dict]:
        return [topic, *(item for child in topic.get("children", {}).get("attached", []) for item in self.topics(child))]

    def rewrite(self, mutate) -> None:
        with zipfile.ZipFile(self.workbook) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        content = json.loads(entries["content.json"].decode("utf-8"))
        mutate(content[0]["rootTopic"])
        entries["content.json"] = json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
        with zipfile.ZipFile(self.workbook, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in entries.items():
                archive.writestr(name, payload)

    def verify(self, markdown: Path = MARKDOWN) -> int:
        return verify_main([str(self.workbook), "--markdown", str(markdown)])

    def test_identical_and_current_real_workbooks_pass(self):
        self.assertEqual(0, self.verify())
        self.assertEqual(0, verify_main([
            str(ROOT / "testcases/clearance-permission-20260718/clearance-permission.xmind"),
            "--markdown", str(ROOT / "testcases/clearance-permission-20260718/clearance-permission.xmind.md"),
        ]))

    def test_same_node_count_but_step_or_expected_title_change_fails(self):
        for original in ("输入已确认的客户编号并查询", "返回集合仅包含该客户编号对应记录"):
            with self.subTest(original=original):
                convert_file(MARKDOWN, self.workbook, overwrite=True)
                self.rewrite(lambda root: next(item for item in self.topics(root) if item["title"] == original).__setitem__("title", original + "-changed"))
                self.assertEqual(1, self.verify())

    def test_tc_and_child_order_changes_fail(self):
        convert_file(CURRENT_MARKDOWN, self.workbook, overwrite=True)
        def swap_tc(root):
            parent = next(
                item
                for item in self.topics(root)
                if {"TC001", "TC002"}.issubset(
                    {child.get("title") for child in item.get("children", {}).get("attached", [])}
                )
            )
            parent["children"]["attached"].reverse()
        self.rewrite(swap_tc)
        self.assertEqual(1, self.verify(CURRENT_MARKDOWN))
        convert_file(MARKDOWN, self.workbook, overwrite=True)
        def swap_children(root):
            parent = next(
                item
                for item in self.topics(root)
                if len(item.get("children", {}).get("attached", [])) >= 2
            )
            parent["children"]["attached"][:2] = reversed(parent["children"]["attached"][:2])
        self.rewrite(swap_children)
        self.assertEqual(1, self.verify())

    def test_node_move_to_other_parent_fails_with_same_total(self):
        def move(root):
            tc1 = next(item for item in self.topics(root) if item["title"] == "TC001")
            tc2 = next(item for item in self.topics(root) if item["title"] == "TC002")
            moved = tc1["children"]["attached"].pop()
            tc2["children"]["attached"].append(moved)
        self.rewrite(move)
        self.assertEqual(1, self.verify())

    def test_missing_and_added_node_fail(self):
        self.rewrite(lambda root: root["children"]["attached"].pop())
        self.assertEqual(1, self.verify())
        convert_file(MARKDOWN, self.workbook, overwrite=True)
        self.rewrite(lambda root: root["children"]["attached"].append({"title": "额外节点"}))
        self.assertEqual(1, self.verify())

    def test_corrupt_zip_fails(self):
        self.workbook.write_bytes(b"not-a-zip")
        self.assertEqual(1, self.verify())


if __name__ == "__main__":
    unittest.main()
