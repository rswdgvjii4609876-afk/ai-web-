import asyncio
import logging

from app.core.celery_app import celery_app
from app.services.client.resume_service import resume_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, name="app.schedule.jobs.resume_tasks.process_resume")
def process_resume_task(self, resume_id: int, ai_config: dict | None = None):
    try:
        asyncio.run(resume_service.process_resume(resume_id, ai_config=ai_config))
        return {"status": "success", "resume_id": resume_id}
    except Exception as exc:
        logger.exception("Resume processing task failed for resume %s: %s", resume_id, exc)
        if self.request.retries < self.max_retries:
            countdown = 30 * (self.request.retries + 1)
            raise self.retry(countdown=countdown, exc=exc)
        raise
