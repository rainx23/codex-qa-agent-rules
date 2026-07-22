from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from file_hash_utils import stable_file_content_hash, stable_multi_file_hash  # noqa: E402
from validate_evidence import (  # noqa: E402
    validate_evidence_reference,
    validate_evidence_references,
)

REQUIREMENT_HASH = "sha256:f18b428754d35a54896bca7fdc32d51291720d95731f614cda782bc6c30ef3a2"
TEXT_LF = b"line one\nobservable value\nline three\n"


class FileHashUtilsTests(unittest.TestCase):
    def evidence(self, content_hash: str) -> dict:
        return {
            "source_type": "requirement",
            "storage_type": "file",
            "source_path": "tests/fixtures/sources/requirement.md",
            "snapshot_path": None,
            "source_record_id": "REQ-001",
            "line_start": 2,
            "line_end": 2,
            "commit_sha": None,
            "content_hash": content_hash,
            "excerpt": "observable value",
            "captured_at": "2026-07-17 00:00:00",
            "captured_timezone": "Asia/Shanghai",
            "evidence_status": "current",
        }

    def write_evidence(self, root: Path, content: bytes) -> Path:
        path = root / "tests" / "fixtures" / "sources" / "requirement.md"
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        return path

    def test_text_hash_is_identical_for_lf_crlf_and_cr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "lf.md", root / "crlf.md", root / "cr.md"]
            for path, content in zip(
                paths,
                (TEXT_LF, TEXT_LF.replace(b"\n", b"\r\n"), TEXT_LF.replace(b"\n", b"\r")),
            ):
                path.write_bytes(content)
            hashes = [
                stable_file_content_hash(path, normalize_text_newlines=True)
                for path in paths
            ]
        self.assertEqual([hashes[0]] * 3, hashes)

    def test_normalized_text_hash_matches_requirement_fixture(self):
        actual = stable_file_content_hash(
            ROOT / "tests" / "fixtures" / "sources" / "requirement.md",
            normalize_text_newlines=True,
        )
        self.assertEqual(REQUIREMENT_HASH, actual)

    def test_crlf_evidence_is_authentic_and_current(self):
        expected = "sha256:" + hashlib.sha256(TEXT_LF).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_evidence(root, TEXT_LF.replace(b"\n", b"\r\n"))
            evidence = self.evidence(expected)
            self.assertEqual([], validate_evidence_reference(evidence, root=root, confirmed=True))
            self.assertEqual([], validate_evidence_references([evidence], label="risk", root=root, confirmed=True))

    def test_cr_evidence_is_authentic_and_current(self):
        expected = "sha256:" + hashlib.sha256(TEXT_LF).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_evidence(root, TEXT_LF.replace(b"\n", b"\r"))
            evidence = self.evidence(expected)
            self.assertEqual([], validate_evidence_reference(evidence, root=root, confirmed=True))
            self.assertEqual([], validate_evidence_references([evidence], label="risk", root=root, confirmed=True))

    def test_text_content_change_is_still_rejected(self):
        expected = "sha256:" + hashlib.sha256(TEXT_LF).hexdigest()
        changed = TEXT_LF.replace(b"observable value", b"observable changed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_evidence(root, changed.replace(b"\n", b"\r\n"))
            evidence = self.evidence(expected)
            evidence["excerpt"] = "observable changed"
            errors = validate_evidence_reference(evidence, root=root, confirmed=True)
        self.assertTrue(any("current Evidence content_hash 与文件不一致" in error for error in errors), errors)

    def test_binary_hash_preserves_every_raw_byte(self):
        original = b"\x00\r\n\x01\r\x02"
        changed = b"\x00\r\n\x01\r\x03"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_path = root / "original.png"
            changed_path = root / "changed.png"
            original_path.write_bytes(original)
            changed_path.write_bytes(changed)
            original_hash = stable_file_content_hash(original_path, normalize_text_newlines=False)
            changed_hash = stable_file_content_hash(changed_path, normalize_text_newlines=False)
        self.assertEqual("sha256:" + hashlib.sha256(original).hexdigest(), original_hash)
        self.assertNotEqual(original_hash, changed_hash)

    def test_source_hash_normalizes_lf_crlf_cr_and_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = (TEXT_LF, TEXT_LF.replace(b"\n", b"\r\n"), TEXT_LF.replace(b"\n", b"\r"), b"\xef\xbb\xbf" + TEXT_LF)
            hashes = []
            for index, content in enumerate(values):
                path = root / "source.md"
                path.write_bytes(content)
                hashes.append(stable_multi_file_hash(root, ["source.md"]))
            self.assertEqual([hashes[0]] * len(hashes), hashes)

    def test_multi_file_source_hash_is_order_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.md").write_bytes(b"a\r\n")
            (root / "b.md").write_bytes(b"b\r")
            self.assertEqual(
                stable_multi_file_hash(root, ["a.md", "b.md"]),
                stable_multi_file_hash(root, ["b.md", "a.md"]),
            )

    def test_source_hash_changes_for_binary_byte_or_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.xmind").write_bytes(b"\x00\r\n\x01")
            original = stable_multi_file_hash(root, ["a.xmind"])
            (root / "a.xmind").write_bytes(b"\x00\r\n\x02")
            self.assertNotEqual(original, stable_multi_file_hash(root, ["a.xmind"]))
            (root / "b.xmind").write_bytes(b"\x00\r\n\x01")
            self.assertNotEqual(original, stable_multi_file_hash(root, ["b.xmind"]))

    def test_windows_and_posix_source_paths_are_equivalent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "nested" / "source.md"
            path.parent.mkdir()
            path.write_bytes(TEXT_LF)
            self.assertEqual(
                stable_multi_file_hash(root, ["nested/source.md"]),
                stable_multi_file_hash(root, [r"nested\source.md"]),
            )


if __name__ == "__main__":
    unittest.main()
