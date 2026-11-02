"""CPU-only publication allowlist, content audit, and delivery fingerprints."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image

P = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {"local_only", "logs", "cache", ".cache", "__pycache__", "tmp", "temp"}
EXCLUDED_FILES = {"active_child.json", "counter.lock", "run.lock", "machine_before.json"}
METADATA = {"public_allowlist.txt", "public_secret_scan.json", "publication_manifest.json"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".txt", ".diff"}
PATTERNS = {
    "openai_token": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}\b"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "aws_access_id": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "credential_assignment": re.compile(
        r'''["']?(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|passwd)["']?\s*[:=]\s*["'][^"'\n]{12,}["']''', re.I),
    "bearer_value": re.compile(r"\bBearer\s+[A-Za-z0-9_.-]{24,}\b"),
    "credential_url": re.compile(r"https?://[^\s/:]+:[^\s/@]+@", re.I),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (P / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    allowed = []
    excluded = []
    for path in sorted(P.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(P)
        if any(part in EXCLUDED_PARTS for part in rel.parts) or path.name in EXCLUDED_FILES:
            excluded.append(str(rel))
            continue
        if path.is_symlink():
            raise RuntimeError("symlink is not a publication asset")
        if path.suffix not in TEXT_SUFFIXES | {".npy", ".npz", ".png"} and path.name != ".gitignore":
            raise RuntimeError("unclassified publication asset: " + str(rel))
        if str(rel) not in METADATA:
            allowed.append(str(rel))
    all_names = sorted(set(allowed) | METADATA)
    (P / "public_allowlist.txt").write_text("\n".join(all_names) + "\n")
    findings = []
    numeric_arrays = []
    images = []
    text_count = 0

    def scan(name, value):
        for kind, pattern in PATTERNS.items():
            count = len(pattern.findall(value))
            if count:
                # Deliberately never disclose matched credential contents.
                findings.append(dict(file=name, rule=kind, count=count))

    for name in sorted(set(allowed) | {"public_allowlist.txt"}):
        path = P / name
        if path.suffix == ".npy":
            arrays = {"array": np.load(path, allow_pickle=False)}
        elif path.suffix == ".npz":
            with np.load(path, allow_pickle=False) as source:
                arrays = {key: source[key].copy() for key in source.files}
        else:
            arrays = None
        if arrays is not None:
            for key, array in arrays.items():
                if array.dtype.kind not in "biufc":
                    raise RuntimeError("non-numeric publication array: " + name)
                if not np.isfinite(array).all():
                    raise RuntimeError("non-finite array: " + name)
                numeric_arrays.append(dict(file=name, key=key, shape=list(array.shape),
                                           dtype=str(array.dtype), allow_pickle=False))
            continue
        if path.suffix == ".png":
            with Image.open(path) as image:
                image.load()
                scan(name + ":metadata", json.dumps(image.info))
                images.append(dict(file=name, size=list(image.size), mode=image.mode))
            continue
        scan(name, path.read_text())
        text_count += 1
    report = dict(utc=datetime.now(timezone.utc).isoformat(), passed=not findings,
                  scope="only explicitly allowlisted original code and small result artifacts",
                  text_files_scanned=text_count, credential_rules=list(PATTERNS), findings=findings,
                  matched_values_disclosed=False, numeric_arrays_checked=numeric_arrays,
                  images_checked=images, excluded=excluded,
                  exclusions="raw CLI logs, address/XML/source snapshots, runtime/cache/temp/lock and active-child state",
                  runtimes_weights_datasets_credentials_included=False,
                  Git_index_owner="main", executor_Git_writes=0,
                  limitation="pattern scan and numeric-array validation; independent publisher review remains required")
    write("public_secret_scan.json", report)
    # Include stable per-file hashes; omit the manifest's own recursive hash.
    entries = [dict(path=name, bytes=(P / name).stat().st_size, sha256=sha(P / name))
               for name in all_names if name != "publication_manifest.json"]
    manifest = dict(utc=report["utc"], files=entries,
          manifest_self_hash="OMITTED_TO_AVOID_RECURSION", allowed_file_count=len(all_names),
          executor_has_not_staged_committed_or_pushed=True, scope_disk_bytes_at_audit=0)
    write("publication_manifest.json", manifest)
    # The digit width settles immediately; include this manifest in the total.
    for _ in range(3):
        manifest["scope_disk_bytes_at_audit"] = sum(f.stat().st_size for f in P.rglob("*") if f.is_file())
        write("publication_manifest.json", manifest)
    disk_bytes = sum(f.stat().st_size for f in P.rglob("*") if f.is_file())
    if disk_bytes > 150 * 2**20:
        raise RuntimeError("delivery disk cap exceeded")
    print(json.dumps(dict(passed=report["passed"], allowlisted_files=len(all_names),
                          text_files_scanned=text_count, numeric_arrays_checked=len(numeric_arrays),
                          images_checked=len(images), credential_findings=len(findings), disk_bytes=disk_bytes)))
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
