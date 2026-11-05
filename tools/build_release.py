#!/usr/bin/env python3
"""Build deterministic source/payload ZIP with licensed, pinned ReShade SDK headers."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIRS = (".agents/skills/nfsuc-visual-modding", "docs", "configs", "tools", "tests", "shaders", "profiles", "native", "third_party")
FILES = ("AGENTS.md", "LICENSE", "README.md", "THIRD_PARTY.md", "VERSION", "CHANGELOG.md", "CMakeLists.txt")
ALLOWED = {".md", ".json", ".py", ".ps1", ".ini", ".fx", ".cpp", ".hpp", ".h", ".hlsl", ".def", ".in", ".txt"}


def build(root=ROOT, output=None):
    version = (root / "VERSION").read_text(encoding="ascii").strip()
    if not version or any(c not in "0123456789." for c in version):
        raise ValueError("Invalid version")
    output = output or root / "artifacts" / f"NFSUC-Visual-Foundation-{version}.zip"
    paths = [root / name for name in FILES]
    for directory in DIRS:
        for path in (root / directory).rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Symlink not distributable: {path}")
            if path.is_file() and "__pycache__" not in path.parts:
                if path.suffix not in ALLOWED:
                    raise ValueError(f"Unapproved file: {path}")
                paths.append(path)
    contents = {}
    for path in paths:
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError(f"Symlink not distributable: {path}")
        contents[path.relative_to(root).as_posix()] = path.read_bytes()
    manifest = {"schema": 1, "project": "NFS Undercover: Definitive Remaster",
                "version": version, "stage": "Native Foundation; local test candidate",
                "third_party_binaries": False, "game_assets": False, "third_party_sources": True,
                "files": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(contents.items())}}
    contents["MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(contents.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{sha}  {output.name}\n", encoding="ascii")
    return output, sha


def main():
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "tools/validate.py"], cwd=ROOT, check=True)
    path, sha = build()
    print(f"Created {path}\nSHA256 {sha}")


if __name__ == "__main__":
    main()
