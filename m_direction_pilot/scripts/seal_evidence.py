"""Seal final compact evidence only after reporting, plot inspection and tests."""
from m_direction.io import ROOT, OUT, REPORT, sha256, read_json, write_json

files = [ROOT/"README.md", ROOT/".gitignore", ROOT/".gitattributes"]
for base in [ROOT/"src", ROOT/"scripts", ROOT/"tests", ROOT/"configs", OUT, REPORT]:
    files.extend(p for p in base.rglob("*") if p.is_file() and p.name not in ["sha256_manifest.json", ".ledger.lock"])
traces = read_json(OUT/"local_trace_index.json")
for t in traces:
    assert sha256(ROOT/t["path"]) == t["sha256"]
write_json(OUT/"sha256_manifest.json", {
    "scope": "M source/config/compact records/reports, excluding this self-referential manifest and ledger lock",
    "sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sorted(set(files))}, "local_traces": traces})
print(f"Sealed {len(set(files))} files and {len(traces)} local trace hashes")
