from pathlib import Path

from app.scripts.check_member_knowledge_usage import (
    INSUFFICIENT_POSITIONS,
    _usage_from_packages,
    build_report,
)
from app.scripts.import_member_knowledge_packages import (
    DEFAULT_SOURCE,
    _package_paths,
    build_import_plans,
)


def test_member_knowledge_usage_report_marks_coverage_and_gaps():
    plans = build_import_plans(_package_paths(Path(DEFAULT_SOURCE)))
    usages = _usage_from_packages(plans)
    report = build_report(usages, mode="package")

    assert len(usages) == 7
    assert "Python后端开发工程师" in report
    assert "产品助理" in report
    assert "问答经验启用切片数" in report
    assert "待正式入库" in report
    for position in INSUFFICIENT_POSITIONS:
        assert position in report


def test_member_knowledge_usage_package_slices_include_interview_experience():
    plans = build_import_plans(_package_paths(Path(DEFAULT_SOURCE)))
    usages = _usage_from_packages(plans)

    assert all(item.slice_count > 0 for item in usages)
    assert all(item.enabled_slice_count > 0 for item in usages)
    assert any(item.interview_experience_slice_count > 0 for item in usages)
    operation_usage = next(item for item in usages if item.target_position == "运营助理")
    assert operation_usage.interview_experience_slice_count == operation_usage.package_experience_count
