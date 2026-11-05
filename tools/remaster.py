#!/usr/bin/env python3
"""NFSUC Visual Foundation: isolated, hash-checked installer (Python 3.10+).

No executable injection, downloads, registry writes or game-data patches.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import struct
import sys
import tempfile
import zipfile

PROJECT = "nfsuc-visual-foundation"
VERSION = "0.3.0"
STATE = ".nfsuc-remaster-state"
PAYLOAD = {
    "nfsuc-remaster/Shaders/NFSUCFoundation.fx": "shaders/NFSUCFoundation.fx",
    **{f"nfsuc-remaster/Profiles/{name}.ini": f"profiles/{name}.ini"
       for name in ("Clean", "Hybrid", "Cinematic")},
}


class SafetyError(RuntimeError):
    """A conflict that must be resolved without overwriting user data."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reject_links(path: Path) -> None:
    # On Windows junctions and other reparse points can redirect writes too.
    for item in (path, *path.parents):
        if item.is_symlink():
            raise SafetyError(f"Symlink refused: {item}")
        if item.exists():
            attrs = getattr(item.stat(follow_symlinks=False), "st_file_attributes", 0)
            if attrs & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                raise SafetyError(f"Reparse point refused: {item}")


def safe_path(root: Path, relative: str) -> Path:
    parsed = PurePosixPath(relative)
    if (not relative or "\\" in relative or ":" in relative or parsed.is_absolute()
            or any(p in (".", "..") for p in relative.split("/"))):
        raise SafetyError(f"Unsafe relative path: {relative!r}")
    candidate = root.joinpath(*parsed.parts)
    reject_links(candidate)
    return candidate


