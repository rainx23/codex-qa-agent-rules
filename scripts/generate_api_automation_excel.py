#!/usr/bin/env python3
"""Generate the fixed company API-automation XLSX and parameter text using stdlib only."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

HEADERS = ["序号", "用例名称", "method", "url", "body类型", "body", "headers", "校验", "优先级", "接口code"]

def cell(ref: str, value: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'

def write_xlsx(path: Path, rows: list[list[str]]) -> None:
    sheet_rows = []
    for r, row in enumerate(rows, 1):
        cells = "".join(cell(f"{chr(64 + c)}{r}", value) for c, value in enumerate(row, 1))
        sheet_rows.append(f'<row r="{r}">{cells}</row>')
    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="接口自动化用例" sheetId="1" r:id="rId1"/></sheets></workbook>'
    workbook_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    sheet = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(sheet_rows) + "</sheetData></worksheet>"
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", ZIP_DEFLATED) as zf:
        for name, value in {"[Content_Types].xml": content_types, "_rels/.rels": rels, "xl/workbook.xml": workbook, "xl/_rels/workbook.xml.rels": workbook_rels, "xl/worksheets/sheet1.xml": sheet}.items():
            zf.writestr(name, value.encode("utf-8"))

def parameter_text(model: dict) -> str:
    p = model["parameterization"]
    return f"参数名：\n{p['parameter_name_text']}\n\n参数值：\n{p['parameter_value_text']}\n"

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成接口自动化 Excel 和参数粘贴文本")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--template", type=Path, help="兼容参数；固定模板不读取模板列定义")
    parser.add_argument("--parameter-output", type=Path)
    args = parser.parse_args(argv)
    model = json.loads(args.model.read_text(encoding="utf-8-sig"))
    from qa_contracts import validate_api_automation
    errors = validate_api_automation(model)
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    cases = model.get("excel_case", [])
    rows = [HEADERS]
    for index, item in enumerate(cases, 1):
        rows.append([str(index), item["case_name"], item["method"].lower(), item["url"], item["body_type"], item["body"], item["headers"], item["validation"], item["priority"], item["interface_code"]])
    write_xlsx(args.output, rows)
    parameter_path = args.parameter_output or args.output.with_name(args.output.stem.replace("-case", "-parameter") + ".txt")
    parameter_path.write_text(parameter_text(model), encoding="utf-8")
    print(f"PASS {args.output}")
    print(f"PASS {parameter_path}")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
