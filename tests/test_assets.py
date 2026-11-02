import json
import struct
import tempfile
import unittest
from pathlib import Path
from tools.assets import compare, dds_info, inventory


def fixture(path, width=8, height=8, mips=4, code=b"DXT5"):
    fields = [0] * 31
    fields[0:7] = [124, 0x21007, height, width, 0, 0, mips]
    fields[18:22] = [32, 4, int.from_bytes(code, "little"), 0]
    fields[26] = 0x401008
    block = 8 if code == b"DXT1" else 16
    count = sum(max(1, (max(1, width >> m) + 3) // 4) *
                max(1, (max(1, height >> m) + 3) // 4) * block for m in range(mips))
    path.write_bytes(b"DDS " + struct.pack("<31I", *fields) + bytes(count))


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a, self.b = self.root / "a.dds", self.root / "b.dds"

    def test_mip_sizes_and_readonly(self):
        fixture(self.a)
        before = self.a.read_bytes()
        info = dds_info(self.a)
        self.assertEqual([m["bytes"] for m in info["mip_layout"]], [64, 16, 16, 16])
        self.assertEqual(info["mip_count"], info["expected_full_mips"])
        self.assertEqual(self.a.read_bytes(), before)

    def test_truncation(self):
        fixture(self.a)
        self.a.write_bytes(self.a.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "truncated"):
            dds_info(self.a)

    def test_format_and_aspect_protected(self):
        fixture(self.a)
        fixture(self.b, width=16, height=8, mips=5, code=b"DXT1")
        result = compare(self.a, self.b)
        self.assertFalse(result["preflight_pass"])
        self.assertIn("fourcc changed", result["errors"])
        self.assertIn("Aspect ratio changed", result["errors"])

    def test_upscale_complete_chain_preflight(self):
        fixture(self.a)
        fixture(self.b, width=16, height=16, mips=5)
        self.assertTrue(compare(self.a, self.b)["preflight_pass"])

    def test_missing_mips_rejected(self):
        fixture(self.a)
        fixture(self.b, mips=1)
        self.assertFalse(compare(self.a, self.b)["preflight_pass"])

    def test_malformed_header(self):
        self.a.write_bytes(b"not DDS")
        with self.assertRaises(ValueError):
            dds_info(self.a)

    def test_inventory_opaque_and_bad_dds(self):
        (self.root / "world.bun").write_bytes(b"local fixture")
        self.a.write_bytes(b"bad")
        report = inventory(self.root)
        self.assertEqual(len(report["files"]), 2)
        self.assertTrue(report["read_only"])
        json.dumps(report)

    def test_symlink_skipped(self):
        fixture(self.a)
        try:
            self.b.symlink_to(self.a)
        except OSError:
            self.skipTest("symlink not available")
        self.assertEqual(len(inventory(self.root)["files"]), 1)
        with self.assertRaises(ValueError):
            dds_info(self.b)


if __name__ == "__main__":
    unittest.main()