def atomic_bytes(path: Path, data: bytes) -> None:
    reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".nfsuc-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_json(path: Path):
    reject_links(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise SafetyError(f"Cannot read state {path.name}: {error}") from error


def file_hash(path: Path):
    reject_links(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise SafetyError(f"Expected regular file: {path}")
    with path.open("rb") as stream:
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def validate_owned(owned):
    if not isinstance(owned, dict):
        raise SafetyError("Malformed owned-file state")
    for name, sha in owned.items():
        if name not in PAYLOAD or not valid_hash(sha):
            raise SafetyError("State contains an unapproved path or hash")
    return owned


def valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        raise SafetyError("Malformed installer lock; inspect before removing it")
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        kernel.GetExitCodeProcess.restype = ctypes.c_int
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.restype = ctypes.c_int
        handle = kernel.OpenProcess(0x1000, False, pid)  # query only; never terminate
        if not handle:
            # ERROR_INVALID_PARAMETER means no such PID; access denied stays alive.
            return ctypes.get_last_error() != 87
        try:
            status = ctypes.c_uint32()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(status)):
                return True
            return status.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Manager:
    def __init__(self, game_dir, source=None):
        self.root = Path(os.path.abspath(game_dir))
        reject_links(self.root)
        if not self.root.is_dir() or not safe_path(self.root, "nfs.exe").is_file():
            raise SafetyError("Game directory must contain nfs.exe; it is never modified")
        self.source = Path(source) if source else Path(__file__).resolve().parents[1]
        self.state = safe_path(self.root, STATE)

    @contextlib.contextmanager
    def locked(self):
        reject_links(self.state)
        if not self.state.exists():
            # Publish only a fully initialized state directory. A killed initializer
            # can leave an isolated staging dir, never an unusable active state.
            stage = Path(tempfile.mkdtemp(prefix=".nfsuc-state-init-", dir=self.root))
            try:
                atomic_bytes(stage / "owner.json", json_bytes({"project": PROJECT, "schema": 1}))
                try:
                    stage.rename(self.state)
                except OSError:
                    if not self.state.exists():
                        raise
            finally:
                if stage.exists():
                    for member in stage.iterdir():
                        member.unlink()
                    stage.rmdir()
        self.validate_marker()
        lock = safe_path(self.state, "lock")
        try:
            handle = lock.open("x", encoding="utf-8")
        except FileExistsError as error:
            try:
                pid = int(lock.read_text(encoding="utf-8"))
            except (ValueError, OSError) as malformed:
                raise SafetyError("Unreadable installer lock. Close all installer processes before removing only the lock, then run restore.") from malformed
            if pid_alive(pid):
                raise SafetyError("Installer lock exists for a live or inaccessible process. Close it before retrying. Do not remove a live lock.") from error
            lock.unlink()  # dead process; journal handles interrupted writes
            try:
                handle = lock.open("x", encoding="utf-8")
            except FileExistsError as raced:
                raise SafetyError("Another installer acquired the lock; retry after it exits") from raced
        try:
            with handle:
                handle.write(str(os.getpid()))
            yield
        finally:
            lock.unlink()

    def validate_marker(self):
        marker = load_json(safe_path(self.state, "owner.json"))
        if marker != {"project": PROJECT, "schema": 1}:
            raise SafetyError("Unrecognized state directory")

    def owned(self):
        path = safe_path(self.state, "owned.json")
        return validate_owned(load_json(path)) if path.exists() else {}

    def payload(self):
        result = {}
        for destination, source in PAYLOAD.items():
            path = safe_path(self.source, source)
            if not path.is_file():
                raise SafetyError(f"Missing package file: {source}")
            result[destination] = path.read_bytes()
        return result

    def preflight(self, old, desired):
        for name in set(old) | set(desired):
            current = file_hash(safe_path(self.root, name))
            if name in old and current != old[name]:
                raise SafetyError(f"Owned file was changed or removed; preserved: {name}")
            if name not in old and current is not None:
                raise SafetyError(f"Foreign file exists; preserved: {name}")

    def plan(self, action):
        if self.state.exists():
            self.validate_marker()
            if safe_path(self.state, "journal.json").exists():
                raise SafetyError("Interrupted transaction detected; run restore first")
        old = self.owned() if self.state.exists() else {}
        desired = self.payload() if action == "install" else {}
        self.preflight(old, desired)
        return {"action": action, "module": "postfx", "dry_run": True,
                "files": sorted(set(old) | set(desired)),
                "game_files_changed": False, "reshade_configuration_changed": False}

    def transact(self, action, dry_run=False):
        if dry_run:
            return self.plan(action)
        with self.locked():
            journal_path = safe_path(self.state, "journal.json")
            if journal_path.exists():
                raise SafetyError("Interrupted transaction detected; run restore first")
            old = self.owned()
            desired = self.payload() if action == "install" else {}
            self.preflight(old, desired)
            new = {name: digest(data) for name, data in desired.items()}
            if old == new:
                return {"action": action, "changed": False, "message": "Already in requested state"}
            entries = []
            for name in sorted(set(old) | set(new)):
                before, after = old.get(name), new.get(name)
                if before:
                    self.store_blob(safe_path(self.root, name).read_bytes())
                if after:
                    self.store_blob(desired[name])
                entries.append({"path": name, "before": before, "after": after})
            journal = {"schema": 1, "action": action, "before_owned": old,
                       "after_owned": new, "entries": entries}
            atomic_bytes(journal_path, json_bytes(journal))
            # Journal reaches disk before any owned payload file changes.
            for entry in entries:
                self.write_blob(entry["path"], entry["after"])
            atomic_bytes(self.state / "owned.json", json_bytes(new))
            atomic_bytes(self.state / "last.json", json_bytes(journal))
            journal_path.unlink()
            self.clean_empty_payload_dirs()
            return {"action": action, "module": "postfx", "changed": True,
                    "files": [e["path"] for e in entries], "restore_available": True}

    def store_blob(self, data):
        name = digest(data)
        target = safe_path(self.state, f"backups/{name}")
        if target.exists() and file_hash(target) != name:
            raise SafetyError("Backup content hash mismatch")
        if not target.exists():
            atomic_bytes(target, data)

    def blob(self, sha):
        if not valid_hash(sha):
            raise SafetyError("Invalid backup hash")
        path = safe_path(self.state, f"backups/{sha}")
        if file_hash(path) != sha:
            raise SafetyError("Backup missing or corrupt; no restoration performed")
        return path.read_bytes()

    def write_blob(self, relative, sha):
        if relative not in PAYLOAD:
            raise SafetyError("Unapproved payload path")
        path = safe_path(self.root, relative)
        if sha is None:
            if path.exists():
                path.unlink()
        else:
            atomic_bytes(path, self.blob(sha))

    def restore(self, dry_run=False):
        if not self.state.exists():
            raise SafetyError("No installer state exists")
        self.validate_marker()
        with (contextlib.nullcontext() if dry_run else self.locked()):
            pending = safe_path(self.state, "journal.json")
            completed = safe_path(self.state, "last.json")
            path = pending if pending.exists() else completed
            if not path.exists():
                raise SafetyError("No transaction to restore")
            journal = load_json(path)
            if not isinstance(journal, dict) or journal.get("schema") != 1:
                raise SafetyError("Malformed journal")
            before = validate_owned(journal.get("before_owned"))
            after = validate_owned(journal.get("after_owned"))
            expected = [{"path": name, "before": before.get(name), "after": after.get(name)}
                        for name in sorted(set(before) | set(after))]
            if journal.get("entries") != expected:
                raise SafetyError("Journal entries do not match approved state")
            # Check every conflict and every backup before making any changes.
            for entry in expected:
                current = file_hash(safe_path(self.root, entry["path"]))
                if current not in (entry["before"], entry["after"]):
                    raise SafetyError(f"File changed since transaction; preserved: {entry['path']}")
                if entry["before"]:
                    self.blob(entry["before"])
            if dry_run:
                return {"action": "restore", "dry_run": True, "files": [e["path"] for e in expected]}
            # Keep journal until restore finishes; repeated restore is idempotent after a crash.
            if not pending.exists():
                atomic_bytes(pending, json_bytes(journal))
            for entry in expected:
                self.write_blob(entry["path"], entry["before"])
            atomic_bytes(self.state / "owned.json", json_bytes(before))
            if completed.exists():
                completed.unlink()
            pending.unlink()
            self.clean_empty_payload_dirs()
            return {"action": "restore", "changed": True, "files": [e["path"] for e in expected]}

    def clean_empty_payload_dirs(self):
        for name in ("nfsuc-remaster/Shaders", "nfsuc-remaster/Profiles", "nfsuc-remaster"):
            path = safe_path(self.root, name)
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()


def pe_info(path):
    result = {"machine": None, "optional_header": None, "file_version": None}
    try:
        with path.open("rb") as stream:
            header = stream.read(64)
            if len(header) != 64 or header[:2] != b"MZ":
                result["error"] = "Not a DOS/PE executable"
                return result
            offset = struct.unpack_from("<I", header, 60)[0]
            stream.seek(offset)
            pe = stream.read(26)
            if len(pe) != 26 or pe[:4] != b"PE\0\0":
                result["error"] = "PE signature missing"
                return result
            result["machine"] = hex(struct.unpack_from("<H", pe, 4)[0])
            result["optional_header"] = hex(struct.unpack_from("<H", pe, 24)[0])
        if os.name == "nt":
            result["file_version"] = windows_version(path)
    except (OSError, ValueError, struct.error) as error:
        result["error"] = str(error)
    return result


def windows_version(path):
    # Windows' documented version-resource APIs; absent resources remain unknown.
    dll = ctypes.WinDLL("version", use_last_error=True)
    size_fn = dll.GetFileVersionInfoSizeW
    size_fn.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
    size_fn.restype = ctypes.c_uint32
    ignored = ctypes.c_uint32()
    size = size_fn(str(path), ctypes.byref(ignored))
    if not size:
        return None
    data = ctypes.create_string_buffer(size)
    get_fn = dll.GetFileVersionInfoW
    get_fn.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    get_fn.restype = ctypes.c_int
    if not get_fn(str(path), 0, size, data):
        return None
    query = dll.VerQueryValueW
    query.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint)]
    query.restype = ctypes.c_int
    pointer, length = ctypes.c_void_p(), ctypes.c_uint()
    if not query(data, "\\", ctypes.byref(pointer), ctypes.byref(length)) or length.value < 52:
        return None
    values = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))
    if values[0] != 0xFEEF04BD:
        return None
    high, low = values[2], values[3]
    return f"{high >> 16}.{high & 65535}.{low >> 16}.{low & 65535}"


