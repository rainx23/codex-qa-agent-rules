from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from parse_chat_ddl import parse_ddl
from qa_contracts import load_json, summarize_confirmations, validate_api_automation, validate_diff_model, validate_knowledge_table, validate_requirement_model, validate_testcase_model, validate_validation_sql
from validate_evidence import validate_evidence_reference
from validate_manifest import validate_manifest_data

FIXTURES = ROOT / "tests/fixtures/anti_hallucination"


def set_path(data: dict, path: str, value=None, remove: bool = False) -> None:
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    if remove:
        current.pop(parts[-1], None)
    else:
        current[parts[-1]] = value


def get_path(data: dict, path: str):
    current = data
    for part in path.split("."):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


class AntiHallucinationFixtureTests(unittest.TestCase):
    def test_all_categories_have_valid_invalid_reason_and_golden(self):
        expected = {
            "confirmed_inference", "blocking_gate", "ddl_partial", "vague_assertion",
            "missing_evidence", "fake_identifier", "suspected_defect", "api_health_scope",
            "core_missing_confirmation", "pending_state_machine", "pending_draft_manifest",
            "evidence_nonexistent_path", "evidence_absolute_path", "evidence_hash_mismatch",
            "evidence_excerpt_mismatch", "zentao_snapshot_required",
            "user_confirmation_snapshot", "screenshot_authenticity",
            "diff_evidence_file_match",
            "ddl_default_null_nullable", "ddl_multi_constraint_consumption",
            "ddl_comment_constraint_isolation", "ddl_generated_column_preservation",
            "ddl_unparsed_tail", "ddl_complete_contract",
            "report_strict_mode_bypass", "report_fake_fact_id", "report_fake_risk_id", "report_missing_core_trace",
            "risk_vague_assertion", "risk_merged_target", "risk_merged_cycle", "risk_blocked_confirmation",
            "risk_deferred_contract", "risk_accepted_contract", "risk_not_applicable_contract",
            "diff_risk_consistency", "risk_testcase_bidirectional",
            "sql_identifier_missing_source_type", "sql_identifier_fake_fact", "sql_identifier_missing_column",
            "sql_identifier_cross_table_field", "sql_identifier_partial_ddl", "sql_identifier_unproven_enum",
            "sql_identifier_unknown_function", "sql_identifier_join_relation", "sql_identifier_unused_evidence",
            "sql_cli_missing_context", "sql_ci_context_required",
            "api_validation_array_bypass", "api_validation_non_object", "api_health_extra_check",
            "api_health_wrong_path", "api_health_wrong_type", "api_business_assertion_forbidden",
            "api_artifact_missing_model", "api_artifact_model_mismatch", "api_script_assertion_swallowed",
            "api_script_default_value_bypass", "api_ci_model_required", "api_rule_protocol_fixed",
            "execution_missing_required_counts", "execution_fake_testcase_branch", "execution_not_run_with_defect",
            "execution_passed_without_evidence", "execution_failed_fake_defect", "execution_blocked_fake_confirmation",
            "execution_skipped_without_decision", "execution_rerun_cross_branch", "execution_rerun_cycle",
            "execution_evidence_hash_mismatch", "execution_manifest_unpassed_core", "execution_ci_context_required",
            "migration_version_only", "migration_confirmed_without_evidence", "migration_conflict_auto_resolved",
            "migration_risk_auto_accepted", "migration_sql_field_auto_confirmed", "migration_api_protocol_rewritten",
            "migration_execution_passed_without_evidence", "migration_unknown_field_dropped", "migration_non_idempotent",
            "migration_partial_write", "migration_bundle_broken_reference", "migration_ci_missing_validation",
            "rule_zentao_priority_conflict", "rule_pending_failed_conflict", "rule_api_protocol_conflict",
            "rule_sql_identifier_weak_description", "rule_execution_history_conflict",
            "rule_migration_version_only_description", "fixture_in_source_directory", "rule_reference_missing_file",
        }
        self.assertEqual(expected, {path.stem for path in FIXTURES.glob("*.json")})
        for path in FIXTURES.glob("*.json"):
            spec = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("expected_failure", spec, path.name)
            self.assertIn("golden", spec, path.name)
            self.assert_fixture(spec, path.name)

    def assert_fixture(self, spec: dict, name: str) -> None:
        kind = spec["kind"]
        if kind == "fifth_batch_contract":
            # These catalog entries are paired with executable cases in
            # test_analysis_report.py and test_structured_models.py.
            self.assertTrue(spec["golden"]["validator_rejects_invalid"], name)
            self.assertTrue(spec["expected_failure"], name)
            return
        if kind == "ddl":
            self.assertEqual(spec["golden"]["valid_scope"], parse_ddl(spec["valid_input"])["tables"][0]["schema_scope"])
            self.assertEqual(spec["golden"]["invalid_scope"], parse_ddl(spec["invalid_input"])["tables"][0]["schema_scope"])
            return
        if kind == "ddl_contract":
            valid_result = parse_ddl(spec["valid_input"])
            self.assertTrue(valid_result["tables"], name)
            table = valid_result["tables"][0]
            for path, expected in spec["golden"]["values"].items():
                self.assertEqual(expected, get_path(table, path), f"{name}: {path}")
            invalid_result = parse_ddl(spec["invalid_input"])
            messages = list(invalid_result["warnings"])
            for invalid_table in invalid_result["tables"]:
                messages.extend(invalid_table.get("parse_warnings", []))
            self.assertTrue(any(spec["expected_failure"] in message for message in messages), name)
            return
        if kind == "ddl_schema":
            table = parse_ddl(spec["valid_input"])["tables"][0]
            self.assertEqual([], validate_knowledge_table(table), name)
            invalid = copy.deepcopy(table)
            set_path(invalid, spec["invalid"]["remove"], remove=True)
            self.assertTrue(any(
                spec["expected_failure"] in error for error in validate_knowledge_table(invalid)
            ), name)
            return
        if kind == "evidence":
            if "base" in spec:
                model = load_json(ROOT / spec["base"])
                valid = copy.deepcopy(get_path(model, spec["evidence_path"]))
                valid.update(spec.get("valid", {}))
            else:
                valid = copy.deepcopy(spec["valid"])
            self.assertEqual([], validate_evidence_reference(valid, root=ROOT, confirmed=True), name)
            invalid = copy.deepcopy(valid)
            invalid.update(spec["invalid"])
            self.assertTrue(any(
                spec["expected_failure"] in error
                for error in validate_evidence_reference(invalid, root=ROOT, confirmed=True)
            ), name)
            return
        if kind == "diff_evidence":
            data = load_json(ROOT / spec["base"])
            self.assertEqual([], validate_diff_model(data), name)
            invalid = copy.deepcopy(data)
            invalid["change_items"][0]["evidence_references"][0].update(spec["invalid"])
            self.assertTrue(any(
                spec["expected_failure"] in error for error in validate_diff_model(invalid)
            ), name)
            return
        data = load_json(ROOT / spec["base"])
        if kind == "requirement_state":
            missing = copy.deepcopy(data["facts"][0])
            missing.update(fact_id="FACT-003", category="missing", handling="等待产品确认")
            data["facts"].append(missing)
            data["confirmation_points"] = [{
                "confirmation_id": "CONF-001", "severity": "blocking", "statement": "确认核心口径",
                "fact_ids": ["FACT-003"], "status": "pending",
            }]
            self.assertEqual([], validate_requirement_model(data), name)
            data["confirmation_points"] = []
            self.assertTrue(any(spec["expected_failure"] in error for error in validate_requirement_model(data)), name)
            return
        if kind == "confirmation_summary":
            missing = copy.deepcopy(data["facts"][0])
            missing.update(fact_id="FACT-003", category="missing", handling="等待产品确认")
            data["facts"].append(missing)
            evidence = copy.deepcopy(data["facts"][0]["evidence_references"])
            data["confirmation_points"] = [
                {"confirmation_id":"CONF-001","severity":"blocking","statement":"核心待确认","fact_ids":["FACT-003"],"status":"pending"},
                {"confirmation_id":"CONF-002","severity":"nonblocking","statement":"边界待确认","fact_ids":["FACT-001"],"status":"pending"},
                {"confirmation_id":"CONF-003","severity":"suggested","statement":"文案待确认","fact_ids":["FACT-002"],"status":"pending"},
                {"confirmation_id":"CONF-004","severity":"blocking","statement":"已解决","fact_ids":["FACT-001"],"status":"resolved","resolution":"沿用原文","resolution_evidence_references":evidence,"resolved_at":"2026-07-17 12:00:00"},
                {"confirmation_id":"CONF-005","severity":"blocking","statement":"跳过核心口径","fact_ids":["FACT-003"],"status":"skipped","skip_reason":"下一版本确认","decision_evidence":copy.deepcopy(evidence)},
            ]
            self.assertEqual(spec["golden"], summarize_confirmations(data), name)
            return
        if kind == "pending_manifest_state":
            valid = copy.deepcopy(data)
            valid.update(spec["valid"])
            self.assertEqual("pending", valid["validation_status"])
            self.assertTrue(valid["pending_reason"])
            self.assertTrue(all(valid[field] is None for field in (
                "report_path", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path",
            )))
            self.assertTrue(all(str(valid[field]).startswith("tests/fixtures/drafts/") for field in (
                "draft_report_path", "draft_risk_matrix_path", "draft_testcase_model_path",
            )))
            invalid = copy.deepcopy(valid)
            invalid.update(spec["invalid"])
            self.assertTrue(any(
                spec["expected_failure"] in error
                for error in validate_manifest_data(invalid, ROOT / spec["base"])
            ), name)
            return
        validators = {"requirement": validate_requirement_model, "testcase": validate_testcase_model, "api": validate_api_automation}
        if kind in validators:
            self.assertEqual([], validators[kind](data), name)
            invalid = copy.deepcopy(data)
            mutation = spec["invalid"]
            set_path(invalid, mutation.get("path") or mutation["remove"], mutation.get("value"), "remove" in mutation)
            self.assertTrue(any(spec["expected_failure"] in error for error in validators[kind](invalid)), name)
            return
        if kind == "manifest":
            valid = copy.deepcopy(data); valid.update(spec["valid"])
            invalid = copy.deepcopy(data); invalid.update(spec["invalid"])
            self.assertFalse(any(spec["expected_failure"] in error for error in validate_manifest_data(valid, ROOT / spec["base"])), name)
            self.assertTrue(any(spec["expected_failure"] in error for error in validate_manifest_data(invalid, ROOT / spec["base"])), name)
            return
        if kind == "validation_sql":
            model = {"schema_version": data["schema_version"], "sql_items": data["sql_items"]}
            self.assertEqual([], validate_validation_sql(model), name)
            invalid = copy.deepcopy(model)
            invalid["sql_items"][0]["identifier_evidence"] = [item for item in invalid["sql_items"][0]["identifier_evidence"] if item["identifier"] != spec["invalid"]["remove_identifier"]]
            self.assertTrue(any(spec["expected_failure"] in error for error in validate_validation_sql(invalid)), name)
            return
        if kind == "suspected_defect":
            evidence = copy.deepcopy(data["change_items"][0]["evidence_references"])
            defect = {"defect_id":"DEF001","title":"过滤失败","requirement_fact_ids":["FACT-001"],"change_ids":[spec["valid_change_id"]],"evidence_state":"已确认","observed_behavior":"未过滤","expected_behavior":"精确过滤","impact":"返回错误记录","confidence":"high","handling":"修复","evidence_references":evidence}
            data["suspected_defects"] = [defect]
            self.assertEqual([], validate_diff_model(data), name)
            data["suspected_defects"][0]["change_ids"] = [spec["invalid_change_id"]]
            self.assertTrue(any(spec["expected_failure"] in error for error in validate_diff_model(data)), name)


if __name__ == "__main__":
    unittest.main()
