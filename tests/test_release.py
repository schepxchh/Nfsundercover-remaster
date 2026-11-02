import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from tools.build_release import build, ROOT
from tools.validate import validate


class ReleaseTests(unittest.TestCase):
    def test_configuration_scope(self):
        self.assertEqual(validate(), [])

    def test_reproducible_zip_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            build(output=first)
            build(output=second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                manifest = json.loads(archive.read("MANIFEST.json"))
                self.assertFalse(manifest["third_party_binaries"])
                self.assertEqual(set(archive.namelist()), set(manifest["files"]) | {"MANIFEST.json"})
                for name, item in manifest["files"].items():
                    data = archive.read(name)
                    self.assertEqual(len(data), item["bytes"])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
                    self.assertFalse(name.startswith("/"))
                    self.assertNotIn("..", name.split("/"))
                    self.assertNotIn(Path(name).suffix.lower(), (".dll", ".exe", ".asi", ".dds", ".bun"))


if __name__ == "__main__":
    unittest.main()
