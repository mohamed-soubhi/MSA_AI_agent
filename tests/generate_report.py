#!/usr/bin/env python3
"""Run the test suite and write a Markdown pass/fail report to doc/test_report.md.

Every test in this suite carries a @pytest.mark.tid("PREFIX-NNN") marker
(registered in pytest.ini). This script runs pytest as an in-process
plugin, reads each test's tid off its collected item, and records the
outcome/duration per test — then renders one Markdown table plus a
summary line, so `doc/test_report.md` always reflects the last run.

Usage:
    python3 tests/generate_report.py            # run the whole suite
    python3 tests/generate_report.py -k confirm  # any extra pytest args
"""

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "doc" / "test_report.md"

_OUTCOME_ICON = {"passed": "✅", "failed": "❌", "skipped": "⏭️", "error": "⚠️"}


class ReportCollector:
    """pytest plugin: maps each test's tid marker to its outcome/duration."""

    def __init__(self):
        self.tid_map = {}
        self.results = []

    def pytest_collection_modifyitems(self, session, config, items):
        for item in items:
            marker = item.get_closest_marker("tid")
            self.tid_map[item.nodeid] = marker.args[0] if marker else "—"

    def pytest_runtest_logreport(self, report):
        # "call" covers the normal pass/fail outcome. A "setup" report is
        # only relevant here if it was skipped or errored (e.g. a failed
        # fixture) -- a normal setup that leads into "call" would double
        # count the same test otherwise.
        is_call = report.when == "call"
        is_setup_problem = report.when == "setup" and report.outcome in ("skipped", "failed")
        if is_call or is_setup_problem:
            tid = self.tid_map.get(report.nodeid, "—")
            nodeid = report.nodeid
            # conftest.py's pytest_itemcollected appends " [TID]" to the
            # node id for -v display; strip that back off here so the
            # report's own ID column isn't duplicated in the Test column.
            suffix = f" [{tid}]"
            if tid != "—" and nodeid.endswith(suffix):
                nodeid = nodeid[: -len(suffix)]
            self.results.append({
                "tid": tid,
                "nodeid": nodeid,
                "outcome": report.outcome,
                "duration": report.duration,
            })


def _tid_sort_key(result):
    # Unmarked tests ("—") sort after every real id, alphabetically within
    # each id so parametrized variants of the same test stay grouped.
    return (result["tid"] == "—", result["tid"], result["nodeid"])


def render_report(results, wall_seconds):
    counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    for result in results:
        key = result["outcome"] if result["outcome"] in counts else "error"
        counts[key] += 1

    rows = sorted(results, key=_tid_sort_key)

    lines = [
        "# Test Report",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**Total:** {len(results)} &nbsp;|&nbsp; "
        f"**Passed:** {counts['passed']} &nbsp;|&nbsp; "
        f"**Failed:** {counts['failed']} &nbsp;|&nbsp; "
        f"**Skipped:** {counts['skipped']} &nbsp;|&nbsp; "
        f"**Errors:** {counts['error']} &nbsp;|&nbsp; "
        f"**Duration:** {wall_seconds:.2f}s",
        "",
        "| ID | Test | Outcome | Duration (s) |",
        "|---|---|---|---|",
    ]
    for result in rows:
        icon = _OUTCOME_ICON.get(result["outcome"], "❓")
        lines.append(
            f"| {result['tid']} | `{result['nodeid']}` | "
            f"{icon} {result['outcome']} | {result['duration']:.3f} |"
        )

    failures = [r for r in rows if r["outcome"] in ("failed", "error")]
    if failures:
        lines += ["", "## Failures"]
        for result in failures:
            lines.append(f"- **{result['tid']}** `{result['nodeid']}`")

    return "\n".join(lines) + "\n", counts


def main(argv=None):
    collector = ReportCollector()
    started = time.time()
    exit_code = pytest.main([str(ROOT / "tests"), "-q", *(argv or [])], plugins=[collector])
    wall_seconds = time.time() - started

    report_text, counts = render_report(collector.results, wall_seconds)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")

    print("\n" + "=" * 70)
    print(" FINAL TEST REPORT")
    print("=" * 70)
    print(report_text)
    print(f"Report written to {REPORT_PATH.relative_to(ROOT)}")
    print(
        f"passed={counts['passed']} failed={counts['failed']} "
        f"skipped={counts['skipped']} errors={counts['error']}"
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
