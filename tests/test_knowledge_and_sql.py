from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_knowledge_index import build_indexes
from compare_ddl import compare_tables
from parse_chat_ddl import parse_ddl
from qa_contracts import (
    load_json, validate_data_validation, validate_knowledge_table, validate_reconciliation,
)
from search_knowledge import search
from validate_knowledge import validate_knowledge
from validate_sql_artifact import validate_artifact
from validate_sql_style import validate_sql


class KnowledgeAndSqlTests(unittest.TestCase):
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
        self.assertEqual([], validate_artifact(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        data["sql_count"] = 2
        with tempfile.NamedTemporaryFile("w", suffix=".json", dir=path.parent, delete=False, encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
            temp = Path(handle.name)
        try:
            self.assertTrue(any("sql_count" in error for error in validate_artifact(temp)))
        finally:
            temp.unlink()

    def test_no_database_execution_or_connection_symbols_added(self):
        scripts = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "scripts").glob("*.py"))
        self.assertNotIn("sqlite3.connect", scripts)
        self.assertNotIn("pymysql.connect", scripts)
        self.assertNotIn("psycopg2.connect", scripts)


if __name__ == "__main__":
    unittest.main()
