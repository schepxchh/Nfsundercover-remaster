import tempfile
import unittest
from pathlib import Path
from tools.benchmark import summarize


class BenchmarkTests(unittest.TestCase):
    def test_tail_and_rejected_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.csv"
            path.write_text("FrameMs\n" + "10\n" * 198 + "50\n" * 2 + "nan\n-1\nmissing\n")
            data = summarize(path, "FrameMs")
            self.assertEqual(data["p95_ms"], 10)
            self.assertEqual(data["p99_ms"], 10)
            self.assertEqual(data["one_percent_low_fps"], 20)
            self.assertEqual(data["rejected_rows"], 3)
            self.assertEqual(data["over_budget_percent"], 1)
            self.assertAlmostEqual(data["average_fps"], 200000 / 2080)

    def test_column_and_short_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.csv"
            path.write_text("FrameMs\n10\n")
            with self.assertRaisesRegex(ValueError, "Missing column"):
                summarize(path, "unknown")
            with self.assertRaisesRegex(ValueError, "100 valid"):
                summarize(path, "FrameMs")


if __name__ == "__main__":
    unittest.main()
