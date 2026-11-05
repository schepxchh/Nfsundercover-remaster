#!/usr/bin/env python3
"""Read-only PE32/D3D9 evidence. Never patches, executes or uploads input files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_SECTIONS = 96
MAX_IMPORT_DESCRIPTORS = 1024
MAX_THUNKS_PER_DLL = 16384
MAX_TOTAL_THUNKS = 65536
MAX_NAME_BYTES = 1024
SOURCE_BASE = 0x400000
SOURCE_ENTRYPOINT = 0x8AEC55
SOURCE_FILE_BYTES = 10584064
VISUAL_CANDIDATES = {"ForceCarLOD": 0x93CED8, "ForceTireLOD": 0x93CEDC}
EXOPTS_PIN = "21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b"


class ProbeError(ValueError):
    def __init__(self, message, category="malformed_or_unsupported"):
        super().__init__(message)
        self.category = category


def read_local(path: Path) -> bytes:
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ProbeError("Symlink input refused")
        if item.exists() and getattr(item.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
            raise ProbeError("Reparse-point input refused")
    if not path.is_file():
        raise ProbeError("Input must be a regular local file")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ProbeError("Input exceeds the 256 MiB analysis limit")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ProbeError("Input grew beyond the analysis limit")
    return data


def safe_text(data: bytes) -> str:
    # Untrusted names are metadata, never evaluated or used as output paths.
    return data.decode("utf-8", errors="replace")


class PE32:
    """A bounded PE32 metadata reader, not a Windows loader or executable validator."""

    def __init__(self, data: bytes):
        self.data = data
        self.sections = []
        self.span(0, 64, "DOS header")
        if data[:2] != b"MZ":
            raise ProbeError("DOS MZ signature missing")
        pe = self.u32(60)
        if pe < 64:
            raise ProbeError("PE header overlaps DOS header")
        self.span(pe, 24, "PE/COFF header")
        if data[pe:pe + 4] != b"PE\0\0":
            raise ProbeError("PE signature missing")
        self.machine = self.u16(pe + 4)
        section_count = self.u16(pe + 6)
        optional_bytes = self.u16(pe + 20)
        optional = pe + 24
        self.span(optional, optional_bytes, "optional header")
        if optional_bytes < 2 or self.u16(optional) != 0x10B:
            raise ProbeError("Only PE32 optional headers are supported", "incompatible_format")
        if optional_bytes < 96:
            raise ProbeError("Truncated PE32 optional header")
        if not 1 <= section_count <= MAX_SECTIONS:
            raise ProbeError("Section count exceeds supported bounds")
        self.entrypoint_rva = self.u32(optional + 16)
        self.image_base = self.u32(optional + 28)
        self.image_bytes = self.u32(optional + 56)
        self.header_bytes = self.u32(optional + 60)
        directory_count = self.u32(optional + 92)
        if directory_count > 16 or optional_bytes < 96 + directory_count * 8:
            raise ProbeError("Data-directory count does not fit supported optional header")
        table = optional + optional_bytes
        self.span(table, section_count * 40, "section table")
        if not table + section_count * 40 <= self.header_bytes <= len(data):
            raise ProbeError("SizeOfHeaders does not cover the section table within the file")
        if self.image_bytes < self.header_bytes:
            raise ProbeError("SizeOfImage is smaller than headers")
        if self.image_base + self.image_bytes > 0x100000000:
            raise ProbeError("Preferred image address range overflows PE32")
        for i in range(section_count):
            at = table + i * 40
            virtual_bytes, rva, raw_bytes, raw_offset = struct.unpack_from("<4I", data, at + 8)
            extent = max(virtual_bytes, raw_bytes)
            self.rva_bounds(rva, extent)
            if extent and rva < self.header_bytes:
                raise ProbeError("Section overlaps mapped headers")
            if raw_bytes:
                self.span(raw_offset, raw_bytes, "section raw data")
                if raw_offset < self.header_bytes:
                    raise ProbeError("Section raw data overlaps headers")
            flags = self.u32(at + 36)
            section = {"name": safe_text(data[at:at + 8].split(b"\0", 1)[0]),
                       "rva": rva, "virtual_bytes": virtual_bytes, "mapped_bytes": extent,
                       "raw_offset": raw_offset, "raw_bytes": raw_bytes,
                       "characteristics": flags, "readable": bool(flags & 0x40000000),
                       "writable": bool(flags & 0x80000000),
                       "executable": bool(flags & 0x20000000)}
            for previous in self.sections:
                if extent and previous["mapped_bytes"] and self.overlaps(rva, extent, previous["rva"], previous["mapped_bytes"]):
                    raise ProbeError("Overlapping section RVA ranges are ambiguous")
                if raw_bytes and previous["raw_bytes"] and self.overlaps(raw_offset, raw_bytes, previous["raw_offset"], previous["raw_bytes"]):
                    raise ProbeError("Overlapping section raw ranges are ambiguous")
            self.sections.append(section)
        self.rva_bounds(self.entrypoint_rva, 1)
        # An entrypoint may be virtual/unpacked. Report that fact; never read its code.
        self.entrypoint_location = self.location(self.entrypoint_rva, 1)
        if self.entrypoint_location["storage"] == "unmapped":
            raise ProbeError("Entrypoint RVA is not mapped by headers or a section")
        self.import_rva, self.import_bytes = (struct.unpack_from("<2I", data, optional + 104)
                                              if directory_count > 1 else (0, 0))

    @staticmethod
    def overlaps(a, a_bytes, b, b_bytes):
        return a < b + b_bytes and b < a + a_bytes

    def span(self, offset, size, label="file span"):
        if offset < 0 or size < 0 or offset > len(self.data) or size > len(self.data) - offset:
            raise ProbeError(f"{label} extends beyond file bounds")

    def u16(self, offset):
        self.span(offset, 2)
        return struct.unpack_from("<H", self.data, offset)[0]

    def u32(self, offset):
        self.span(offset, 4)
        return struct.unpack_from("<I", self.data, offset)[0]

    def rva_bounds(self, rva, size):
        if rva < 0 or size < 0 or rva > 0xFFFFFFFF or rva + size > 0x100000000:
            raise ProbeError("RVA arithmetic overflows PE32")
        if rva + size > self.image_bytes:
            raise ProbeError("RVA range exceeds SizeOfImage")

    def location(self, rva, size):
        self.rva_bounds(rva, size)
        if rva < self.header_bytes and rva + size <= self.header_bytes:
            return {"storage": "headers", "file_offset": rva, "section": None,
                    "section_declares_writable": False}
        for section in self.sections:
            delta = rva - section["rva"]
            if 0 <= delta and delta + size <= section["mapped_bytes"]:
                initialized = delta + size <= section["raw_bytes"]
                return {"storage": "initialized" if initialized else "virtual_only",
                        "file_offset": section["raw_offset"] + delta if initialized else None,
                        "section": section["name"], "section_declares_writable": section["writable"]}
        return {"storage": "unmapped", "file_offset": None, "section": None,
                "section_declares_writable": False}

    def offset(self, rva, size):
        loc = self.location(rva, size)
        if loc["file_offset"] is None:
            raise ProbeError("Import metadata is not backed by initialized file bytes")
        self.span(loc["file_offset"], size)
        return loc["file_offset"]

    def cstring(self, rva):
        offset = self.offset(rva, 1)
        if rva < self.header_bytes:
            available = self.header_bytes - rva
        else:
            available = next(s["raw_bytes"] - (rva - s["rva"]) for s in self.sections
                             if s["rva"] <= rva < s["rva"] + s["raw_bytes"])
        end = self.data.find(b"\0", offset, offset + min(available, MAX_NAME_BYTES))
        if end < 0:
            raise ProbeError("Unterminated or oversized import name")
        if end == offset:
            raise ProbeError("Empty import name")
        return safe_text(self.data[offset:end])

    def imports(self):
        if not self.import_rva and not self.import_bytes:
            return {"descriptor_count": 0, "d3d9": [], "Direct3DCreate9_imported": False}
        if not self.import_rva or self.import_bytes < 20:
            raise ProbeError("Incomplete import-directory location or size")
        base = self.offset(self.import_rva, self.import_bytes)
        count, total_thunks, result = 0, 0, []
        descriptor_limit = min(self.import_bytes // 20, MAX_IMPORT_DESCRIPTORS)
        terminated = False
        for index in range(descriptor_limit):
            values = struct.unpack_from("<5I", self.data, base + index * 20)
            if not any(values):
                terminated = True
                break
            lookup_rva, _, _, name_rva, iat_rva = values
            if not name_rva or not iat_rva:
                raise ProbeError("Import descriptor missing DLL name or IAT")
            dll = self.cstring(name_rva)
            selected = dll.casefold() == "d3d9.dll"
            functions = []
            thunk_rva = lookup_rva or iat_rva
            thunk_terminated = False
            for n in range(MAX_THUNKS_PER_DLL):
                total_thunks += 1
                if total_thunks > MAX_TOTAL_THUNKS:
                    raise ProbeError("Import thunk analysis limit exceeded")
                value = self.u32(self.offset(thunk_rva + n * 4, 4))
                # The corresponding IAT slot must exist, including the terminator.
                self.offset(iat_rva + n * 4, 4)
                if value == 0:
                    thunk_terminated = True
                    break
                if value & 0x80000000:
                    if value & 0x7FFF0000:
                        raise ProbeError("Reserved ordinal-import bits are set")
                    item = {"ordinal": value & 0xFFFF}
                else:
                    hint = self.u16(self.offset(value, 2))
                    name = self.cstring(value + 2)
                    item = {"name": name, "hint": hint}
                if selected:
                    functions.append(item)
            if not thunk_terminated:
                raise ProbeError("Import thunk table lacks terminator within analysis limit")
            count += 1
            if selected:
                result.append({"dll": dll, "functions": functions})
        if not terminated:
            raise ProbeError("Import descriptors lack terminator within directory/analysis limit")
        return {"descriptor_count": count, "d3d9": result,
                "Direct3DCreate9_imported": any(f.get("name") == "Direct3DCreate9"
                                               for dll in result for f in dll["functions"])}

    def visual_candidates(self):
        result = {}
        for name, rva in VISUAL_CANDIDATES.items():
            if rva + 4 > self.image_bytes:
                loc = {"storage": "outside_image", "file_offset": None, "section": None,
                       "section_declares_writable": False}
            else:
                loc = self.location(rva, 4)
            value = (struct.unpack_from("<i", self.data, loc["file_offset"])[0]
                     if loc["storage"] == "initialized" else None)
            result[name] = {"candidate_rva": hex(rva), **loc, "on_disk_int32": value,
                            "exopts_setting_default": -1,
                            "matches_exopts_setting_default": value == -1 if value is not None else None,
                            "address_applicability": "unverified; research candidate only",
                            "runtime_value": "not inspected"}
        return result


def pe_info(path: Path) -> dict:
    data = read_local(path)
    pe = PE32(data)
    imports = pe.imports()
    fingerprint = {"i386_pe32": pe.machine == 0x14C,
                   "file_size_matches_source_message": len(data) == SOURCE_FILE_BYTES,
                   "preferred_base_matches_research_assumption": pe.image_base == SOURCE_BASE,
                   "normalized_entrypoint_matches_source_check": SOURCE_BASE + pe.entrypoint_rva == SOURCE_ENTRYPOINT}
    return {"schema": 1, "file": str(path), "read_only": True, "sha256": hashlib.sha256(data).hexdigest(),
            "file_bytes": len(data), "machine": hex(pe.machine), "optional_header": "PE32",
            "image_base": hex(pe.image_base), "image_bytes": pe.image_bytes,
            "entrypoint_rva": hex(pe.entrypoint_rva),
            "preferred_entrypoint_va": hex(pe.image_base + pe.entrypoint_rva),
            "normalized_entrypoint_va": hex(SOURCE_BASE + pe.entrypoint_rva),
            "entrypoint_storage": pe.entrypoint_location["storage"], "sections": pe.sections,
            "imports": imports, "visual_candidates": pe.visual_candidates(),
            "assessment": {"classification": "structural_candidate" if all(fingerprint.values()) else "incompatible_fingerprint",
                           "fingerprint_checks": fingerprint, "approved_hash_allowlist_entries": 0,
                           "approved_hash_match": False, "runtime_compatibility": "unverified",
                           "explanation": "Source landmarks are not a build signature or proof of compatibility. No patch/write is authorized by this report."},
            "source": {"project": "ExOptsTeam/NFSUCExOpts", "commit": EXOPTS_PIN},
            "limitations": ["Not a complete Windows loader validator; no DRM/executable changes",
                            "Normal imports only; delay-load/dynamic GetProcAddress calls are not inferred",
                            "Writable section flags are on-disk declarations, not runtime page protections",
                            "ExOpts default -1 is not evidence of original game global values",
                            "Report includes paths, hashes, section layout and public D3D9 symbol names; no code bytes"]}


def shader_info(path: Path) -> dict:
    data = read_local(path)
    if len(data) < 8 or len(data) % 4:
        raise ProbeError("D3D9 token stream must contain aligned version and END DWORDs")
    version, end = struct.unpack_from("<I", data, 0)[0], struct.unpack_from("<I", data, len(data) - 4)[0]
    kind = {0xFFFF: "pixel", 0xFFFE: "vertex"}.get(version >> 16)
    if kind is None:
        raise ProbeError("D3D9 pixel/vertex shader version token missing", "incompatible_format")
    if end != 0x0000FFFF:
        raise ProbeError("Final DWORD is not a D3D9 END token")
    major, minor = (version >> 8) & 0xFF, version & 0xFF
    return {"schema": 1, "file": str(path), "read_only": True,
            "sha256": hashlib.sha256(data).hexdigest(), "file_bytes": len(data),
            "shader_type": kind, "shader_model": f"{major}.{minor}",
            "version_token": hex(version), "dword_count": len(data) // 4,
            "final_END_token": True,
            "assessment": "sm3_framing_candidate" if (major, minor) == (3, 0) else "other_shader_model_framing",
            "instruction_decode_performed": False, "runtime_compatibility": "unverified",
            "limitations": ["Only token-stream framing is checked, not instruction lengths, operands or control flow",
                            "An aligned file ending in END may still contain invalid shader bytecode",
                            "No disassembly, code bytes, compilation or execution is produced"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("pe-info", "shader-info"):
        command = sub.add_parser(action)
        command.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        report = pe_info(args.file) if args.action == "pe-info" else shader_info(args.file)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ProbeError) as exc:
        print(json.dumps({"read_only": True, "error": str(exc),
                          "assessment": getattr(exc, "category", "file_access_error"),
                          "runtime_compatibility": "unverified"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