def diagnostic(game_dir):
    manager = Manager(game_dir)
    files, warnings = [], []
    # Bounded inventory, never traversing junctions, and no game assets read into reports.
    for folder in (manager.root, manager.root / "scripts", manager.root / "plugins"):
        reject_links(folder)
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in (".exe", ".dll", ".asi", ".ini", ".cfg", ".json", ".log"):
                continue
            reject_links(path)
            if not path.is_file():
                continue
            entry = {"path": path.relative_to(manager.root).as_posix(),
                     "size": path.stat().st_size, "sha256": file_hash(path)}
            if path.suffix.lower() in (".exe", ".dll", ".asi"):
                entry["pe"] = pe_info(path)
            if path.suffix.lower() in (".ini", ".cfg"):
                # Report configuration as evidence, without inferring that keys exist in installed ASI.
                entry["configuration"] = path.read_text(encoding="utf-8-sig", errors="replace")
            files.append(entry)
    names = {e["path"].lower() for e in files}
    proxy_names = sorted(n for n in names if n in {"d3d9.dll", "dxgi.dll", "dinput8.dll", "dsound.dll", "winmm.dll", "version.dll"})
    if proxy_names:
        warnings.append("Proxy/loader files present: " + ", ".join(proxy_names) + ". Names do not identify their provider. Do not overwrite; inspect publisher/version and ReShade.log.")
    if "d3d9.dll" in names and "dxgi.dll" in names:
        warnings.append("Both d3d9.dll and dxgi.dll exist. Undercover targets DX9; investigate existing wrappers before installing ReShade.")
    asi = [n for n in names if n.endswith(".asi")]
    if len(asi) != len({Path(n).name for n in asi}):
        warnings.append("Duplicate ASI filenames in loader folders may load twice.")
    exe = next((e for e in files if e["path"].lower() == "nfs.exe"), None)
    if not exe or exe.get("pe", {}).get("file_version") != "1.0.0.1":
        warnings.append("Steam nfs.exe 1.0.0.1 has not been established by version resources. Hashes are evidence, not an approved-build allowlist.")
    return {"project": PROJECT, "version": VERSION, "game_dir": str(manager.root),
            "files": files, "warnings": warnings, "compatibility": "requires-in-game-test",
            "fusionfix_changed": False, "dlls_changed": False,
            "privacy": "Report contains local paths, INI settings and file hashes. Review before sharing."}


