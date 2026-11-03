"""Fail when service or repository coverage drops below the recorded baseline."""

import argparse
import json
from pathlib import Path


GROUPS = ("app/services", "app/repositories")


def coverage_percent(report: dict, group: str) -> float:
    covered = 0
    statements = 0
    for path, details in report.get("files", {}).items():
        normalized = path.replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized.startswith(f"{group}/"):
            summary = details["summary"]
            covered += summary["covered_lines"]
            statements += summary["num_statements"]
    if statements == 0:
        raise ValueError(f"Coverage report contains no measured files for {group}")
    return 100 * covered / statements


def compare_to_baseline(
    report: dict, baseline: dict
) -> tuple[dict[str, float], list[str]]:
    current = {group: coverage_percent(report, group) for group in GROUPS}
    failures = [
        f"{group} coverage {current[group]:.2f}% is below baseline {baseline[group]:.2f}%"
        for group in GROUPS
        if current[group] + 1e-9 < baseline[group]
    ]
    return current, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument("baseline_json", type=Path)
    args = parser.parse_args()

    report = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline_json.read_text(encoding="utf-8"))
    current, failures = compare_to_baseline(report, baseline)
    for group, percent in current.items():
        print(f"{group}: {percent:.2f}% (baseline {baseline[group]:.2f}%)")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Service and repository coverage meet their recorded baselines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
