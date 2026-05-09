"""Validate the server-side stage 79 Markdown report.

This script is dependency-free and can run on Windows or Ubuntu. It reads the
Markdown report produced by scripts/stage79_server_verify.sh and turns it into
a small PASS/FAIL summary for stage 1/13 server validation.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


DEFAULT_REPORT = Path(
    "docs/competition/server_validation_reports/stage79_server_verify_latest.md"
)

SUMMARY_KEYS = {
    "自动结论": "overall",
    "公共岗位画像": "public_profiles",
    "知识切片": "knowledge_slices",
    "执行后提交": "commit_after",
}


def split_markdown_row(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.strip().strip("`") for cell in line.strip("|").split("|")]


def is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def parse_int(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


def parse_report(path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    summary: dict[str, str] = {}
    checks: list[dict[str, str]] = []

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        cells = split_markdown_row(line)
        if not cells or is_separator(cells):
            continue

        if len(cells) >= 2 and cells[0] in SUMMARY_KEYS:
            summary[SUMMARY_KEYS[cells[0]]] = cells[1]
            continue

        if len(cells) >= 3 and cells[0] not in {"检查项", "项目"}:
            result = cells[1].upper()
            if result in {"PASS", "FAIL", "WARN", "UNKNOWN"}:
                checks.append(
                    {
                        "name": cells[0],
                        "result": result,
                        "note": cells[2],
                    }
                )

    return summary, checks


def validate(
    summary: dict[str, str],
    checks: list[dict[str, str]],
    min_public_profiles: int,
    strict: bool,
) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    lines: list[str] = []

    overall = summary.get("overall", "")
    public_profiles = parse_int(summary.get("public_profiles", ""))
    knowledge_slices = parse_int(summary.get("knowledge_slices", ""))
    failed_checks = [check for check in checks if check["result"] == "FAIL"]
    warn_checks = [check for check in checks if check["result"] == "WARN"]

    lines.append(f"overall={overall or 'MISSING'}")
    lines.append(f"public_profiles={public_profiles if public_profiles is not None else 'MISSING'}")
    lines.append(f"knowledge_slices={knowledge_slices if knowledge_slices is not None else 'MISSING'}")
    lines.append(f"failed_checks={len(failed_checks)}")
    lines.append(f"warn_checks={len(warn_checks)}")
    if summary.get("commit_after"):
        lines.append(f"commit_after={summary['commit_after']}")

    if overall != "PASS":
        errors.append(f"Server report overall result is not PASS: {overall or 'MISSING'}")
    if public_profiles is None:
        errors.append("Public profile count is missing.")
    elif public_profiles < min_public_profiles:
        errors.append(
            f"Public profile count is {public_profiles}, expected at least {min_public_profiles}."
        )
    if knowledge_slices is None:
        errors.append("Knowledge slice count is missing.")
    elif knowledge_slices <= 0:
        errors.append(f"Knowledge slice count is {knowledge_slices}, expected greater than 0.")
    for check in failed_checks:
        errors.append(f"Failed check: {check['name']} - {check['note']}")
    for check in warn_checks:
        warnings.append(f"Warning check: {check['name']} - {check['note']}")

    if strict and warnings:
        errors.extend(warnings)

    return errors, warnings, lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate stage 79 server report.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Markdown report path.")
    parser.add_argument(
        "--min-public-profiles",
        type=int,
        default=12,
        help="Minimum acceptable public position profiles.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat WARN checks as failures.",
    )
    args = parser.parse_args()

    if not args.report.exists():
        print(f"ERROR: report file not found: {args.report}")
        return 2

    summary, checks = parse_report(args.report)
    errors, warnings, lines = validate(summary, checks, args.min_public_profiles, args.strict)

    print(f"report={args.report}")
    if errors:
        print("result=FAIL")
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("result=PASS")
    for warning in warnings:
        print(f"WARN: {warning}")
    for line in lines:
        print(line)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
