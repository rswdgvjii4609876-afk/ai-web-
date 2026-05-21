import pytest

from app.models.learning_plan import LearningPlan
from app.models.learning_task import LearningTask
from app.services.client.learning_plan_service import LearningPlanService
from app.services.client.learning_task_service import LearningTaskService


@pytest.mark.unit
def test_learning_task_normalize_accepts_plan_linkage_fields():
    payload = LearningTaskService._normalize_input(
        {
            "task_id": "plan_3__step_1",
            "title": "Complete one FastAPI practice",
            "learning_plan_id": 3,
            "step_order": 1,
        }
    )

    assert payload["learning_plan_id"] == 3
    assert payload["step_order"] == 1


@pytest.mark.unit
def test_learning_plan_serialize_returns_progress_and_next_action():
    plan = LearningPlan(
        id=9,
        user_id=1,
        title="Python backend plan",
        status="draft",
        target_position="Python Backend",
        plan_days=14,
        daily_minutes=45,
    )
    tasks = [
        LearningTask(id=1, user_id=1, task_key="t1", title="Done task", done=True, step_order=1),
        LearningTask(id=2, user_id=1, task_key="t2", title="Next task", done=False, step_order=2),
    ]

    payload = LearningPlanService._serialize_plan(plan, tasks)

    assert payload["learning_plan_id"] == 9
    assert payload["progress"]["total"] == 2
    assert payload["progress"]["done"] == 1
    assert payload["progress"]["completion_rate"] == 50
    assert payload["next_action"]["type"] == "continue_task"
    assert payload["next_action"]["task_key"] == "t2"
