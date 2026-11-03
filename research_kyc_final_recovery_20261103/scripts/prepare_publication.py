"""Explicit public bundle; preserve originals and redact process addresses in copies."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

P = Path(__file__).resolve().parents[1]
PUB = P / "publication"
PUB.mkdir(exist_ok=True)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n")

now = datetime.now(timezone.utc).isoformat()
receipts = []
for p in sorted((P / "discussion").glob("*_metadata.json")):
    d = json.loads(p.read_text())
    base = p.name.removesuffix("_metadata.json")
    receipt = {k:d.get(k) for k in ["turn", "started_utc", "ended_utc", "exit_code", "result_status", "permission_denials", "response_model_fields"]}
    receipt["valid_review"] = d.get("exit_code") == 0
    receipt["source_metadata_sha256"] = sha(p)
    receipt["raw_CLI_sha256"] = sha(P / "discussion" / (base + "_raw.jsonl"))
    receipt["prompt_sha256"] = sha(P / "discussion" / (base + "_prompt.md"))
    receipt["response_sha256"] = sha(P / "discussion" / (base + "_response.md"))
    receipt["prompt"] = "discussion/" + base + "_prompt.md"
    receipt["response"] = "discussion/" + base + "_response.md"
    if base == "32_candidate_independent":
        receipt["limitation"] = "API400 context full; result_status alone misleading; exit1, NO VALID APPROVAL"
    if base == "36_model_independent":
        receipt["independence_scope"] = "Read original JSON arrays and runtime artifacts before Codex notes08; no separate executable arithmetic script"
    receipts.append(receipt)
dump(PUB / "deepseek_receipts.json", {"utc":now, "transport":"existing terminal Claude connection", "raw_CLI_and_credentials":"local only", "receipts":receipts})

top = [
    ".gitignore", "AGENTS.md", "00_本轮用户任务书_原文.md", "01_有限恢复边界与阶段门.md",
    "02_联合验收与研究决策报告.md", "FINAL_REPORT.md", "README.md", "STATUS.md", "completion.json",
    "PROTOCOL.md", "CPU_PREFLIGHT_REPORT.md", "CPU_PREFLIGHT_REPORT.json", "run.py",
    "call_plan.json", "sample_plan.json", "root_plan.json", "criteria_reference.md", "copied_sources.json",
    "repair_ledger.json", "candidate_manifest.json", "engineering_gate.json", "preflight_scope_gate.json",
    "scientific_freeze.json", "science_gate.json", "science_clock.json", "input_gate.json", "stage2_decision.json",
    "gpu_preflight_result.json", "input_result.json", "model_result.json", "analysis.json", "strict_load.json",
    "status.json", "recovery_state.json", "call_ledger.jsonl", "resources.jsonl", "commands.jsonl", "model_events.jsonl",
    "integrity_report.json"
]
candidates = {P/n for n in top if (P/n).is_file()}
for name in ["kyc_recovery", "candidate_diffs", "repairs", "cpu_preflight", "references", "notes", "inputs", "results", "artifacts", "review_packets", "stages", "scripts"]:
    candidates.update(f for f in (P/name).rglob("*") if f.is_file() and "__pycache__" not in f.parts)
for pattern in ["*_prompt.md", "*_response.md", "32_context_handoff.md"]:
    candidates.update((P/"discussion").glob(pattern))
for f in (P/"orchestration").iterdir():
    if any(s in f.name for s in ["dispatch", "executor_launch", "return_receipt", "supervisor_stdout", "cpu_analyze"]) or f.name in ["basis.json", "initial_joint_review_receipt.json", "deepseek_context_transition.json", "clocks.json"]:
        candidates.add(f)

export_map = []
for name in ["cpu_R1.log", "cpu_R2.log", "cpu_final.log", "cpu_preflight_traceback.log", "cpu_termination_test.log", "gpu-preflight.log", "s1-input.log", "s1-model.log"]:
    src = P/"logs"/name
    dest = PUB/"runtime_logs"/name
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Pointer text is private; retained raw log remains unchanged locally.
    text, count = re.subn(r"0x[0-9a-fA-F]{9,16}\b", "<native-address-redacted>", src.read_text())
    dest.write_text(text)
    export_map.append({"source":str(src.relative_to(P)), "source_sha256":sha(src), "public_copy":str(dest.relative_to(P)), "public_sha256":sha(dest), "native_pointer_strings_redacted":count})

def redact(v, path="", changes=None):
    if isinstance(v, dict):
        out = {}
        for k,x in v.items():
            if k == "module_id":
                changes.append(path+"/"+k)
                out[k] = "PROCESS_ADDRESS_REDACTED"
            else:
                out[k] = redact(x,path+"/"+k,changes)
        return out
    if isinstance(v,list):
        return [redact(x,path+"/"+str(i),changes) for i,x in enumerate(v)]
    if isinstance(v,str):
        value,n = re.subn(r"0x[0-9a-fA-F]{9,16}\b", "<native-address-redacted>", v)
        if n: changes.append(path)
        return value
    return v

allowed = set()
for p in sorted(candidates):
    assert p.suffix not in [".pyc", ".pt", ".pth", ".h5", ".hdf5", ".xml", ".lock", ".tmp"], p
    changes = []
    if p.suffix == ".json":
        original = json.loads(p.read_text())
        safe = redact(original, changes=changes)
        if changes:
            dest=PUB/"redacted"/p.relative_to(P)
            dump(dest,safe)
            export_map.append({"source":str(p.relative_to(P)), "source_sha256":sha(p), "public_copy":str(dest.relative_to(P)), "public_sha256":sha(dest), "redacted_json_paths":changes})
            allowed.add(dest)
            continue
    allowed.add(p)

dump(PUB/"export_map.json", {"utc":now,"originals_unchanged":True,"exports":export_map})
(PUB/"README.md").write_text('''# 公开证据说明

原始科学小结果完整公开：4个固定输入NPZ、12张RGB及读回/保存边界、16个ACT输出NPZ与JSON、严格加载、调用/资源/阶段账本、专家与两常数、完整分析和父审独立重算。它们仅为本轮固定样本，不是完整训练数据集。

CPU/GPU模块来源证据中的 `module_id` 是CPython进程地址；为遵守不公开原生地址的协议，这些原件保留本地，公开副本位于 `redacted/`。仅替换这些地址及长十六进制原生指针字符串，路径、hash、sys.modules同一对象判断、错误/预算/科学数值不改变。小整数GL对象编号不是原生指针，保留以核查FBO/RBO事件。[export_map.json](export_map.json) 精确记录原路径、原件SHA、导出SHA及删减字段。manifest引用原件hash而非导出hash，不把两者混称同一原件。

运行日志的公开副本在 `runtime_logs/`，原log的hash和指针替换数在导出清单。DeepSeek真实响应与原prompt保留；[deepseek_receipts.json](deepseek_receipts.json) 记录每轮时间、退出码、返回模型字段、原始CLI/metadata及公开响应hash。原CLI、会话档、累计计费信息和凭据不公开。第32轮上下文满失败未被当作批准，32b起为真实续接的新会话。

执行代码/修复差异/冻结前协议原文保持原字节，不为了当前状态重写。原代码含只读运行环境路径，这不是环境本体；Python环境、权重、完整数据、XML、cache、local_only、私钥与API凭据全部排除。

[final_public_allowlist.txt](../final_public_allowlist.txt) 是唯一staging集合；[final_publication_manifest.json](../final_publication_manifest.json) 绑定稳定证据。STATUS、completion、clocks及本目录远程/自动检查关闭回执属于可变交付记录，不纳入稳定证据hash，避免自引用；它们由Git提交记录绑定。清单/扫描/manifest自身也不参与自身hash。秘密扫描是本次内容检查，不能视为对任意未来文件的安全保证。

未被公开的原件仍在本地原路径，不删除旧结果。[remote_verification.json](remote_verification.json) 记录实际远程SHA与校验结果。
''')
allowed.update(f for f in PUB.rglob("*") if f.is_file())
relative = sorted(str(f.relative_to(P)) for f in allowed)
closure = {"STATUS.md", "completion.json", "orchestration/clocks.json", "final_public_allowlist.txt", "final_publication_manifest.json", "final_secret_scan.json", "publication/remote_verification.json", "publication/automation_closure.json"}
allowlist_names = sorted(set(relative) | {"final_public_allowlist.txt", "final_publication_manifest.json", "final_secret_scan.json"})
(P/"final_public_allowlist.txt").write_text("\n".join(allowlist_names)+"\n")
manifest = {"utc":now,"scope":"stable published evidence, not mutable delivery records","excluded_mutable_delivery_records":sorted(closure),"files":{n:{"sha256":sha(P/n),"bytes":(P/n).stat().st_size} for n in relative if n not in closure}}
dump(P/"final_publication_manifest.json",manifest)

patterns = {
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "github_token": r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
    "api_token": r"\bsk-[A-Za-z0-9_-]{20,}",
    "bearer_value": r"Bearer\s+[A-Za-z0-9._~-]{20,}",
    "url_user_password": r"https?://[^\s/:]+:[^\s/@]+@",
    "aws_access_key": r"\bAKIA[A-Z0-9]{16}\b",
    "native_pointer_string": r"\b0x[0-9a-fA-F]{9,16}\b",
    "literal_secret_assignment": r'''(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*[=:]\s*["'][A-Za-z0-9_./+=-]{20,}["']'''
}
findings=[]
for name in allowlist_names:
    f=P/name
    if not f.exists() or f.suffix in [".npz", ".npy", ".png", ".pdf"]: continue
    text=f.read_text()
    for label,pattern in patterns.items():
        for m in re.finditer(pattern,text):
            findings.append({"file":name,"line":text[:m.start()].count("\n")+1,"rule":label})
dump(P/"final_secret_scan.json", {"utc":now,"state":"PASS" if not findings else "REVIEW_REQUIRED","allowlist_sha256":sha(P/"final_public_allowlist.txt"),"files":len(allowlist_names),"patterns":list(patterns),"findings":findings,"binary_policy":"Only known local numpy numeric arrays and inspected figures; archives, weights, environments, XML and CLI sessions excluded","originals_preserved":True})
print(json.dumps({"allowed_files":len(allowlist_names),"stable_evidence_bytes":sum(v["bytes"] for v in manifest["files"].values()),"redacted_or_log_exports":len(export_map),"findings":findings},ensure_ascii=False))
if findings: raise SystemExit(2)
