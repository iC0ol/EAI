#!/usr/bin/env python3
"""Fetch only the two approved π0.5 checkpoints with resumable file transfers."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import time


TASKS = ("stack_blocks_three", "place_phone_stand")
REPOSITORY = "https://huggingface.co/niejunnan25/pi05-robotwin"
REVISION = "17ef545270cf26ed81169893b60f845f80ce6557"
MANIFEST = "2337bd9e7244fc3f6d51b0b830a9cdfc8d6e683decf2c398a431bc5800696c41"
ASSETS = Path(__file__).resolve().parents[1] / "assets" / "policy"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verified(path, entry):
    return (
        path.is_file()
        and ("bytes" not in entry or path.stat().st_size == entry["bytes"])
        and ("sha256" not in entry or sha256(path) == entry["sha256"])
    )


def fetch(entry, verify_only):
    relative = entry["path"]
    destination = ASSETS / relative
    if verified(destination, entry):
        return
    if verify_only:
        raise ValueError(f"Missing or invalid checkpoint file: {relative}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    for attempt in range(5):
        if verified(partial, entry):
            partial.replace(destination)
            print(f"Verified {relative}", flush=True)
            return
        if partial.is_file() and partial.stat().st_size >= entry.get("bytes", float("inf")):
            partial.unlink()
        url = f"{REPOSITORY}/resolve/{REVISION}/{relative}"
        if attempt:
            url += f"?download=true&retry={time.time_ns()}"
        response = subprocess.run(
            [
                "curl", "--fail", "--silent", "--show-error", "--location",
                "--connect-timeout", "25", "--speed-time", "60", "--speed-limit", "1024",
                "--continue-at", "-", "--output", str(partial), url,
            ],
            check=False,
        )
        if response.returncode == 0 and verified(partial, entry):
            partial.replace(destination)
            print(f"Verified {relative}", flush=True)
            return
        time.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"Could not verify {relative}. Partial transfer retained at {partial}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", action="append", choices=TASKS, help="Defaults to both tasks.")
    parser.add_argument("--jobs", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    fetch({"path": "manifest.json", "sha256": MANIFEST}, args.verify_only)
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    entries = [
        manifest["tokenizer"],
        {"path": "TERMS.md", "sha256": "c5883dd0152dad353660b8583bced5d4f5837973dc2362a1fc5668bb1721b6d9"},
        {"path": "NOTICE", "sha256": "41cba3df605aa06eaa58af46152567057f7f45962995af273984a191aae27525"},
    ]
    by_task = {model["task"]: model for model in manifest["models"]}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for group in (entries, *(by_task[task]["files"] for task in (args.task or TASKS))):
            list(pool.map(lambda entry: fetch(entry, args.verify_only), group))
    print(f"Verified checkpoint assets at Hugging Face revision {REVISION}", flush=True)


if __name__ == "__main__":
    main()
