"""Extract the official RoboTwin assets needed by the two demo_clean tasks."""

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import time
from urllib.request import Request, urlopen
import zipfile


ASSETS = Path(__file__).resolve().parents[1] / "assets/sim"
REPOSITORY = "TianxingChen/RoboTwin2.0"
REVISION = "3dc3b798668feb99ac61cc9086d84cbcc3d79186"
ARCHIVES = {
    "embodiments.zip": {
        "size": 219_847_741,
        "repository_sha256": "85ffeff55a5066def5931224a85cfa3f8abaa1fbf779bd17789a7fb3f85bc789",
        "prefixes": ("embodiments/aloha-agilex/",),
    },
    "objects.zip": {
        "size": 3_737_778_549,
        "repository_sha256": "6aa56b3cf1e1064f7c809308144da36b00815f8b137fef2d7e4de856f8becf27",
        "prefixes": ("objects/077_phone/", "objects/078_phonestand/", "objects/objaverse/list.json", "objects/same.json"),
    },
}


class RemoteArchive(io.RawIOBase):
    """Expose a pinned large ZIP as a seekable stream backed by HTTP ranges."""

    def __init__(self, name, size):
        self.url = f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/{name}"
        self.size = size
        self.offset = 0
        self.ranges = []

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.offset

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.offset, io.SEEK_END: self.size}[whence]
        if base + offset < 0:
            raise OSError("Cannot seek before the beginning of the remote archive")
        self.offset = base + offset
        return self.offset

    def prefetch(self, start, end):
        request = Request(
            f"{self.url}?download=true&segment={start}-{end - 1}",
            headers={"Range": f"bytes={start}-{end - 1}"},
        )
        expected = f"bytes {start}-{end - 1}/{self.size}"
        for attempt in range(3):
            try:
                with urlopen(request, timeout=90) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != expected:
                        raise OSError(f"Expected {expected}, got HTTP {response.status} {response.headers.get('Content-Range')}")
                    data = response.read(end - start + 1)
                    if len(data) != end - start:
                        raise OSError(f"Truncated range {start}-{end - 1}")
                    self.ranges.append((start, end, data))
                    return data
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def read(self, size=-1):
        start = self.offset
        end = self.size if size < 0 else min(start + size, self.size)
        if end <= start:
            return b""
        self.offset = end
        for cached_start, cached_end, data in self.ranges:
            if cached_start <= start and end <= cached_end:
                return data[start - cached_start:end - cached_start]
        return self.prefetch(start, end)


def extract_zip(name, spec, destination):
    with RemoteArchive(name, spec["size"]) as remote, zipfile.ZipFile(remote) as archive:
        members = sorted(archive.infolist(), key=lambda info: info.header_offset)
        spans = []
        for index, member in enumerate(members):
            path = PurePosixPath(member.filename)
            if member.is_dir() or not member.filename.startswith(spec["prefixes"]):
                continue
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unexpected ZIP member {member.filename!r}")
            start = member.header_offset
            end = members[index + 1].header_offset if index + 1 < len(members) else archive.start_dir
            if spans and start - spans[-1][1] <= 256 * 1024 and end - spans[-1][0] < 64 * 1024**2:
                previous_start, _, previous_members = spans[-1]
                spans[-1] = (previous_start, end, [*previous_members, member])
            else:
                spans.append((start, end, [member]))
        if not spans:
            raise ValueError(f"No members found for {spec['prefixes']} in {name}")

        files = []
        for start, end, selected in spans:
            print(f"{name}: fetching {end - start:,} bytes for {len(selected)} files", flush=True)
            remote.ranges.clear()
            remote.prefetch(start, end)
            for member in selected:
                path = destination / member.filename
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, path.open("wb") as target:
                    shutil.copyfileobj(source, target)
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for content in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(content)
                files.append({"path": member.filename, "bytes": member.file_size, "sha256": digest.hexdigest()})
        for prefix in spec["prefixes"]:
            if not any(file["path"].startswith(prefix) for file in files):
                raise ValueError(f"Missing asset directory {prefix}")
        return {**spec, "ranges": [[start, end] for start, end, _ in spans], "files": files}


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    installed = ASSETS / "robotwin"
    if installed.exists():
        raise FileExistsError(f"Assets are already present at {installed}")
    with tempfile.TemporaryDirectory(dir=ASSETS, prefix=".extract-") as temporary:
        output = Path(temporary) / "robotwin"
        archives = {name: extract_zip(name, spec, output) for name, spec in ARCHIVES.items()}
        manifest = {"repository": REPOSITORY, "revision": REVISION, "archives": archives}
        (output / "asset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.rename(output, installed)


if __name__ == "__main__":
    main()
