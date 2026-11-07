import pytest

from app.services.client.ai_service import AIService
from app.services.client.interview_service import InterviewService
from app.services.client.matching_engine import MatchingEngine
from app.services.client.learning_plan_service import LearningPlanService
from app.constants.learning_routes import iter_builtin_learning_route_stage_records
import asyncio
import json


def test_learning_summary_does_not_promote_related_terms_to_candidate_facts():
    result = MatchingEngine._learning_priority_summary({'top_gaps': [{
        'name': '框架', 'action_type': 'evidence_completion',
        'direct_matches': ['FastAPI'], 'related_matches': ['Django', 'Flask'],
    }]})[0]
    assert 'FastAPI' in result
    assert 'Django' not in result and 'Flask' not in result


@pytest.mark.parametrize('database_routes', [False, True])
def test_transaction_plan_does_not_match_python_in_job_title(database_routes):
    task = LearningPlanService._build_tasks_from_records(
        records=list(iter_builtin_learning_route_stage_records()) if database_routes else [],
        abilities=[{'name': 'PostgreSQL 事务回滚', 'missing_keywords': ['事务']}],
        target_position='Python后端开发工程师',
    )['tasks'][0]
    assert task['route_stage'] == 'database_orm'
    assert '事务' in task['learning_material']
    assert '回滚' in task['practice_task']
    assert any('事务' in criterion for criterion in task['acceptance_criteria'])


@pytest.mark.parametrize('answer', ['最多三次重试，指数退避。', '暂时性错误重试，例如最多3次。'])
def test_explicit_retry_limit_cannot_be_called_absent(answer):
    payload = {'score': 7, 'feedback': '缺少生产验证。未给出重试次数。',
               'unresolved_gaps': ['未给出重试次数、退避参数的具体数值或配置示例', '未说明检查点存储位置']}
    corrected = AIService._check_answer_consistency(payload, answer)
    assert corrected['score'] == 7
    assert '未给出重试次数' not in str(corrected['unresolved_gaps'])
    assert '原文' in corrected['feedback']
    assert '缺少生产验证' in corrected['feedback']
    assert '未说明检查点存储位置' in corrected['unresolved_gaps']
    assert payload['feedback'].endswith('未给出重试次数。')


@pytest.mark.parametrize('answer', ['我没有设置重试次数。', '不是三次重试，次数尚未确定。', '不重试，三次是测试运行次数。'])
def test_retry_guard_does_not_invent_a_limit(answer):
    payload = {'feedback': '未给出重试次数。', 'gaps': ['未给出重试次数']}
    assert AIService._check_answer_consistency(payload, answer) == payload


def test_report_defaults_check_stale_gaps_against_answer_evidence():
    signals = InterviewService._build_report_signals([{'answer': '最多三次重试。'}])
    signals['common_gaps'] = ['未给出重试次数']
    result = InterviewService._merge_report_defaults({'summary': '测试'}, signals, 'single')
    assert '未给出重试次数' not in str(result['weaknesses'])
    assert '原文' in str(result['weaknesses'])


def test_existing_seeded_database_route_gets_missing_specific_exercise():
    records = list(iter_builtin_learning_route_stage_records())
    for row in records:
        row.pop('practice_task', None)
        row.pop('acceptance_criteria', None)
    task = LearningPlanService._build_tasks_from_records(
        records=records, abilities=[{'name': 'PostgreSQL 事务回滚'}],
        target_position='Python后端开发工程师',
    )['tasks'][0]
    assert '回滚' in task['practice_task']
    assert any('事务' in item for item in task['acceptance_criteria'])


def test_real_evaluation_entry_applies_consistency_guard(monkeypatch):
    async def fake_json(*args, **kwargs):
        return json.dumps({'score': 7, 'feedback': '未给出重试次数。',
                           'gaps': ['未给出重试次数']}), 'json_mode'
    monkeypatch.setattr(AIService, '_chat_json', fake_json)
    result = asyncio.run(AIService.evaluate_answer(
        question='如何处理重试？', answer='最多三次重试。', resume_context={}, chat_history=[]))
    assert '未给出重试次数' not in result['feedback']
    assert result['score'] == 7


def test_retry_count_does_not_prove_configuration_code_or_production_validation():
    payload = {'gaps': ['未给出重试次数的配置代码', '未给出生产验证，重试次数已说明']}
    assert AIService._check_answer_consistency(payload, '最多三次重试。') == payload
