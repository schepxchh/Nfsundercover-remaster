#!/usr/bin/env python3
"""Read-only local asset inventory and strict legacy DDS preflight. Python 3.10+."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

BLOCK_BYTES = {"DXT1": 8, "DXT3": 16, "DXT5": 16, "ATI1": 8,
               "ATI2": 16, "BC4U": 8, "BC4S": 8, "BC5U": 16, "BC5S": 16}
CONTAINERS = {".bin", ".bun", ".lzc", ".bnd", ".dds", ".tpk", ".geometry"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dds_info(path: Path) -> dict:
    """No decoding, writes or container guessing. Reject malformed lengths early."""
    if path.is_symlink():
        raise ValueError("Symlink input refused")
    with path.open("rb") as stream:
        header = stream.read(148)
    if len(header) < 128 or header[:4] != b"DDS ":
        raise ValueError("Not a complete DDS header")
    words = struct.unpack_from("<31I", header, 4)
    if words[0] != 124 or words[18] != 32:
        raise ValueError("Invalid DDS or pixel-format header size")
    flags, height, width, depth, mip_field = words[1], words[2], words[3], words[5], words[6]
    if not (flags & 0x1000 and flags & 0x2 and flags & 0x4):
        raise ValueError("DDS missing required width/height/pixel-format flags")
    if not (1 <= width <= 65536 and 1 <= height <= 65536):
        raise ValueError("Invalid or unreasonable DDS dimensions")
    mip_count = mip_field if flags & 0x20000 else 1
    full_mips = max(width, height).bit_length()
    if not (1 <= mip_count <= full_mips):
        raise ValueError("Invalid mip count")
    pf_flags, code, bpp = words[19], words[20], words[21]
    fourcc = struct.pack("<I", code).decode("ascii", errors="replace") if pf_flags & 4 else None
    caps2 = words[27]
    complex_surface = bool(caps2 & (0x200 | 0x200000)) or depth > 1
    offset = 128
    warnings = []
    dx10 = None
    if fourcc == "DX10":
        if len(header) < 148:
            raise ValueError("Truncated DDS DX10 header")
        dx10 = dict(zip(("dxgi_format", "resource_dimension", "misc_flag", "array_size", "alpha_mode"),
                        struct.unpack_from("<5I", header, 128)))
        offset = 148
        warnings.append("DX10 header: not approved for the Undercover DX9 import path")
    if complex_surface:
        warnings.append("Cubemap/volume: surface layout requires tool-specific validation")
    sizes = []
    if not dx10 and not complex_surface:
        for level in range(mip_count):
            w, h = max(1, width >> level), max(1, height >> level)
            if fourcc in BLOCK_BYTES:
                count = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * BLOCK_BYTES[fourcc]
            elif fourcc is None and bpp in (8, 16, 24, 32):
                # DDS row pitch can include padding; do not certify unknown padding.
                count = ((w * bpp + 7) // 8) * h
            else:
                warnings.append("Unknown pixel layout; payload length cannot be certified")
                break
            sizes.append({"level": level, "width": w, "height": h, "bytes": count})
    size = path.stat().st_size
    if sizes and size < offset + sum(m["bytes"] for m in sizes):
        raise ValueError("DDS payload truncated: declared mip levels do not fit")
    if fourcc is None:
        warnings.append("Uncompressed DDS: row-pitch and channel-mask checks needed in importer")
    if mip_count != full_mips:
        warnings.append("Incomplete mip chain: prone to shimmering/aliasing at distance")
    alpha = ("explicit/interpolated" if fourcc in ("DXT3", "DXT5") else
             "optional 1-bit; requires decode inspection" if fourcc == "DXT1" else
             "mask" if words[25] else "not established")
    return {"file": str(path), "sha256": sha256(path), "bytes": size,
            "width": width, "height": height, "fourcc": fourcc, "bits_per_pixel": bpp,
            "pixel_flags": pf_flags, "channel_masks": list(words[22:26]),
            "caps2": caps2, "depth": depth, "mip_count": mip_count,
            "expected_full_mips": full_mips, "alpha_storage": alpha,
            "dx10": dx10, "mip_layout": sizes, "warnings": warnings,
            "runtime_compatibility": "requires game run"}


def compare(original: Path, candidate: Path) -> dict:
    a, b = dds_info(original), dds_info(candidate)
    errors = []
    for key in ("fourcc", "bits_per_pixel", "pixel_flags", "channel_masks", "caps2", "depth"):
        if a[key] != b[key]:
            errors.append(f"{key} changed")
    if a["width"] * b["height"] != b["width"] * a["height"]:
        errors.append("Aspect ratio changed")
    if b["width"] < a["width"] or b["height"] < a["height"]:
        errors.append("Candidate has lower resolution")
    if b["mip_count"] != b["expected_full_mips"]:
        errors.append("Candidate lacks a complete mip chain")
    if not b["mip_layout"] or b["fourcc"] not in ("DXT1", "DXT3", "DXT5") or b["dx10"]:
        errors.append("Only simple legacy DXT1/3/5 2D candidates approved by this preflight")
    return {"original": a, "candidate": b, "preflight_pass": not errors,
            "errors": errors, "limitations": ["Does not decode/compare alpha pixels, color space or visual quality",
                "Does not verify texture-ID, container importer or runtime compatibility",
                "No import performed; test lossless roundtrip on local copies first"]}


def inventory(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Inventory needs a real directory")
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            continue
        if path.is_file() and path.suffix.lower() in CONTAINERS:
            item = {"path": str(path.relative_to(root)), "bytes": path.stat().st_size,
                    "sha256": sha256(path), "format_status": "opaque container; not decoded"}
            if path.suffix.lower() == ".dds":
                try:
                    item["dds"] = dds_info(path)
                except ValueError as exc:
                    item["error"] = str(exc)
            records.append(item)
    return {"schema": 1, "read_only": True, "root": str(root), "files": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("inventory", "dds-info"):
        part = sub.add_parser(action)
        part.add_argument("path", type=Path)
    part = sub.add_parser("compare-dds")
    part.add_argument("original", type=Path)
    part.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        result = (inventory(args.path) if args.action == "inventory" else
                  dds_info(args.path) if args.action == "dds-info" else
                  compare(args.original, args.candidate))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("preflight_pass") is False else 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Asset analysis failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
