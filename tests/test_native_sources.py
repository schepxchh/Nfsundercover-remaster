"""Source packaging/provenance checks; actual C++ and SM3 compiler tests are separate."""
import hashlib
import json
from pathlib import Path
import unittest
from tools.build_release import ROOT


class NativeSourceTests(unittest.TestCase):
    def test_official_sdk_matches_snapshot(self):
        root = ROOT / "third_party/reshade"
        snapshot = json.loads((root / "snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["license_choice"], "BSD-3-Clause")
        self.assertEqual(len(snapshot["files"]), 9)
        for record in snapshot["files"]:
            data = (root / record["path"]).read_bytes()
            self.assertEqual(len(data), record["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
            prefix = f"blob {len(data)}\0".encode()
            self.assertEqual(hashlib.sha1(prefix + data).hexdigest(), record["git_blob_sha1"])

    def test_native_default_is_disabled_and_not_installer_payload(self):
        from tools.remaster import PAYLOAD
        text = (ROOT / "native/config/NFSUCNative.ini").read_text(encoding="utf-8")
        entries = dict(line.split("=", 1) for line in text.splitlines() if line and not line.startswith("#"))
        self.assertEqual(entries["Enabled"], "0")
        self.assertEqual(entries["ObserveShaders"], "0")
        self.assertTrue(all(name.startswith("nfsuc-remaster/") for name in PAYLOAD))
        self.assertTrue(all(not Path(name).suffix.lower() in (".addon32", ".asi", ".dll") for name in PAYLOAD))


if __name__ == "__main__":
    unittest.main()
