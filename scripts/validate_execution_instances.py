#!/usr/bin/env python3
"""Validate execution instances, reruns, evidence and model references."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_MODEL_FIELDS = ("schema_version","rule_version","execution_model_id","testcase_model_id","validation_status","branch_count","execution_instance_count","execution_instances")
REQUIRED_INSTANCE_FIELDS = ("execution_instance_id","testcase_id","branch_id","run_type","run_sequence","status","executed_at","executor","actual_result","evidence_references","defect_ids","confirmation_ids","rerun_of_execution_instance_id","notes")
STATUSES = {"not_run","passed","failed","blocked","skipped"}

def _sha(path: Path) -> str: return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def build_testcase_branch_index(model: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for case in model.get("cases", []):
        branches = {b.get("branch_id"): b for b in case.get("entry_branches", []) if b.get("branch_id") and b.get("executable", True) and b.get("status") != "not_applicable"}
        result[case.get("tc_id")] = {"risk_ids": case.get("risk_ids", []), "branches": branches, "test_priority": case.get("test_priority")}
    return {"testcases": result}

def build_defect_id_index(model: dict[str, Any] | None) -> dict[str, Any]:
    return {item.get("defect_id"): item for item in (model or {}).get("defects", []) if item.get("defect_id")}

def summarize_execution_model(model: dict[str, Any], testcase_model: dict[str, Any]) -> dict[str, int]:
    instances = model.get("execution_instances", []) if isinstance(model.get("execution_instances"), list) else []
    final = {}
    for item in instances:
        key = (item.get("testcase_id"), item.get("branch_id")); seq = item.get("run_sequence", 0)
        if key not in final or seq > final[key].get("run_sequence", 0): final[key] = item
    summary = {"branch_count": sum(len(v["branches"]) for v in build_testcase_branch_index(testcase_model)["testcases"].values()), "execution_instance_count": len(instances),
               "initial_count": sum(i.get("run_type") == "initial" for i in instances), "rerun_count": sum(i.get("run_type") == "rerun" for i in instances)}
    for status in STATUSES: summary[f"final_{status}_count"] = sum(i.get("status") == status for i in final.values())
    summary["core_skipped_count"] = sum(i.get("status") == "skipped" for i in final.values())
    summary["core_unpassed_count"] = sum(i.get("status") != "passed" for i in final.values())
    return summary

def _evidence_errors(ref: Any, instance: dict[str, Any], root: Path) -> list[str]:
    iid, tc, branch = instance.get("execution_instance_id"), instance.get("testcase_id"), instance.get("branch_id")
    if not isinstance(ref, dict): return [f"{iid} execution evidence 必须为 object"]
    path = root / str(ref.get("source_path", ""))
    if root.resolve() not in path.resolve().parents or not path.is_file(): return [f"{iid} execution evidence 路径不存在或越界"]
    errors = []
    if ref.get("content_hash") != _sha(path): errors.append(f"{iid} execution evidence hash 不一致")
    if ref.get("evidence_status") != "current": errors.append(f"{iid} execution evidence 必须 current")
    record = str(ref.get("source_record_id", ""))
    if not all(str(token) in record for token in (iid, tc, branch)): errors.append(f"{iid} execution evidence source_record_id 与 TC/Branch 不一致")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if not all(str(token) in text for token in (iid, tc, branch)): errors.append(f"{iid} execution evidence 内容与实例不一致")
    return errors

def validate_execution_model(model: Any, *, testcase_model: dict[str, Any], risk_model: dict[str, Any], requirement_model: dict[str, Any], defect_model: dict[str, Any] | None, root: Path, strict: bool = True) -> list[str]:
    if not isinstance(model, dict): return ["Execution Model 根节点必须为 object"]
    errors = [f"Execution Model 缺少 {field}" for field in REQUIRED_MODEL_FIELDS if field not in model]
    if errors: return errors
    if model.get("schema_version") != "2.0.0": errors.append("Execution Model schema_version 非法")
    if not re.fullmatch(r"EXEC-MODEL-\d{3}", str(model.get("execution_model_id"))): errors.append("execution_model_id 非法")
    if model.get("testcase_model_id") != testcase_model.get("model_id"): errors.append("testcase_model_id 与 Testcase Model 不一致")
    tc_path = root / str(model.get("testcase_model_path", ""))
    if not tc_path.is_file() or model.get("testcase_model_hash") != _sha(tc_path): errors.append("Testcase Model 路径或 hash 不一致")
    index = build_testcase_branch_index(testcase_model)["testcases"]
    expected_branches = {(tc, branch) for tc, value in index.items() for branch in value["branches"]}
    if model.get("branch_count") != len(expected_branches): errors.append("branch_count 与 Testcase Model 真实 Branch 数不一致")
    instances = model.get("execution_instances")
    if not isinstance(instances, list): return errors + ["execution_instances 必须为 array"]
    if model.get("execution_instance_count") != len(instances): errors.append("execution_instance_count 与数组长度不一致")
    by_id = {}; groups = {}
    defects = build_defect_id_index(defect_model)
    confirmations = {c.get("confirmation_id"): c for c in requirement_model.get("confirmation_points", [])}
    for item in instances:
        if not isinstance(item, dict): errors.append("Execution Instance 必须为 object"); continue
        iid = item.get("execution_instance_id")
        for field in REQUIRED_INSTANCE_FIELDS:
            if field not in item: errors.append(f"{iid} 缺少 {field}")
        if iid in by_id or not re.fullmatch(r"EXEC-\d{3}", str(iid)): errors.append(f"Execution Instance ID 重复或非法：{iid}")
        by_id[iid] = item; key = (item.get("testcase_id"), item.get("branch_id")); groups.setdefault(key, []).append(item)
        if key not in expected_branches: errors.append(f"{iid} 引用不存在或跨 Testcase 的 Branch")
        status = item.get("status")
        if status not in STATUSES: errors.append(f"{iid} status 非法")
        if item.get("run_type") == "initial" and (item.get("run_sequence") != 1 or item.get("rerun_of_execution_instance_id") is not None): errors.append(f"{iid} initial 契约非法")
        if item.get("run_type") == "rerun" and (not isinstance(item.get("run_sequence"), int) or item.get("run_sequence") < 2 or not item.get("rerun_of_execution_instance_id")): errors.append(f"{iid} rerun 契约非法")
        evidence = item.get("evidence_references") if isinstance(item.get("evidence_references"), list) else []
        for ref in evidence: errors.extend(_evidence_errors(ref, item, root))
        if status == "not_run":
            if any(item.get(f) not in (None, [], "") for f in ("executed_at","executor","actual_result","evidence_references","defect_ids","confirmation_ids","rerun_of_execution_instance_id")): errors.append(f"{iid} not_run 携带执行结果或引用")
        elif status == "passed":
            if not all((item.get("executed_at"), item.get("executor"), item.get("actual_result"), evidence)): errors.append(f"{iid} passed 缺少执行结果或 Evidence")
            if str(item.get("actual_result", "")).strip() in {"通过","正常","符合预期","无问题"}: errors.append(f"{iid} passed actual_result 过于模糊")
            if item.get("defect_ids") or item.get("confirmation_ids") or item.get("blocked_reason") or item.get("skip_reason"): errors.append(f"{iid} passed 包含其他状态专属字段")
        elif status == "failed":
            if not all((item.get("executed_at"), item.get("executor"), item.get("actual_result"), evidence)): errors.append(f"{iid} failed 缺少执行结果或 Evidence")
            unknown = set(item.get("defect_ids", [])) - defects.keys()
            if unknown: errors.append(f"{iid} 引用不存在 Defect：{sorted(unknown)}")
            if not item.get("defect_ids") and not (item.get("failure_classification") == "suspected_defect" and item.get("confirmation_ids")): errors.append(f"{iid} failed 缺少真实 Defect 或 suspected_defect Confirmation")
            if item.get("skip_reason") or item.get("blocked_reason"): errors.append(f"{iid} failed 包含其他状态专属字段")
        elif status == "blocked":
            ids = set(item.get("confirmation_ids", [])); unknown = ids - confirmations.keys()
            if unknown: errors.append(f"{iid} blocked 引用不存在 Confirmation：{sorted(unknown)}")
            if not ids or not any(confirmations[x].get("severity") == "blocking" and confirmations[x].get("status") in {"pending","skipped"} for x in ids & confirmations.keys()): errors.append(f"{iid} blocked 缺少 unresolved blocking Confirmation")
            if item.get("defect_ids") or item.get("skip_reason"): errors.append(f"{iid} blocked 包含其他状态专属字段")
        elif status == "skipped":
            if not all((item.get("skip_reason"), item.get("decision_evidence_references"), item.get("skipped_by"), item.get("skipped_at"))): errors.append(f"{iid} skipped 缺少正式决策字段")
            if item.get("defect_ids"): errors.append(f"{iid} skipped 不得关联 Defect")
    for key, chain in groups.items():
        if sum(i.get("run_type") == "initial" for i in chain) != 1: errors.append(f"{key} 必须恰好一个 initial")
        seqs = sorted(i.get("run_sequence") for i in chain if isinstance(i.get("run_sequence"), int))
        if seqs != list(range(1, len(chain)+1)): errors.append(f"{key} run_sequence 必须连续且唯一")
    for iid, item in by_id.items():
        parent_id = item.get("rerun_of_execution_instance_id")
        if not parent_id: continue
        parent = by_id.get(parent_id)
        if not parent: errors.append(f"{iid} rerun_of 不存在"); continue
        if parent_id == iid: errors.append(f"{iid} rerun 不得自引用")
        if (parent.get("testcase_id"), parent.get("branch_id")) != (item.get("testcase_id"), item.get("branch_id")): errors.append(f"{iid} rerun 必须对应同一 Testcase/Branch")
        if item.get("run_sequence") != parent.get("run_sequence", 0) + 1: errors.append(f"{iid} rerun 必须引用直接前序")
        if parent.get("status") not in {"failed","blocked"}: errors.append(f"{iid} 前序状态不允许 rerun")
        if item.get("executed_at") and parent.get("executed_at") and item["executed_at"] < parent["executed_at"]: errors.append(f"{iid} rerun 时间早于前序")
        seen = {iid}; current = parent
        while current:
            current_id = current.get("execution_instance_id")
            if current_id in seen: errors.append(f"{iid} rerun 链形成循环"); break
            seen.add(current_id); current = by_id.get(current.get("rerun_of_execution_instance_id"))
    covered = {(i.get("testcase_id"), i.get("branch_id")) for i in instances}
    if strict and expected_branches - covered: errors.append(f"缺少 Branch Execution：{sorted(expected_branches-covered)}")
    summary = summarize_execution_model(model, testcase_model)
    if strict and model.get("validation_status") == "passed" and summary["core_unpassed_count"]: errors.append("passed Execution Model 存在未通过最终 Branch")
    return list(dict.fromkeys(errors))

def main(argv=None) -> int:
    p=argparse.ArgumentParser(); p.add_argument("--execution",required=True,type=Path); p.add_argument("--testcase",required=True,type=Path); p.add_argument("--risk",required=True,type=Path); p.add_argument("--requirement",required=True,type=Path); p.add_argument("--defects",type=Path); p.add_argument("--draft",action="store_true"); a=p.parse_args(argv)
    try:
        load=lambda x: json.loads(x.read_text(encoding="utf-8-sig")); execution,testcase,risk,req=map(load,(a.execution,a.testcase,a.risk,a.requirement)); defects=load(a.defects) if a.defects else None
        if any(i.get("defect_ids") for i in execution.get("execution_instances",[])) and defects is None: errors=["Execution 引用 Defect 时 --defects 必填"]
        else: errors=validate_execution_model(execution,testcase_model=testcase,risk_model=risk,requirement_model=req,defect_model=defects,root=Path.cwd(),strict=not a.draft)
    except (OSError,json.JSONDecodeError) as exc: errors=[f"Execution context 无法读取：{exc}"]
    for e in errors: print("FAIL",e,file=sys.stderr)
    if 'execution' in locals():
        s=summarize_execution_model(execution,testcase); print(f"CONTEXT branches={s['branch_count']} instances={s['execution_instance_count']}")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}"); return 1 if errors else 0
if __name__=="__main__": raise SystemExit(main())
