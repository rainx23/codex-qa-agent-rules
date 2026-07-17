#!/usr/bin/env python3
"""Safe Schema 1.0.0 -> 2.0.0 migration CLI."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from migration_contracts import FROM_VERSION, TO_VERSION, detect_model_type, migrate_document, serialize_json


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        json.loads(Path(temporary).read_text(encoding="utf-8"))
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def report_for(source: Path, destination: Path, source_raw: bytes, destination_raw: bytes, result: Any, written: bool) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    model_type = detect_model_type(result.data)
    return {
        "migration_report_version": "1.0.0",
        "migration_id": "MIG-" + hashlib.sha256((str(source.resolve()) + digest(source_raw)).encode()).hexdigest()[:12].upper(),
        "from_schema_version": FROM_VERSION,
        "to_schema_version": TO_VERSION,
        "started_at": now,
        "completed_at": now,
        "status": result.status,
        "source_path": source.as_posix(),
        "destination_path": destination.as_posix(),
        "source_hash": digest(source_raw),
        "destination_hash": digest(destination_raw),
        "destination_written": written,
        "model_type": model_type,
        "changes": result.changes,
        "unknown_fields": result.unknown_fields,
        "reconfirm_required": result.reconfirm_required,
        "dropped_fields": result.dropped_fields,
        "validation_results": result.validation_results,
        "warnings": result.warnings,
        "errors": result.errors,
    }


def migrate_one(source: Path, destination: Path, dry_run: bool, strict: bool = False) -> tuple[dict[str, Any], bytes]:
    source_raw = source.read_bytes()
    data = json.loads(source_raw.decode("utf-8-sig"))
    result = migrate_document(data)
    destination_raw = serialize_json(result.data)
    if strict and result.status == "pending":
        raise ValueError("strict migration rejects pending/reconfirm-required output")
    if not dry_run:
        atomic_write(destination, destination_raw)
    return report_for(source, destination, source_raw, destination_raw, result, not dry_run), destination_raw


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    source = value.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--input-dir", type=Path)
    destination = value.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--output-dir", type=Path)
    value.add_argument("--report", required=True, type=Path)
    value.add_argument("--from-version", default=FROM_VERSION)
    value.add_argument("--to-version", default=TO_VERSION)
    value.add_argument("--dry-run", action="store_true")
    value.add_argument("--in-place", action="store_true")
    mode = value.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true")
    mode.add_argument("--best-effort", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if (args.from_version, args.to_version) != (FROM_VERSION, TO_VERSION):
        parser().error("only migration 1.0.0 -> 2.0.0 is supported")
    if args.input and not (args.output or args.in_place):
        parser().error("--input requires --output or --in-place")
    if args.input_dir and not args.output_dir:
        parser().error("--input-dir requires --output-dir")
    if args.output and args.input_dir or args.output_dir and args.input:
        parser().error("single-file and directory arguments cannot be mixed")
    if args.in_place and not args.input:
        parser().error("--in-place is single-file only")
    reports: list[dict[str, Any]] = []
    written: list[Path] = []
    try:
        if args.input:
            source = args.input.resolve()
            if not source.is_file(): raise ValueError(f"input file does not exist: {source}")
            destination = source if args.in_place else args.output.resolve()
            if destination == source and not args.in_place: raise ValueError("source and destination require --in-place")
            report, _ = migrate_one(source, destination, args.dry_run, args.strict)
            reports.append(report)
            if not args.dry_run: written.append(destination)
        else:
            source_dir = args.input_dir.resolve()
            if not source_dir.is_dir(): raise ValueError(f"input directory does not exist: {source_dir}")
            destination_dir = args.output_dir.resolve()
            staged: list[tuple[Path, Path, dict[str, Any], bytes]] = []
            priority = {"requirement_analysis": 0, "diff_impact": 1, "risk_coverage_matrix": 2, "testcase_model": 3, "validation_sql": 4, "api_automation": 4, "api_automation_artifact": 5, "execution_model": 6, "knowledge_table": 7, "artifact_manifest": 8}
            sources = list(source_dir.rglob("*.json"))
            sources.sort(key=lambda path: priority[detect_model_type(json.loads(path.read_text(encoding="utf-8-sig")))])
            for source in sources:
                target = destination_dir / source.relative_to(source_dir)
                source_raw = source.read_bytes()
                result = migrate_document(json.loads(source_raw.decode("utf-8-sig")))
                if args.strict and result.status == "pending":
                    raise ValueError(f"strict migration rejects pending output: {source}")
                raw = serialize_json(result.data)
                staged.append((source, target, report_for(source, target, source_raw, raw, result, not args.dry_run), raw))
            if not args.dry_run:
                for _, target, _, raw in staged:
                    atomic_write(target, raw); written.append(target)
            reports = [item[2] for item in staged]
        status = "unchanged" if reports and all(x["status"] == "unchanged" for x in reports) else ("pending" if any(x["status"] == "pending" for x in reports) else "passed")
        aggregate = reports[0] if len(reports) == 1 else {
            "migration_report_version": "1.0.0", "migration_id": "MIG-BUNDLE-" + hashlib.sha256("".join(x["source_hash"] for x in reports).encode()).hexdigest()[:12].upper(),
            "from_schema_version": FROM_VERSION, "to_schema_version": TO_VERSION, "status": status, "model_type": "bundle",
            "source_path": args.input_dir.as_posix(), "destination_path": args.output_dir.as_posix(),
            "source_hash": digest("".join(x["source_hash"] for x in reports).encode()), "destination_hash": digest("".join(x["destination_hash"] for x in reports).encode()),
            "destination_written": not args.dry_run, "changes": [c for x in reports for c in x["changes"]], "unknown_fields": [c for x in reports for c in x["unknown_fields"]],
            "reconfirm_required": [c for x in reports for c in x["reconfirm_required"]], "dropped_fields": [c for x in reports for c in x["dropped_fields"]],
            "validation_results": [c for x in reports for c in x["validation_results"]], "warnings": [], "errors": [], "files": reports,
        }
        atomic_write(args.report.resolve(), serialize_json(aggregate))
        counts = {action: sum(1 for change in aggregate["changes"] if change["action"] == action) for action in ("copied", "renamed", "transformed", "defaulted", "unknown", "reconfirm_required", "dropped")}
        print(f"Model: {aggregate['model_type']}\nSource: {aggregate['source_path']}\nDestination: {aggregate['destination_path']}\nStatus: {status}")
        print(" ".join(f"{key.title()}: {value}" for key, value in counts.items()) + f" Validation Errors: {len(aggregate['errors'])}")
        return 0
    except Exception as error:
        for path in written:
            if not args.in_place: path.unlink(missing_ok=True)
        failure = {"migration_report_version": "1.0.0", "migration_id": "MIG-FAILED", "from_schema_version": FROM_VERSION, "to_schema_version": TO_VERSION,
                   "status": "failed", "model_type": "unknown", "source_path": str(args.input or args.input_dir), "destination_path": str(args.output or args.output_dir or args.input),
                   "source_hash": "sha256:" + "0" * 64, "destination_hash": "sha256:" + "0" * 64, "destination_written": False,
                   "changes": [], "unknown_fields": [], "reconfirm_required": [], "dropped_fields": [], "validation_results": [], "warnings": [], "errors": [str(error)]}
        try: atomic_write(args.report.resolve(), serialize_json(failure))
        except Exception: pass
        print(f"FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
