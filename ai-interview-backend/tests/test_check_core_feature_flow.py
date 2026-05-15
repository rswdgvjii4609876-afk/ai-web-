from app.scripts.check_core_feature_flow import (
    CheckResult,
    SYNTHETIC_CASES,
    build_report,
    first_failure,
    overall_status,
    run_checks,
)


def test_core_feature_flow_checks_pass_with_synthetic_cases():
    results = run_checks()
    failures = [item for item in results if item.status == "FAIL"]

    assert not failures
    assert overall_status(results) == "PASS"
    assert {case.case_id for case in SYNTHETIC_CASES} == {"C1", "C2", "C3"}
    assert any(item.name == "member_knowledge_packages" for item in results)


def test_core_feature_flow_report_contains_result_and_representative_jobs():
    results = run_checks()
    report = build_report(results)

    assert "阶段 133 核心功能自动化自检报告" in report
    assert "自动结论：PASS" in report
    assert "Python后端开发工程师" in report
    assert "产品助理/产品经理实习生" in report
    assert "人力资源专员" in report


def test_core_feature_flow_first_failure_is_explicit():
    results = [
        CheckResult("snapshot", "PASS", "ok"),
        CheckResult("polish", "FAIL", "missing knowledge source"),
        CheckResult("learning", "FAIL", "lost evidence status"),
    ]

    assert overall_status(results) == "FAIL"
    assert first_failure(results) == "polish: missing knowledge source"
    assert "第一条失败：polish: missing knowledge source" in build_report(results)
