#!/usr/bin/env python3
"""Static validation for fixed API automation workbooks and parameter text."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from generate_api_automation_excel import HEADERS

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
def read_rows(path: Path) -> list[list[str]]:
    with ZipFile(path) as zf:
        if "xl/worksheets/sheet1.xml" not in zf.namelist(): raise ValueError("缺少 sheet1.xml")
        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in root.findall(".//m:row", NS):
        values = []
        for c in row.findall("m:c", NS):
            node = c.find("m:is/m:t", NS)
            values.append("" if node is None else (node.text or ""))
        rows.append(values)
    return rows
def parse_params(path: Path) -> tuple[str, object]:
    text = path.read_text(encoding="utf-8-sig")
    match = re.fullmatch(r"参数名：\n([^\n]+)\n\n参数值：\n(.+?)\n?", text, re.S)
    if not match: raise ValueError("参数文本格式必须为参数名/参数值两段")
    return match.group(1), json.loads(match.group(2))
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验接口自动化 Excel 和参数文本")
    parser.add_argument("--excel", required=True, type=Path); parser.add_argument("--parameters", required=True, type=Path); parser.add_argument("--model", type=Path)
    args = parser.parse_args(argv); errors = []
    try: rows = read_rows(args.excel)
    except Exception as exc: rows = []; errors.append(f"Excel 无法打开：{exc}")
    if not rows or rows[0] != HEADERS: errors.append("Excel 表头或顺序不符合固定 10 列")
    codes = []
    for row in rows[1:]:
        if len(row) != 10: errors.append("每行必须包含 10 列"); continue
        if not row[2] or row[2] != row[2].lower(): errors.append("method 必须为小写且非空")
        if not re.match(r"^https?://", row[3]): errors.append("url 必须为完整 http(s) 地址")
        if row[4] not in {"json", "params", "data"}: errors.append(f"body类型非法：{row[4]}")
        for field, value in (("body", row[5]), ("headers", row[6]), ("校验", row[7])):
            try: json.loads(value)
            except json.JSONDecodeError: errors.append(f"{field} 不是合法 JSON")
        try:
            validation = json.loads(row[7]); checks = validation.get("validate", [])
            if not any(c.get("check") == "content.code" and str(c.get("expected")) == "0" for c in checks): errors.append("校验缺少 content.code=0")
            if not any(c.get("check") == "content.msg" and c.get("expected") == "OK" for c in checks): errors.append("校验缺少 content.msg=OK")
        except (json.JSONDecodeError, AttributeError): pass
        if not row[9]: errors.append("接口code 非空")
        codes.append(row[9])
    if len(codes) != len(set(codes)): errors.append("同一接口重复生成 Excel 行且没有拆分证据")
    try:
        name_text, values = parse_params(args.parameters)
        if not isinstance(values, list) or not values: errors.append("参数值必须是非空数组")
        names = name_text.split(",")
        if len(names) == 1 and any(isinstance(v, list) for v in values): errors.append("单参数必须是一维数组")
        if len(names) > 1 and (not all(isinstance(v, list) and len(v) == len(names) for v in values)): errors.append("关联参数必须是维度一致的二维数组")
        variables = set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", " ".join(" ".join(row) for row in rows[1:])))
        if not variables.issubset(set(names)): errors.append(f"Body 引用了未定义参数：{sorted(variables - set(names))}")
    except Exception as exc: errors.append(f"参数文本无效：{exc}")
    if args.model:
        try:
            from qa_contracts import validate_api_automation
            model = json.loads(args.model.read_text(encoding="utf-8-sig")); errors.extend(validate_api_automation(model))
        except Exception as exc: errors.append(f"模型无效：{exc}")
    if errors:
        for error in dict.fromkeys(errors): print(f"FAIL {error}", file=sys.stderr)
        print(f"SUMMARY passed=0 warning=0 failed={len(set(errors))}"); return 1
    print("PASS API automation artifacts"); print("SUMMARY passed=1 warning=0 failed=0"); return 0
if __name__ == "__main__": raise SystemExit(main())
