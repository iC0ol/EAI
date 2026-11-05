#!/usr/bin/env python3
"""Run the user-authorized literature-only DeepSeek task independently of chat."""
from pathlib import Path
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import subprocess
import time
import uuid

TASK = Path(__file__).resolve().parents[1]
REPO = TASK.parent
BRANCH = "codex/spatial-action-survey-20261105"
MODEL = "deepseek-flash[1M]"
RUNTIME = TASK / "orchestration/runtime"
LOGS = TASK / "logs"
TOOLS = "Read,Write,Edit,Glob,Grep,Bash,WebSearch,WebFetch,TodoWrite"


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, obj):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def git(*args):
    return subprocess.check_output(
        ["git", "-C", str(REPO), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


def deliverables_complete():
    required = [
        "reports/FINAL_REPORT.md", "reports/EXECUTIVE_SUMMARY.md",
        "reports/SELF_AUDIT.md", "sources/papers.jsonl",
        "notes/search_log.md", "notes/nearest_neighbor_review.md",
    ]
    try:
        completion = json.loads((TASK / "reports/COMPLETION.json").read_text())
        audit_keys = [
            "seven_report_parts", "primary_sources_checked",
            "key_full_texts_read_or_access_limits_disclosed",
            "direct_competitors_and_classical_counterexamples",
            "action_metrics_and_confounds", "asset_and_resource_audit",
            "short_paper_and_thesis_continuity",
            "unknowns_and_negative_findings_disclosed", "no_experiments_performed",
        ]
        if completion.get("status") != "COMPLETE":
            return False
        if not all(completion.get("self_audit", {}).get(k) is True for k in audit_keys):
            return False
        if not all((TASK / p).is_file() and (TASK / p).stat().st_size > 0 for p in required):
            return False
        if git("status", "--porcelain", "--", str(TASK)):
            return False
        remote = git("ls-remote", "origin", "refs/heads/" + BRANCH)
        return bool(remote) and remote.split()[0] == git("rev-parse", "HEAD")
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    lock = (RUNTIME / "runner.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    original = (TASK / "USER_PROMPT.md").read_text()
    delegation = (TASK / "DELEGATION.md").read_text()
    session = str(uuid.uuid4())
    receipt = {
        "created_utc": now(), "runner_pid": os.getpid(), "workspace": str(REPO),
        "task_directory": str(TASK), "branch": BRANCH,
        "requested_model": MODEL, "session_id": session,
        "original_prompt_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "original_prompt_bytes": len(original.encode()),
        "delivery": "Claude Code CLI to the configured DeepSeek Anthropic-compatible endpoint",
        "first_assistant_utc": None, "response_model_fields": [],
    }
    write_json(RUNTIME / "dispatch_receipt.json", receipt)
    failures = 0
    round_number = 0
    use_resume = False
    system = (
        "You are the single user-authorized DeepSeek literature-research worker. "
        "Honor the current user's delegation and workspace instructions. "
        "Only this new task directory may be modified. Never run experiments, training, "
        "GPU/inference tests, installs, model/dataset downloads, or other agents. "
        "Paper downloads, original research documents, and scoped GitHub publication are authorized. "
        "Do not expose credentials. Read the complete attached research specification. "
        "Use actual primary sources, full texts when needed, and honest limitations. "
        "Continue working with tools until substantive deliverables are complete.\n\n"
        + (TASK / "AGENTS.md").read_text()
    )
    initial = delegation + "\n\n---\n以下是用户附件原文，须完整执行研究要求：\n\n" + original
    continuation = (
        delegation + "\n\n后台接续：你上轮已结束，但实质交付与远程发布尚未全部通过检查。"
        "不要重复计划或声称完成。先阅读 notes/research_state.md、已有笔记和报告，"
        "核查 reports/COMPLETION.json、缺失的来源/全文/查新/自检以及 Git 状态。"
        "针对真实缺口继续检索、阅读、修订和提交推送，直至交付完成。"
        "初始完整规范仍在 USER_PROMPT.md。全部候选不合格是允许的诚实结论。"
        "如遇真实不可消除的外部阻断，在 notes/research_state.md 中写明证据。"
    )
    while True:
        if (RUNTIME / "STOP").exists():
            write_json(RUNTIME / "status.json", {"state": "STOPPED", "utc": now()})
            return
        if git("branch", "--show-current") != BRANCH:
            write_json(RUNTIME / "status.json", {"state": "BLOCKED", "reason": "Workspace branch changed", "utc": now()})
            return
        blocked_path = TASK / "reports/BLOCKED.json"
        if blocked_path.exists():
            try:
                blocked = json.loads(blocked_path.read_text())
            except ValueError:
                blocked = {}
            if blocked.get("status") == "BLOCKED" and blocked.get("reason") and blocked.get("attempted_alternatives"):
                write_json(RUNTIME / "status.json", {"state": "BLOCKED", "utc": now(), "researcher_action_needed": blocked})
                return
        if round_number and deliverables_complete():
            write_json(RUNTIME / "status.json", {
                "state": "COMPLETE", "utc": now(), "rounds": round_number,
                "commit": git("rev-parse", "HEAD"), "branch": BRANCH,
            })
            return
        round_number += 1
        raw_path = LOGS / f"round_{round_number:04d}.jsonl"
        error_path = LOGS / f"round_{round_number:04d}.stderr"
        command = [
            "claude", "-p", "--resume" if use_resume else "--session-id", session,
            "--model", MODEL, "--tools", TOOLS, "--allowedTools", TOOLS,
            "--permission-mode", "dontAsk", "--strict-mcp-config",
            "--output-format", "stream-json", "--verbose",
            "--append-system-prompt", system,
        ]
        status = {
            "state": "RUNNING", "utc": now(), "round": round_number,
            "session_id": session, "model": MODEL,
            "raw_log": str(raw_path.relative_to(TASK)),
        }
        write_json(RUNTIME / "status.json", status)
        result = None
        had_assistant = False
        with raw_path.open("w") as raw, error_path.open("w") as err:
            process = subprocess.Popen(
                command, cwd=TASK, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=err, text=True, bufsize=1,
            )
            status["claude_pid"] = process.pid
            write_json(RUNTIME / "status.json", status)
            process.stdin.write(initial if round_number == 1 else continuation)
            process.stdin.close()
            for line in process.stdout:
                raw.write(line)
                raw.flush()
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "system" and event.get("subtype") == "init":
                    receipt["reported_init_model"] = event.get("model")
                    receipt["cli_session_id"] = event.get("session_id")
                    write_json(RUNTIME / "dispatch_receipt.json", receipt)
                if event.get("type") == "assistant":
                    had_assistant = True
                    message = event.get("message", {})
                    model = message.get("model")
                    if model and model not in receipt["response_model_fields"]:
                        receipt["response_model_fields"].append(model)
                    if not receipt["first_assistant_utc"]:
                        receipt["first_assistant_utc"] = now()
                    receipt["last_assistant_utc"] = now()
                    receipt["last_tool_names"] = [
                        p.get("name") for p in message.get("content", []) if p.get("type") == "tool_use"
                    ]
                    write_json(RUNTIME / "dispatch_receipt.json", receipt)
                    status["last_assistant_utc"] = now()
                    write_json(RUNTIME / "status.json", status)
                if event.get("type") == "result":
                    result = event
            returncode = process.wait()
        successful = returncode == 0 and result and not result.get("is_error") and result.get("subtype") == "success"
        if successful:
            failures = 0
            use_resume = True
            status.update({"state": "CONTINUING", "utc": now(), "last_exit_code": returncode})
            write_json(RUNTIME / "status.json", status)
            time.sleep(3)
            continue
        failures += 1
        result_text = json.dumps(result or {}, ensure_ascii=False).lower() + error_path.read_text().lower()
        context_exhausted = any(s in result_text for s in ["context window", "context limit", "maximum context", "prompt is too long"])
        if context_exhausted:
            session = str(uuid.uuid4())
            use_resume = False
            failures = 0
        elif had_assistant:
            use_resume = True
        status.update({"state": "RETRYING", "utc": now(), "last_exit_code": returncode, "consecutive_failures": failures})
        if failures >= 3:
            status.update({"state": "BLOCKED", "reason": "Three consecutive CLI/service failures; inspect local stderr and raw logs"})
            write_json(RUNTIME / "status.json", status)
            return
        write_json(RUNTIME / "status.json", status)
        time.sleep(15 if context_exhausted else 30 * failures)


if __name__ == "__main__":
    main()
