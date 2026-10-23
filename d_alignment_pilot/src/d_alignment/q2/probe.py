"""Active filesystem-denial probe executed inside the same mount namespace."""
import argparse
from pathlib import Path

from .common import write_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--forbidden", action="append", default=[])
    args = p.parse_args()
    probes = []
    for path in args.forbidden:
        try:
            with Path(path).open("rb") as handle:
                handle.read(1)
        except (FileNotFoundError, PermissionError, IsADirectoryError) as exc:
            probes.append({"path": path, "denied": True, "exception": type(exc).__name__})
        else:
            raise AssertionError(f"Forbidden input visible: {path}")
    assert probes
    write_json(args.output, {"all_forbidden_reads_denied": True, "probes": probes,
                            "network_namespace": "unshared by bubblewrap", "gpu_devices_mounted": False})


if __name__ == "__main__":
    main()
