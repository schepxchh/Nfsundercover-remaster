#!/usr/bin/env python3
"""Summarize an explicit frametime column (milliseconds) in a local CSV capture."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def summarize(path, column, budget_ms=16.666667):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if column not in (reader.fieldnames or []):
            raise ValueError(f"Missing column {column!r}; available: {reader.fieldnames}")
        values = []
        rejected = 0
        for row in reader:
            try:
                value = float(row[column])
            except (ValueError, TypeError):
                rejected += 1
                continue
            if not math.isfinite(value) or value <= 0:
                rejected += 1
                continue
            values.append(value)
    if len(values) < 100:
        raise ValueError("At least 100 valid frame samples required")
    ordered = sorted(values)
    percentile = lambda p: ordered[max(0, math.ceil(p * len(ordered)) - 1)]
    worst_count = max(1, math.ceil(len(values) * .01))
    return {"file": str(path), "column_ms": column, "frames": len(values), "rejected_rows": rejected,
            "duration_seconds": sum(values) / 1000,
            "average_fps": 1000 / statistics.mean(values),
            "median_ms": statistics.median(values), "p95_ms": percentile(.95),
            "p99_ms": percentile(.99),
            "one_percent_low_fps": 1000 / statistics.mean(ordered[-worst_count:]),
            "over_budget_percent": 100 * sum(v > budget_ms for v in values) / len(values),
            "budget_ms": budget_ms,
            "method": "nearest-rank percentiles; 1% low = reciprocal mean of slowest ceil(1%) frames",
            "caveat": "Filter one process/swapchain and identical steady-state intervals before analysis"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--column", required=True, help="Exact frametime column in ms; no unit inference")
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--budget-ms", type=float, default=16.666667)
    args = parser.parse_args()
    try:
        if not math.isfinite(args.budget_ms) or args.budget_ms <= 0:
            raise ValueError("budget-ms must be finite and positive")
        result = {"baseline": summarize(args.capture, args.column, args.budget_ms)}
        if args.compare:
            result["candidate"] = summarize(args.compare, args.column, args.budget_ms)
            result["average_fps_change_percent"] = 100 * (
                result["candidate"]["average_fps"] / result["baseline"]["average_fps"] - 1)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Benchmark analysis failed: {exc}\n")


if __name__ == "__main__":
    main()
