#!/usr/bin/env python3
"""Static validation for fixed API automation workbooks and parameter text."""
from __future__ import annotations
import argparse, ast, hashlib, json, re, sys
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from generate_api_automation_excel import HEADERS
from qa_contracts import FIXED_API_ASSERTION_SCOPE, FIXED_API_HEALTH_CHECKS, _validate_fixed_api_checks, validate_api_automation

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

def _sha256(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(content).hexdigest()

def _subscript_path(node) -> str | None:
    parts = []
    while isinstance(node, ast.Subscript):
        key = node.slice
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str): return None
        parts.append(key.value); node = node.value
    if not isinstance(node, ast.Name) or node.id != "response": return None
    return ".".join(reversed(parts))

def _validate_script(path: Path, artifact: dict) -> list[str]:
    try: text = path.read_text(encoding="utf-8-sig"); tree = ast.parse(text)
    except (OSError, SyntaxError) as exc: return [f"API script 无法读取或解析：{exc}"]
    errors = []
    if re.search(r"\.get\s*\([^,]+,\s*(?:0|['\"]OK['\"])", text): errors.append("API script 禁止使用默认成功值绕过字段缺失")
    if re.search(r"(?i)(?:token|password|cookie|secret)\s*=\s*['\"][^$][^'\"]+", text): errors.append("API script 禁止写死 secret")
    assertions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(isinstance(child, ast.Assert) for child in ast.walk(node)):
            errors.append("API script 不得在 try/except 中吞掉断言")
        if isinstance(node, ast.Assert): assertions.append(node.test)
    expected = [("content.code", 0, int), ("content.msg", "OK", str)]
    if len(assertions) != 2: errors.append("API script 必须恰好包含两条响应健康断言")
    for index, contract in enumerate(expected):
        if index >= len(assertions): break
        check = assertions[index]
        if not isinstance(check, ast.Compare) or len(check.ops) != 1 or not isinstance(check.ops[0], ast.Eq) or len(check.comparators) != 1:
            errors.append(f"API script assert[{index}] 必须使用精确 equals 比较"); continue
        path_name = _subscript_path(check.left); right = check.comparators[0]
        value = right.value if isinstance(right, ast.Constant) else object()
        if path_name != contract[0] or type(value) is not contract[2] or value != contract[1]:
            errors.append(f"API script assert[{index}] 不符合固定响应契约")
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try: constants[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError): pass
    if constants.get("METHOD") != artifact.get("method") or constants.get("URL_OR_PATH") != artifact.get("url_or_path"):
        errors.append("API script method/path 与 Artifact 不一致")
    if set(constants.get("PARAMETERS", ())) != set(artifact.get("parameters", [])):
        errors.append("API script parameters 与 Artifact 不一致")
    if set(constants.get("REQUIRED_ENVIRONMENT_VARIABLES", ())) != set(artifact.get("required_environment_variables", [])):
        errors.append("API script environment variables 与 Artifact 不一致")
    return errors

def validate_api_automation_artifact(artifact, *, api_model, root: Path, strict: bool = True) -> list[str]:
    if not isinstance(artifact, dict): return ["API Artifact 根节点必须为 object"]
    if not isinstance(api_model, dict): return ["strict API Artifact validation requires API Model object"]
    errors = validate_api_automation(api_model)
    required = ("artifact_type","model_reference","script_path","language","entrypoint","assertion_scope","health_checks","business_assertions","required_environment_variables","validation_status")
    for field in required:
        if field not in artifact: errors.append(f"API Artifact 缺少 {field}")
    errors.extend(_validate_fixed_api_checks({"assertion_scope": artifact.get("assertion_scope"), "checks": artifact.get("health_checks")}, "API Artifact"))
    if not isinstance(artifact.get("business_assertions"), list) or artifact.get("business_assertions"):
        errors.append("API Artifact business_assertions 必须存在且为空数组")
    reference = artifact.get("model_reference")
    if not isinstance(reference, dict): errors.append("API Artifact model_reference 必须为 object"); return list(dict.fromkeys(errors))
    model_path = root / str(reference.get("model_path", ""))
    try: resolved_model = model_path.resolve()
    except OSError: resolved_model = model_path
    if root.resolve() not in resolved_model.parents or not resolved_model.is_file(): errors.append("API Artifact model_path 不安全或不存在")
    else:
        if reference.get("model_hash") != _sha256(resolved_model): errors.append("API Artifact model_hash 与真实 Model 不一致")
    if reference.get("model_id") != api_model.get("model_id"): errors.append("API Artifact model_id 与 Model 不一致")
    comparisons = {"method": api_model.get("method"), "url_or_path": api_model.get("url_or_path"), "required_environment_variables": api_model.get("required_environment_variables")}
    model_parameters = [item.get("name") for item in api_model.get("parameters", [])]
    comparisons["parameters"] = model_parameters
    for field, value in comparisons.items():
        if artifact.get(field) != value: errors.append(f"API Artifact {field} 与 Model 不一致")
    if artifact.get("health_checks") != api_model.get("validation", {}).get("checks"): errors.append("API Artifact health_checks 与 Model 不一致")
    if artifact.get("language") != "python": errors.append("API Artifact 仅支持 python")
    script = (root / str(artifact.get("script_path", ""))).resolve()
    if root.resolve() not in script.parents or not script.is_file(): errors.append("API Artifact script_path 不安全或不存在")
    elif strict: errors.extend(_validate_script(script, artifact))
    return list(dict.fromkeys(errors))
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
    parser.add_argument("artifact_pos", nargs="?", type=Path)
    parser.add_argument("--artifact", type=Path); parser.add_argument("--excel", type=Path); parser.add_argument("--parameters", type=Path); parser.add_argument("--model", required=True, type=Path); parser.add_argument("--draft", action="store_true")
    args = parser.parse_args(argv); errors = []
    artifact_path = args.artifact or args.artifact_pos
    if artifact_path:
        try:
            artifact = json.loads(artifact_path.read_text(encoding="utf-8-sig")); model = json.loads(args.model.read_text(encoding="utf-8-sig"))
            errors = validate_api_automation_artifact(artifact, api_model=model, root=Path.cwd(), strict=not args.draft)
            if args.draft and artifact.get("validation_status") == "passed": errors.append("draft 模式不得声明 passed")
        except (OSError, json.JSONDecodeError) as exc: errors = [f"API Artifact 或 Model 无法读取：{exc}"]
        for error in errors: print(f"FAIL {error}", file=sys.stderr)
        print(f"CONTEXT artifact={artifact_path} model={args.model}")
        print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
        return 1 if errors else 0
    if not args.excel or not args.parameters: parser.error("--artifact 或 --excel 与 --parameters 必须提供")
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
