"""Behavioral lifecycle tests; no installed game or Windows runtime required."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("remaster", Path(__file__).resolve().parents[1] / "tools/remaster.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.source = self.root / "package"
        self.source.mkdir()
        (self.game / "nfs.exe").write_bytes(b"test-executable-preserved")
        (self.game / "dinput8.dll").write_bytes(b"existing-loader")
        (self.game / "ReShade.ini").write_bytes(b"[GENERAL]\r\nOriginal=1\r\n")
        (self.game / "scripts").mkdir()
        (self.game / "scripts/NFSUndercover.FusionFix.cfg").write_bytes(b"[MAIN]\nSimRate=120\nFPSLimit=60\n")
        for dst, src in m.PAYLOAD.items():
            path = self.source / src
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("content:" + dst).encode())
        self.manager = m.Manager(self.game, self.source)

    def baseline(self):
        return {str(p.relative_to(self.game)): p.read_bytes() for p in self.game.rglob("*") if p.is_file() and m.STATE not in p.parts and "nfsuc-remaster" not in p.parts}

    def test_install_uninstall_byte_exact_baseline_and_restore_uninstall(self):
        original = self.baseline()
        self.manager.transact("install")
        for dst, src in m.PAYLOAD.items():
            self.assertEqual((self.game / dst).read_bytes(), (self.source / src).read_bytes())
        self.assertEqual(original, self.baseline())
        self.manager.transact("uninstall")
        self.assertFalse((self.game / "nfsuc-remaster").exists())
        self.assertEqual(original, self.baseline())
        self.manager.restore()
        self.assertTrue((self.game / next(iter(m.PAYLOAD))).exists())

    def test_dry_run_no_files_created(self):
        before = sorted(str(p) for p in self.game.rglob("*"))
        result = self.manager.transact("install", dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(before, sorted(str(p) for p in self.game.rglob("*")))

    def test_restore_install_removes_only_payload(self):
        self.manager.transact("install")
        extra = self.game / "nfsuc-remaster/user-note.txt"
        extra.write_text("keep")
        self.manager.restore()
        self.assertEqual(extra.read_text(), "keep")
        self.assertFalse(self.manager.owned())

    def test_foreign_collision_refuses_before_any_payload_write(self):
        destination = self.game / list(m.PAYLOAD)[2]
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"foreign")
        with self.assertRaises(m.SafetyError):
            self.manager.transact("install")
        self.assertEqual(destination.read_bytes(), b"foreign")
        self.assertFalse((self.game / list(m.PAYLOAD)[0]).exists())

    def test_user_edit_preserved_on_uninstall_and_restore(self):
        self.manager.transact("install")
        target = self.game / list(m.PAYLOAD)[-1]
        target.write_bytes(b"user changed preset")
        for operation in (lambda: self.manager.transact("uninstall"), self.manager.restore):
            with self.assertRaises(m.SafetyError):
                operation()
        self.assertEqual(target.read_bytes(), b"user changed preset")
        self.assertTrue((self.game / list(m.PAYLOAD)[0]).exists())

    def test_repeat_install_is_idempotent(self):
        self.manager.transact("install")
        result = self.manager.transact("install")
        self.assertFalse(result["changed"])
        self.manager.restore()
        self.assertFalse((self.game / "nfsuc-remaster").exists())

    def test_upgrade_and_restore_old_bytes(self):
        self.manager.transact("install")
        dst, src = next(iter(m.PAYLOAD.items()))
        old = (self.game / dst).read_bytes()
        (self.source / src).write_bytes(b"updated-shader")
        self.manager.transact("install")
        self.assertEqual((self.game / dst).read_bytes(), b"updated-shader")
        self.manager.restore()
        self.assertEqual((self.game / dst).read_bytes(), old)

    def test_corrupt_backup_no_partial_restoration(self):
        self.manager.transact("install")
        dst, src = next(iter(m.PAYLOAD.items()))
        old_hash = self.manager.owned()[dst]
        (self.source / src).write_bytes(b"updated")
        self.manager.transact("install")
        (self.manager.state / "backups" / old_hash).write_bytes(b"corrupt")
        before = (self.game / dst).read_bytes()
        with self.assertRaises(m.SafetyError):
            self.manager.restore()
        self.assertEqual((self.game / dst).read_bytes(), before)

    def test_crash_mid_install_restores_original_state(self):
        real_write = self.manager.write_blob
        count = 0
        def failing_write(relative, sha):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("simulated power failure")
            real_write(relative, sha)
        with patch.object(self.manager, "write_blob", side_effect=failing_write):
            with self.assertRaises(OSError):
                self.manager.transact("install")
        self.assertTrue((self.manager.state / "journal.json").exists())
        with self.assertRaises(m.SafetyError):
            self.manager.transact("install")
        self.manager.restore()
        self.assertFalse((self.game / "nfsuc-remaster").exists())
        self.assertEqual(self.manager.owned(), {})

    def test_crash_mid_uninstall_restores_installation(self):
        self.manager.transact("install")
        real_write = self.manager.write_blob
        calls = 0
        def failing_write(relative, sha):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("simulated crash")
            real_write(relative, sha)
        with patch.object(self.manager, "write_blob", side_effect=failing_write):
            with self.assertRaises(OSError):
                self.manager.transact("uninstall")
        self.manager.restore()
        for dst, src in m.PAYLOAD.items():
            self.assertEqual((self.game / dst).read_bytes(), (self.source / src).read_bytes())

    def test_tampered_journal_cannot_target_executable(self):
        self.manager.transact("install")
        journal_path = self.manager.state / "last.json"
        journal = json.loads(journal_path.read_text())
        journal["entries"][0]["path"] = "nfs.exe"
        journal_path.write_text(json.dumps(journal))
        with self.assertRaises(m.SafetyError):
            self.manager.restore()
        self.assertEqual((self.game / "nfs.exe").read_bytes(), b"test-executable-preserved")

    def test_path_traversal_and_windows_absolute_paths_refused(self):
        for name in ("../nfs.exe", "/tmp/x", "C:/nfs.exe", "x\\..\\nfs.exe", "x//../x", "./x"):
            with self.subTest(path=name), self.assertRaises(m.SafetyError):
                m.safe_path(self.game, name)

    def test_symlink_payload_directory_refused(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        try:
            (self.game / "nfsuc-remaster").symlink_to(elsewhere, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(m.SafetyError):
            self.manager.transact("install")
        self.assertFalse(list(elsewhere.iterdir()))

    def test_locked_state_refuses_second_writer(self):
        with self.manager.locked():
            with self.assertRaises(m.SafetyError):
                self.manager.transact("install")

    def test_dead_process_lock_recovers_interrupted_transaction(self):
        self.manager.transact("install")
        (self.manager.state / "lock").write_text("99999999")
        with patch.object(m, "pid_alive", return_value=False):
            self.manager.restore()
        self.assertFalse((self.game / "nfsuc-remaster").exists())

    def test_dry_run_refuses_pending_journal(self):
        self.manager.transact("install")
        (self.manager.state / "journal.json").write_bytes((self.manager.state / "last.json").read_bytes())
        with self.assertRaises(m.SafetyError):
            self.manager.transact("install", dry_run=True)

    def test_initializer_failure_does_not_publish_broken_state(self):
        real_atomic = m.atomic_bytes
        def fail_marker(path, data):
            if path.name == "owner.json":
                raise OSError("simulated initialization failure")
            real_atomic(path, data)
        with patch.object(m, "atomic_bytes", side_effect=fail_marker):
            with self.assertRaises(OSError):
                self.manager.transact("install")
        self.assertFalse(self.manager.state.exists())
        self.manager.transact("install")

    def test_foreign_state_directory_refused(self):
        self.manager.state.mkdir()
        with self.assertRaises(m.SafetyError):
            self.manager.transact("install")

    def test_restoration_dry_run_no_mutation(self):
        self.manager.transact("install")
        before = {str(p): p.read_bytes() for p in self.game.rglob("*") if p.is_file()}
        self.manager.restore(dry_run=True)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.game.rglob("*") if p.is_file()})

    def test_report_does_not_claim_compatibility_and_preserves_config(self):
        report = m.diagnostic(self.game)
        self.assertEqual(report["compatibility"], "requires-in-game-test")
        config = next(e for e in report["files"] if e["path"].endswith(".cfg"))
        self.assertIn("SimRate=120", config["configuration"])
        self.assertTrue(any("Proxy/loader" in warning for warning in report["warnings"]))

    def test_pe32_header_evidence_no_version_guess(self):
        header = bytearray(128)
        header[:2] = b"MZ"
        struct.pack_into("<I", header, 60, 64)
        header[64:68] = b"PE\0\0"
        struct.pack_into("<H", header, 68, 0x14c)
        struct.pack_into("<H", header, 88, 0x10b)
        target = self.game / "nfs.exe"
        target.write_bytes(header)
        report = m.pe_info(target)
        self.assertEqual(report["machine"], "0x14c")
        self.assertEqual(report["optional_header"], "0x10b")
        self.assertIsNone(report["file_version"])

    def test_backup_and_report_cannot_overwrite_existing_or_game_files(self):
        for target in (self.game / "report.json", self.game / "nfs.exe"):
            with self.assertRaises(m.SafetyError):
                m.output_path(target, self.game)
        output = self.root / "report.json"
        output.write_text("keep")
        with self.assertRaises(m.SafetyError):
            m.output_path(output, self.game)
        self.assertEqual(output.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
