from pathlib import Path

from app.scripts.check_member_knowledge_usage import (
    INSUFFICIENT_POSITIONS,
    PositionUsage,
    _usage_from_packages,
    build_report,
    database_usage_blockers,
)
from app.scripts.import_member_knowledge_packages import (
    DEFAULT_SOURCE,
    _package_paths,
    build_import_plans,
)


def test_member_knowledge_usage_report_marks_canonical_merge_and_gaps():
    plans = build_import_plans(_package_paths(Path(DEFAULT_SOURCE)))
    usages = _usage_from_packages(plans)
    report = build_report(usages, mode="package")

    assert len(usages) == 7
    assert "Python后端开发工程师" in report
    assert "产品助理" in report
    assert "问答经验启用切片数" in report
    assert "待归并入标准岗位画像" in report
    assert "成员资料补充：{岗位}" in report
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


def test_member_knowledge_usage_database_blockers_detect_non_ok_status():
    usages = [
        PositionUsage(
            target_position="Python后端开发工程师",
            title="职启智评岗位画像：Python后端开发工程师",
            knowledge_base_count=1,
            slice_count=10,
            enabled_slice_count=10,
            interview_experience_slice_count=3,
            package_experience_count=3,
            imported=True,
            status="ok",
        ),
        PositionUsage(
            target_position="产品助理",
            title="职启智评岗位画像：产品助理",
            knowledge_base_count=0,
            slice_count=0,
            enabled_slice_count=0,
            interview_experience_slice_count=0,
            package_experience_count=2,
            imported=False,
            status="missing_canonical_profile",
            notes="missing active exact canonical profile",
        ),
    ]

    blockers = database_usage_blockers(usages)
    report = build_report(usages, mode="database_canonical_profiles")

    assert len(blockers) == 1
    assert blockers[0].target_position == "产品助理"
    assert "missing_canonical_profile" in report
