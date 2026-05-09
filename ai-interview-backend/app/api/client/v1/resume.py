import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import get_current_user
from app.core.celery_app import celery_app
from app.db.session import get_db
from app.exceptions.http_exceptions import ValidationError
from app.models.user import User
from app.constants.competition import DEFAULT_TARGET_POSITION
from app.schemas.response import ApiResponse
from app.services.client.resume_service import resume_service
from app.services.common.deepseek_config_service import deepseek_config_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _has_available_resume_worker() -> bool:
    try:
        responses = celery_app.control.ping(timeout=1.0)
        return bool(responses)
    except Exception as exc:
        logger.warning("Resume worker ping failed, fallback to background task: %s", exc)
        return False


def _build_resume_runtime_config(
    current_user: User,
    ai_provider: Optional[str],
    ai_model: Optional[str],
) -> dict:
    ai_config = deepseek_config_service.build_runtime_config(
        current_user,
        require_personal_key=True,
        provider=ai_provider,
    )
    model = (ai_model or "").strip()
    if model:
        ai_config["model"] = model
    return ai_config


@router.post("/upload")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_position: str = Form(default=DEFAULT_TARGET_POSITION),
    ai_provider: Optional[str] = Form(default=None),
    ai_model: Optional[str] = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise ValidationError(message="仅支持上传 PDF 格式文件")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise ValidationError(message="文件大小不能超过 10MB")

    ai_config = _build_resume_runtime_config(current_user, ai_provider, ai_model)
    result = await resume_service.create_resume_upload(
        db=db,
        user_id=current_user.id,
        file_content=content,
        file_name=file.filename,
        target_position=target_position,
    )
    logger.info(
        "Resume upload accepted: resume_id=%s provider=%s model=%s",
        result["resume_id"],
        ai_config.get("provider"),
        ai_config.get("model"),
    )

    if _has_available_resume_worker():
        try:
            from app.schedule.jobs.resume_tasks import process_resume_task

            process_resume_task.delay(result["resume_id"], ai_config)
        except Exception as exc:
            logger.exception("Dispatch resume task failed, fallback to background task: %s", exc)
            background_tasks.add_task(
                resume_service.process_resume,
                result["resume_id"],
                ai_config,
            )
    else:
        background_tasks.add_task(
            resume_service.process_resume,
            result["resume_id"],
            ai_config,
        )

    return ApiResponse.success(data=result)


@router.get("/{resume_id}")
async def get_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await resume_service.get_resume(db, resume_id, current_user.id)
    return ApiResponse.success(data=result)


@router.get("")
async def get_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await resume_service.get_user_resumes(db, current_user.id)
    return ApiResponse.success(data=result)
