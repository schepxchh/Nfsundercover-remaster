"""Synthetic metadata fixtures only; no executable/game bytes or GPU execution."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import engine_probe as probe


PE = 0x80
OPTIONAL = PE + 24
TABLE = OPTIONAL + 224


def u32(data, offset, value):
    struct.pack_into("<I", data, offset, value)


def fixture(candidate=False):
    data = bytearray(probe.SOURCE_FILE_BYTES if candidate else 0x800)
    data[:2] = b"MZ"
    u32(data, 60, PE)
    data[PE:PE + 4] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, PE + 4, 0x14C, 3, 0, 0, 0, 224, 0x102)
    struct.pack_into("<H", data, OPTIONAL, 0x10B)
    u32(data, OPTIONAL + 16, 0x4AEC55 if candidate else 0x1000)
    u32(data, OPTIONAL + 28, 0x400000)
    u32(data, OPTIONAL + 32, 0x1000)
    u32(data, OPTIONAL + 36, 0x200)
    u32(data, OPTIONAL + 56, 0x940000)
    u32(data, OPTIONAL + 60, 0x200)
    u32(data, OPTIONAL + 92, 16)
    u32(data, OPTIONAL + 104, 0x2000)
    u32(data, OPTIONAL + 108, 40)
    sections = ((b".text", 0x1000 if candidate else 0x200, 0x4AE000 if candidate else 0x1000, 0x200, 0x200, 0x60000020),
                (b".idata", 0x200, 0x2000, 0x200, 0x400, 0xC0000040),
                (b".data", 0x200, 0x93CE00, 0x200, 0x600, 0xC0000040))
    for n, (name, virtual_bytes, rva, raw_bytes, offset, flags) in enumerate(sections):
        at = TABLE + 40 * n
        data[at:at + len(name)] = name
        struct.pack_into("<4I", data, at + 8, virtual_bytes, rva, raw_bytes, offset)
        u32(data, at + 36, flags)
    struct.pack_into("<5I", data, 0x400, 0x2040, 0, 0, 0x2030, 0x2060)
    data[0x430:0x439] = b"d3d9.dll\0"
    struct.pack_into("<3I", data, 0x440, 0x2080, 0x8000000C, 0)
    struct.pack_into("<3I", data, 0x460, 0x2080, 0x8000000C, 0)
    struct.pack_into("<H", data, 0x480, 7)
    data[0x482:0x492] = b"Direct3DCreate9\0"
    struct.pack_into("<2i", data, 0x6D8, -1, 2)
    return data


class EngineProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic-pe.fixture"

    def report(self, data=None):
        self.path.write_bytes(fixture() if data is None else data)
        return probe.pe_info(self.path)

    def test_metadata_imports_candidates_and_no_mutation(self):
        data = fixture()
        report = self.report(data)
        self.assertEqual(self.path.read_bytes(), data)
        self.assertEqual(report["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(report["machine"], "0x14c")
        self.assertTrue(report["imports"]["Direct3DCreate9_imported"])
        functions = report["imports"]["d3d9"][0]["functions"]
        self.assertEqual(functions, [{"name": "Direct3DCreate9", "hint": 7}, {"ordinal": 12}])
        car, tire = report["visual_candidates"].values()
        self.assertEqual(car["on_disk_int32"], -1)
        self.assertTrue(car["section_declares_writable"])
        self.assertEqual(tire["on_disk_int32"], 2)
        self.assertFalse(tire["matches_exopts_setting_default"])
        self.assertEqual(report["assessment"]["classification"], "incompatible_fingerprint")
        self.assertEqual(report["assessment"]["runtime_compatibility"], "unverified")

    def test_all_source_landmarks_still_do_not_approve_unknown_hash(self):
        report = self.report(fixture(candidate=True))
        self.assertEqual(report["assessment"]["classification"], "structural_candidate")
        self.assertFalse(report["assessment"]["approved_hash_match"])
        self.assertEqual(report["assessment"]["approved_hash_allowlist_entries"], 0)
        self.assertEqual(report["assessment"]["runtime_compatibility"], "unverified")

    def test_virtual_only_variables_do_not_invent_default_values(self):
        data = fixture()
        u32(data, TABLE + 80 + 16, 0)
        u32(data, TABLE + 80 + 20, 0)
        report = self.report(data)
        for item in report["visual_candidates"].values():
            self.assertEqual(item["storage"], "virtual_only")
            self.assertIsNone(item["on_disk_int32"])
            self.assertIsNone(item["matches_exopts_setting_default"])

    def test_section_names_decode_invalid_utf8_without_exposing_bytes(self):
        data = fixture()
        data[TABLE:TABLE + 8] = b"bad\xff\0\0\0\0"
        report = self.report(data)
        self.assertEqual(report["sections"][0]["name"], "bad\ufffd")
        json.dumps(report, ensure_ascii=True)

    def test_only_direct3d9_import_names_are_reported(self):
        data = fixture()
        data[0x430:0x439] = b"other.dll"
        data[0x439] = 0
        report = self.report(data)
        self.assertEqual(report["imports"]["descriptor_count"], 1)
        self.assertEqual(report["imports"]["d3d9"], [])
        self.assertFalse(report["imports"]["Direct3DCreate9_imported"])
        self.assertNotIn("other.dll", json.dumps(report))

    def test_absent_import_directory_is_not_inferred_as_incompatibility(self):
        data = fixture()
        struct.pack_into("<2I", data, OPTIONAL + 104, 0, 0)
        report = self.report(data)
        self.assertEqual(report["imports"]["descriptor_count"], 0)
        self.assertEqual(report["assessment"]["runtime_compatibility"], "unverified")

    def test_bad_headers_and_pe64_are_rejected(self):
        cases = []
        cases.append(bytearray(b"MZ"))
        data = fixture(); u32(data, 60, 0xFFFFFFF0); cases.append(data)
        data = fixture(); struct.pack_into("<H", data, PE + 6, 97); cases.append(data)
        data = fixture(); struct.pack_into("<H", data, OPTIONAL, 0x20B); cases.append(data)
        data = fixture(); u32(data, OPTIONAL + 92, 17); cases.append(data)
        data = fixture(); u32(data, OPTIONAL + 60, 0x100); cases.append(data)
        for data in cases:
            with self.subTest(length=len(data)), self.assertRaises(probe.ProbeError):
                probe.PE32(data)

    def test_section_bounds_and_overlaps_are_rejected(self):
        cases = []
        data = fixture(); u32(data, TABLE + 16, 0xFFFFFFFF); cases.append(data)
        data = fixture(); u32(data, TABLE + 12, 0xFFFFFFF0); cases.append(data)
        data = fixture(); u32(data, TABLE + 40 + 12, 0x1000); cases.append(data)
        data = fixture(); u32(data, TABLE + 40 + 20, 0x200); cases.append(data)
        data = fixture(); u32(data, OPTIONAL + 16, 0x3000); cases.append(data)
        for data in cases:
            with self.subTest(), self.assertRaises(probe.ProbeError):
                probe.PE32(data)

    def test_rva_arithmetic_overflow_and_virtual_imports_are_rejected(self):
        pe = probe.PE32(fixture())
        with self.assertRaisesRegex(probe.ProbeError, "overflows"):
            pe.offset(0xFFFFFFFF, 4)
        data = fixture()
        u32(data, OPTIONAL + 104, 0x93D000)
        with self.assertRaises(probe.ProbeError):
            probe.PE32(data).imports()

    def test_import_names_and_rvas_require_bounded_termination(self):
        data = fixture()
        u32(data, 0x40C, 0x21FF)
        data[0x5FF] = 0x61
        with self.assertRaisesRegex(probe.ProbeError, "Unterminated"):
            probe.PE32(data).imports()
        data = fixture()
        u32(data, 0x440, 0xFFFFFFF0)
        with self.assertRaises(probe.ProbeError):
            probe.PE32(data).imports()

    def test_import_descriptor_and_thunk_analysis_limits(self):
        with patch.object(probe, "MAX_IMPORT_DESCRIPTORS", 1):
            with self.assertRaisesRegex(probe.ProbeError, "descriptors lack terminator"):
                probe.PE32(fixture()).imports()
        with patch.object(probe, "MAX_THUNKS_PER_DLL", 2):
            with self.assertRaisesRegex(probe.ProbeError, "thunk table lacks terminator"):
                probe.PE32(fixture()).imports()
        with patch.object(probe, "MAX_TOTAL_THUNKS", 1):
            with self.assertRaisesRegex(probe.ProbeError, "analysis limit"):
                probe.PE32(fixture()).imports()

    def test_import_directory_size_and_reserved_ordinal_bits(self):
        data = fixture()
        u32(data, OPTIONAL + 108, 20)
        with self.assertRaisesRegex(probe.ProbeError, "descriptors lack terminator"):
            probe.PE32(data).imports()
        data = fixture()
        u32(data, 0x444, 0x8001000C)
        with self.assertRaisesRegex(probe.ProbeError, "ordinal"):
            probe.PE32(data).imports()

    def test_empty_lookup_still_requires_initialized_iat_terminator(self):
        data = fixture()
        u32(data, 0x440, 0)
        u32(data, 0x410, 0x93D000)
        with self.assertRaises(probe.ProbeError):
            probe.PE32(data).imports()

    def test_shader_sm3_pixel_vertex_framing_without_decode(self):
        for version, kind in ((0xFFFF0300, "pixel"), (0xFFFE0300, "vertex")):
            with self.subTest(kind=kind):
                data = struct.pack("<3I", version, 0xDEADBEEF, 0xFFFF)
                self.path.write_bytes(data)
                report = probe.shader_info(self.path)
                self.assertEqual(report["shader_type"], kind)
                self.assertEqual(report["shader_model"], "3.0")
                self.assertEqual(report["assessment"], "sm3_framing_candidate")
                self.assertFalse(report["instruction_decode_performed"])
                self.assertEqual(self.path.read_bytes(), data)
                self.assertNotIn("deadbeef", json.dumps(report).lower())

    def test_shader_bad_alignment_version_and_end(self):
        for data in (b"", b"x" * 9, struct.pack("<2I", 0, 0xFFFF),
                     struct.pack("<2I", 0xFFFF0300, 0)):
            self.path.write_bytes(data)
            with self.subTest(data_length=len(data)), self.assertRaises(probe.ProbeError):
                probe.shader_info(self.path)

    def test_symlink_input_refused(self):
        self.path.write_bytes(fixture())
        link = self.path.with_name("link.fixture")
        try:
            link.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaisesRegex(probe.ProbeError, "Symlink"):
            probe.pe_info(link)

    def test_cli_error_is_json_and_has_nonzero_status(self):
        self.path.write_bytes(b"MZ")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = probe.main(["pe-info", str(self.path)])
        self.assertEqual(result, 2)
        report = json.loads(stderr.getvalue())
        self.assertTrue(report["read_only"])
        self.assertEqual(report["runtime_compatibility"], "unverified")


if __name__ == "__main__":
    unittest.main()