def output_path(value, root):
    path = Path(os.path.abspath(value))
    reject_links(path)
    if path == root or root in path.parents:
        raise SafetyError("Report/backup output must be outside the game directory")
    if path.exists():
        raise SafetyError("Output already exists; choose a new filename")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("diagnose", "install", "uninstall", "restore", "backup"))
    parser.add_argument("--game-dir", required=True, help="Directory containing nfs.exe")
    parser.add_argument("--module", choices=("postfx",), default="postfx")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", help="New report JSON or backup ZIP outside game folder")
    args = parser.parse_args(argv)
    try:
        manager = Manager(args.game_dir)
        if args.action in ("install", "uninstall"):
            result = manager.transact(args.action, args.dry_run)
        elif args.action == "restore":
            result = manager.restore(args.dry_run)
        else:
            result = diagnostic(args.game_dir)
            if args.action == "backup":
                if not args.output:
                    raise SafetyError("backup requires --output OUTSIDE_GAME.zip")
                if args.dry_run:
                    result = {"action": "backup", "dry_run": True, "output": args.output}
                else:
                    target = output_path(args.output, manager.root)
                    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                        archive.writestr("diagnostics.json", json_bytes(result))
                        for item in result["files"]:
                            if "configuration" in item:
                                archive.writestr("configs/" + item["path"], safe_path(manager.root, item["path"]).read_bytes())
                    result = {"action": "backup", "output": str(target), "scope": "INI/CFG configs and hash inventory; not exe/game assets"}
            elif args.output and not args.dry_run:
                target = output_path(args.output, manager.root)
                with target.open("xb") as stream:
                    stream.write(json_bytes(result))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (SafetyError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
