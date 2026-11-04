import pytest

from scripts.check_coverage_baseline import compare_to_baseline, coverage_percent


def _report(covered: int, statements: int) -> dict:
    return {
        "files": {
            "app/services/example.py": {
                "summary": {
                    "covered_lines": covered,
                    "num_statements": statements,
                }
            },
            "app\\repositories\\example.py": {
                "summary": {
                    "covered_lines": covered,
                    "num_statements": statements,
                }
            },
        }
    }


def test_coverage_percent_handles_windows_and_posix_report_paths():
    report = _report(3, 4)
    report["files"]["./app/services/nested.py"] = {
        "summary": {"covered_lines": 1, "num_statements": 2}
    }

    assert coverage_percent(report, "app/services") == pytest.approx(66.666, rel=1e-3)
    assert coverage_percent(report, "app/repositories") == 75


def test_coverage_gate_accepts_baseline_and_rejects_a_drop():
    baseline = {"app/services": 75, "app/repositories": 75}

    current, failures = compare_to_baseline(_report(3, 4), baseline)
    assert not failures
    assert current["app/services"] == 75

    _, failures = compare_to_baseline(_report(2, 4), baseline)
    assert len(failures) == 2
    assert all("below baseline" in failure for failure in failures)


def test_coverage_gate_fails_if_a_group_was_not_measured():
    with pytest.raises(ValueError, match="no measured files"):
        coverage_percent({"files": {}}, "app/services")
