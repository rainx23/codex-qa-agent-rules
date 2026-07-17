from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_knowledge_index import build_indexes
from compare_ddl import compare_tables
from parse_chat_ddl import parse_ddl, parse_partial_fields
from qa_contracts import (
    load_json, validate_data_validation, validate_knowledge_table, validate_reconciliation,
)
from search_knowledge import search
from validate_knowledge import validate_knowledge
from validate_sql_artifact import validate_artifact, validate_sql_artifact
from validate_sql_style import validate_sql
from sql_identifier_extractor import extract_sql_identifiers


class KnowledgeAndSqlTests(unittest.TestCase):
    def test_sql_extractor_excludes_cte_alias_comments_and_strings(self):
        sql = """-- from fake.table\nwith v as (select o.order_id as id from demo.orders o where o.status='fake_column') select id from v where id=${order_id}"""
        result = extract_sql_identifiers(sql, dialect="starrocks")
        self.assertEqual(["demo.orders"], result["physical_tables"])
        self.assertIn("v", result["cte_names"])
        self.assertEqual("demo.orders", result["table_aliases"]["o"])
        self.assertIn("demo.orders.order_id", result["columns"])
        self.assertNotIn("fake.table", result["physical_tables"])
        self.assertEqual(["order_id"], result["parameters"])

    def test_ci_sql_command_requires_full_context(self):
        workflow = (ROOT / ".github/workflows/qa-rules-validation.yml").read_text(encoding="utf-8")
        command = next(line for line in workflow.splitlines() if "validate_sql_artifact.py" in line)
        for flag in ("--requirement", "--diff", "--risk", "--testcase", "--knowledge"):
            self.assertIn(flag, command)
        self.assertNotIn("|| true", command)
        self.assertNotIn("--draft", command)
        self.assertNotIn("--legacy", command)
    def test_sql_identifier_strict_context_and_required_sources(self):
        artifact = load_json(ROOT / "tests/fixtures/artifacts/validation-sql-manifest.json")
        errors = validate_sql_artifact(artifact, requirement_model=None, knowledge_models=[], strict=True)
        self.assertTrue(any("Requirement" in error for error in errors), errors)
        self.assertTrue(any("Knowledge" in error for error in errors), errors)
        evidence = copy.deepcopy(artifact["sql_items"][0]["identifier_evidence"][0])
        evidence.pop("source_reference_type", None)
        artifact["sql_items"][0]["identifier_evidence"] = [evidence]
        self.assertTrue(any("source_reference_type" in error for error in validate_sql_artifact(
            artifact, requirement_model={}, knowledge_models=[{}], strict=True
        )))

    def test_sql_identifier_fake_fact_and_missing_column_fail(self):
        artifact = load_json(ROOT / "tests/fixtures/artifacts/validation-sql-manifest.json")
        requirement = load_json(ROOT / "tests/fixtures/models/requirement-analysis.json")
        knowledge = load_json(ROOT / "qa-knowledge/examples/domains/demo/tables/demo.orders/metadata.json")
        enum = copy.deepcopy(artifact["sql_items"][0]["identifier_evidence"][0])
        enum.update(identifier="已确认", identifier_type="enum_value", qualified_identifier="status=已确认", scope_table="demo.orders", usage_type="filter", source_reference_type="fact", source_reference_id="FACT-999")
        artifact["sql_items"][0]["identifier_evidence"] = [enum]
        errors = validate_sql_artifact(artifact, requirement_model=requirement, knowledge_models=[knowledge], strict=True)
        self.assertTrue(any("FACT-999" in error for error in errors), errors)
        column = copy.deepcopy(enum)
        column.update(identifier="missing_column", identifier_type="column", qualified_identifier="demo.orders.missing_column", source_reference_type="knowledge_table_field", source_reference_id="demo_orders#missing_column")
        artifact["sql_items"][0]["identifier_evidence"] = [column]
        errors = validate_sql_artifact(artifact, requirement_model=requirement, knowledge_models=[knowledge], strict=True)
        self.assertTrue(any("missing_column" in error for error in errors), errors)
    def test_field_constraint_tokens_are_fully_consumed(self):
        table = parse_ddl(
            "create table demo.orders (id bigint not null default 0 comment 'primary key');"
        )["tables"][0]
        field = table["fields"][0]
        self.assertEqual("complete", table["schema_scope"])
        self.assertFalse(field["nullable"])
        self.assertEqual("0", field["default"])
        self.assertEqual("known_value", field["default_state"])
        self.assertEqual("primary key", field["comment"])
        self.assertIsNone(field["unparsed_fragment"])

    def test_nullable_uses_only_explicit_constraint_tokens(self):
        cases = (
            ("id bigint not null", False),
            ("id bigint null", True),
            ("id bigint", None),
            ("id bigint default null", None),
            ("id bigint null comment 'not null value'", True),
            ("id bigint not null comment 'nullable field'", False),
            ("id bigint default 'not null'", None),
        )
        for fragment, expected in cases:
            with self.subTest(fragment=fragment):
                table = parse_ddl(f"create table demo.t ({fragment});")["tables"][0]
                self.assertEqual("complete", table["schema_scope"])
                self.assertEqual(expected, table["fields"][0]["nullable"])
        for fragment in ("id bigint null not null", "id bigint not null null"):
            with self.subTest(conflict=fragment):
                table = parse_ddl(f"create table demo.t ({fragment});")["tables"][0]
                self.assertEqual("partial", table["schema_scope"])
                self.assertTrue(table["parse_warnings"])

    def test_constraint_order_default_and_comment_values(self):
        for constraints in (
            "not null default 0 comment 'id'",
            "default 0 not null comment 'id'",
            "comment 'id' default 0 not null",
        ):
            with self.subTest(constraints=constraints):
                field = parse_ddl(f"create table demo.t (id bigint {constraints});")["tables"][0]["fields"][0]
                self.assertFalse(field["nullable"])
                self.assertEqual("0", field["default"])
                self.assertEqual("id", field["comment"])
                self.assertIsNone(field["unparsed_fragment"])
        defaults = (
            ("null", None, "known_null"), ("0", "0", "known_value"),
            ("-1", "-1", "known_value"), ("1.25", "1.25", "known_value"),
            ("''", "", "known_value"), ("'user''name'", "user'name", "known_value"),
            ("current_timestamp", "current_timestamp", "known_value"),
            ("current_timestamp()", "current_timestamp()", "known_value"),
            ("now()", "now()", "known_value"), (("(uuid())"), "(uuid())", "known_value"),
            ("true", "true", "known_value"), ("false", "false", "known_value"),
        )
        for expression, expected, state in defaults:
            with self.subTest(default=expression):
                field = parse_ddl(f"create table demo.t (id varchar(30) default {expression});")["tables"][0]["fields"][0]
                self.assertEqual(expected, field["default"])
                self.assertEqual(state, field["default_state"])
        field = parse_ddl("create table demo.t (id bigint comment '用户''名称 default null');")["tables"][0]["fields"][0]
        self.assertEqual("用户'名称 default null", field["comment"])

    def test_generated_columns_and_nested_types_are_preserved(self):
        ddl = """create table demo.orders (
            id bigint,
            tags array<varchar(20)>,
            attrs map<string, bigint>,
            payload struct<a:int,b:string>,
            created_at datetime(3),
            code char(10),
            amount decimal(18, 2),
            tax decimal(18, 2),
            total decimal(18, 2) generated always as (round(amount + tax, 2)),
            label varchar(50) generated as (concat('tax(', amount, ')')),
            copied bigint as (id)
        );"""
        table = parse_ddl(ddl)["tables"][0]
        self.assertEqual("complete", table["schema_scope"], table["parse_warnings"])
        self.assertEqual(
            ["bigint", "array<varchar(20)>", "map<string, bigint>", "struct<a:int,b:string>", "datetime(3)", "char(10)",
             "decimal(18, 2)", "decimal(18, 2)", "decimal(18, 2)", "varchar(50)", "bigint"],
            [field["type"] for field in table["fields"]],
        )
        self.assertEqual("round(amount + tax, 2)", table["fields"][8]["generated_expression"])
        self.assertEqual("concat('tax(', amount, ')')", table["fields"][9]["generated_expression"])
        self.assertEqual("id", table["fields"][10]["generated_expression"])
        self.assertEqual(["always", "generated", "as"], [field["generated_type"] for field in table["fields"][8:]])

    def test_table_constraints_and_tail_are_fully_consumed(self):
        ddl = """create table demo.orders (
            id bigint primary key,
            code varchar(20),
            primary key (id),
            unique key uk_code (code),
            check (id > 0),
            constraint ck_code check (code <> ''),
            index idx_code (code)
        ) engine=olap
        duplicate key(id)
        partition by range(id) ()
        distributed by hash(id) buckets 3
        order by (id)
        properties ("replication_num" = "1", 'storage_medium' = 'SSD')
        comment 'table comment';"""
        table = parse_ddl(ddl)["tables"][0]
        self.assertEqual("complete", table["schema_scope"], table["parse_warnings"])
        self.assertIn("primary key", table["fields"][0]["inline_constraints"])
        self.assertGreaterEqual(len(table["keys"]), 5)
        self.assertTrue(table["indexes"])
        self.assertTrue(table["partitions"])
        self.assertEqual("SSD", table["engine_properties"]["storage_medium"])
        self.assertTrue(table["raw_tail"])
        self.assertTrue(table["parsed_tail_tokens"])
        self.assertIsNone(table["unparsed_tail"])
        unknown = parse_ddl("create table demo.orders (id bigint) engine=olap unknown table option abc;")["tables"][0]
        self.assertEqual("partial", unknown["schema_scope"])
        self.assertEqual("unknown table option abc", unknown["unparsed_tail"])

    def test_complete_knowledge_contract_rejects_missing_consumption_evidence(self):
        table = parse_ddl("create table demo.t (id bigint, total bigint as (id));")["tables"][0]
        self.assertEqual([], validate_knowledge_table(table))
        for field_name in ("raw_fragment", "parsed_tokens", "unparsed_fragment"):
            changed = copy.deepcopy(table)
            changed["fields"][0].pop(field_name)
            self.assertTrue(validate_knowledge_table(changed), field_name)
        changed = copy.deepcopy(table)
        changed.pop("unparsed_tail")
        self.assertTrue(validate_knowledge_table(changed))
        changed = copy.deepcopy(table)
        changed["fields"][1]["generated_expression"] = None
        self.assertTrue(any("generated_expression" in error for error in validate_knowledge_table(changed)))
        changed = copy.deepcopy(table)
        changed.update(schema_scope="partial", unparsed_tail="unknown option", parse_warnings=["unknown option"])
        self.assertEqual([], validate_knowledge_table(changed))

    def test_partial_fields_preserve_unknowns_and_table_identity(self):
        result = parse_partial_fields("name varchar(20)", "orders", "trade")
        self.assertFalse(result["sensitive"])
        table = result["tables"][0]
        self.assertEqual("partial", table["schema_scope"])
        self.assertEqual("", table["database"])
        self.assertEqual("orders", table["table_name"])
        self.assertEqual("orders", table["full_name"])
        self.assertEqual("trade", table["domain"])
        self.assertIsNone(table["raw_ddl"])
        self.assertIsNone(table["normalized_ddl"])
        field = table["fields"][0]
        self.assertIsNone(field["nullable"])
        self.assertEqual("unknown", field["default_state"])
        self.assertEqual(["name", "type"], field["evidence_fields"])
        self.assertEqual(["nullable", "default", "comment"], field["unknown_fields"])

    def test_partial_fields_keep_order_and_explicit_constraints(self):
        result = parse_partial_fields(
            "id bigint not null,\nname varchar(20),\namount decimal(18, 2),\n"
            "remark varchar(100) null,\ncode varchar(8) default null comment '状态'",
            "demo.orders",
        )
        table = result["tables"][0]
        self.assertEqual("partial", table["schema_scope"])
        self.assertEqual(["id", "name", "amount", "remark", "code"], [field["name"] for field in table["fields"]])
        self.assertEqual([1, 2, 3, 4, 5], [field["ordinal"] for field in table["fields"]])
        self.assertFalse(table["fields"][0]["nullable"])
        self.assertTrue(table["fields"][3]["nullable"])
        self.assertIsNone(table["fields"][4]["nullable"])
        self.assertEqual("known_null", table["fields"][4]["default_state"])
        self.assertEqual("状态", table["fields"][4]["comment"])

    def test_partial_fields_block_empty_unparseable_and_sensitive_input(self):
        for text in ("", "   ", "??? unsupported"):
            result = parse_partial_fields(text, "demo.orders")
            self.assertFalse(result["sensitive"])
            self.assertEqual("blocked", result["tables"][0]["schema_scope"])
            self.assertEqual([], result["tables"][0]["fields"])
            self.assertTrue(result["warnings"])
        sensitive = parse_partial_fields("password=secret\nid bigint", "demo.orders")
        self.assertTrue(sensitive["sensitive"])
        self.assertEqual([], sensitive["tables"])
        self.assertTrue(sensitive["warnings"])

    def test_parse_chat_ddl_cli_complete_partial_and_missing_table(self):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        script = ROOT / "scripts/parse_chat_ddl.py"
        with tempfile.TemporaryDirectory() as directory:
            ddl_path = Path(directory) / "ddl.sql"
            fields_path = Path(directory) / "fields.txt"
            ddl_path.write_text("create table demo.orders (id bigint);", encoding="utf-8")
            fields_path.write_text("id bigint,\nname varchar(20)", encoding="utf-8")
            complete = subprocess.run(
                [sys.executable, str(script), str(ddl_path)],
                capture_output=True, text=True, encoding="utf-8", env=environment, check=False,
            )
            self.assertEqual(0, complete.returncode, complete.stderr)
            self.assertEqual("complete", json.loads(complete.stdout)["tables"][0]["schema_scope"])
            partial = subprocess.run(
                [sys.executable, str(script), "--partial", str(fields_path), "--table", "demo.orders"],
                capture_output=True, text=True, encoding="utf-8", env=environment, check=False,
            )
            self.assertEqual(0, partial.returncode, partial.stderr)
            self.assertEqual("partial", json.loads(partial.stdout)["tables"][0]["schema_scope"])
            missing_table = subprocess.run(
                [sys.executable, str(script), "--partial", str(fields_path)],
                capture_output=True, text=True, encoding="utf-8", env=environment, check=False,
            )
            self.assertNotEqual(0, missing_table.returncode)

    def test_single_and_multi_ddl_split_preserves_field_order(self):
        text = """create table demo.a (id bigint not null, amount decimal(18,2));
create table demo.b (code varchar(16));"""
        result = parse_ddl(text)
        self.assertEqual(2, len(result["tables"]))
        self.assertEqual(["id", "amount"], [item["name"] for item in result["tables"][0]["fields"]])
        self.assertEqual([], validate_knowledge_table(result["tables"][0]))

    def test_same_ddl_has_same_normalized_hash(self):
        first = parse_ddl("create table demo.a (id bigint);")["tables"][0]
        second = parse_ddl("create   table demo.a ( id bigint );")["tables"][0]
        self.assertEqual(first["normalized_hash"], second["normalized_hash"])

    def test_ddl_structural_diff_categories(self):
        old = parse_ddl("create table demo.a (id bigint, amount decimal(10,2));")["tables"][0]
        new = parse_ddl("create table demo.a (id bigint, amount decimal(18,2), status varchar(8));")["tables"][0]
        diff = compare_tables(old, new)
        self.assertEqual(["status"], diff["added_fields"])
        self.assertEqual(["amount"], diff["type_changed_fields"])
        self.assertTrue(diff["structural_change"])

    def test_complete_ddl_preserves_explicit_table_structures(self):
        ddl = """create table demo.orders (
  order_id bigint not null,
  amount decimal(18,2),
  primary key (order_id),
  index idx_amount (amount)
) engine=olap
partition by range(order_id) ()
distributed by hash(order_id) buckets 3
properties ("replication_num"="1");"""
        table = parse_ddl(ddl)["tables"][0]
        self.assertEqual("complete", table["schema_scope"])
        self.assertTrue(any("PRIMARY KEY" in item.upper() for item in table["keys"]))
        self.assertTrue(table["partitions"])
        self.assertTrue(any("INDEX" in item.upper() for item in table["indexes"]))
        self.assertTrue(any("DISTRIBUTED BY" in item.upper() for item in table["indexes"]))
        self.assertEqual("olap", table["engine_properties"]["engine"].lower())
        self.assertEqual("1", table["engine_properties"]["replication_num"])

    def test_explicit_unparsed_ddl_structure_downgrades_complete(self):
        table = parse_ddl("create table demo.a (id bigint) engine= properties (); ")["tables"][0]
        self.assertEqual("partial", table["schema_scope"])
        self.assertTrue(any("Engine" in warning or "Properties" in warning for warning in table["parse_warnings"]))

    def test_partial_model_cannot_be_complete_table(self):
        table = load_json(ROOT / "qa-knowledge/examples/domains/demo/tables/demo.orders/metadata.json")
        table["schema_scope"] = "partial"
        self.assertTrue(any("partial" in error for error in validate_knowledge_table(table)))

    def test_sensitive_ddl_is_rejected(self):
        result = parse_ddl("create table demo.a (token varchar(64)); -- password: x")
        self.assertTrue(result["sensitive"])
        self.assertFalse(result["tables"])

    def test_knowledge_example_valid_and_indexes_stable(self):
        root = ROOT / "qa-knowledge/examples"
        self.assertEqual([], validate_knowledge(root))
        indexes = build_indexes(root)
        self.assertEqual(["demo_orders"], [item["id"] for item in indexes["by-table.json"]])
        self.assertEqual(["amount", "order_id", "status", "trade_date"], [item["id"] for item in indexes["by-field.json"]])
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "examples"
            shutil.copytree(root, clone)
            (clone / "indexes/by-table.json").write_text("[]\n", encoding="utf-8")
            self.assertTrue(any("索引漂移" in error for error in validate_knowledge(clone)))

    def test_search_defaults_to_active_and_can_include_history(self):
        root = ROOT / "qa-knowledge/examples"
        self.assertTrue(search(root, "demo.orders", "table"))
        self.assertEqual([], search(root, "does-not-exist"))

    def test_data_validation_decisions(self):
        valid = load_json(ROOT / "tests/fixtures/models/data-validation-valid.json")
        self.assertEqual([], validate_data_validation(valid))
        cross = load_json(ROOT / "tests/fixtures/models/data-validation-cross-source-valid.json")
        self.assertEqual([], validate_data_validation(cross))
        blocked = load_json(ROOT / "tests/fixtures/models/data-validation-blocked.json")
        self.assertEqual([], validate_data_validation(blocked))
        invalid = load_json(ROOT / "tests/fixtures/models/data-validation-invalid-page-only.json")
        self.assertTrue(validate_data_validation(invalid))

    def test_reconciliation_requires_distinct_entries(self):
        model = load_json(ROOT / "tests/fixtures/models/reconciliation-valid.json")
        self.assertEqual([], validate_reconciliation(model))
        model["reconciliation_plans"][0]["target_entry"] = model["reconciliation_plans"][0]["baseline_entry"]
        self.assertTrue(any("不得相同" in error for error in validate_reconciliation(model)))

    def test_sql_style_valid_and_dangerous_sql_fails(self):
        valid = (ROOT / "tests/fixtures/sql/valid_validation_sql.sql").read_text(encoding="utf-8")
        errors, warnings = validate_sql(valid, strict=True)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        invalid = (ROOT / "tests/fixtures/sql/invalid_validation_sql.sql").read_text(encoding="utf-8")
        self.assertTrue(validate_sql(invalid, strict=True)[0])

    def test_sql_artifact_is_static_and_counted(self):
        path = ROOT / "tests/fixtures/artifacts/validation-sql-manifest.json"
        context = {
            "requirement": ROOT / "tests/fixtures/models/requirement-analysis.json",
            "diff": ROOT / "tests/fixtures/models/diff-impact.json",
            "risk_matrix": ROOT / "tests/fixtures/models/risk-coverage-matrix.json",
            "testcase_model": ROOT / "tests/fixtures/models/testcase-model.json",
            "knowledge_root": ROOT / "qa-knowledge/examples",
        }
        self.assertEqual([], validate_artifact(path, **context))
        data = json.loads(path.read_text(encoding="utf-8"))
        data["sql_count"] = 2
        with tempfile.NamedTemporaryFile("w", suffix=".json", dir=path.parent, delete=False, encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
            temp = Path(handle.name)
        try:
            self.assertTrue(any("sql_count" in error for error in validate_artifact(temp, **context)))
        finally:
            temp.unlink()

    def test_no_database_execution_or_connection_symbols_added(self):
        scripts = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "scripts").glob("*.py"))
        self.assertNotIn("sqlite3.connect", scripts)
        self.assertNotIn("pymysql.connect", scripts)
        self.assertNotIn("psycopg2.connect", scripts)


if __name__ == "__main__":
    unittest.main()
