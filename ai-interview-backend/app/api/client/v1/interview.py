import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import get_current_user
from app.db.session import get_db
from app.exceptions.http_exceptions import ValidationError
from app.models.user import User
from app.schemas.client.interview import AnswerSubmit, InterviewStart
from app.schemas.response import ApiResponse
from app.services.client.interview_service import interview_service
from app.services.common.deepseek_config_service import deepseek_config_service

router = APIRouter()
logger = logging.getLogger(__name__)


START_INTERVIEW_ROUTE_ERROR_MESSAGE = (
    "开始面试失败：后端开始面试链路异常。"
    "请管理员查看 docker compose logs --tail=300 app 中 /api/v1/interviews/start 附近的第一条异常。"
)

START_INTERVIEW_ROUTE_DB_ERROR_MESSAGE = (
    "开始面试失败：数据库读取或写入异常，可能是服务器数据库迁移未完成。"
    "请管理员执行 alembic upgrade head，并查看后端日志中的第一条数据库异常。"
)


def _build_interview_runtime_config(
    current_user: User,
    ai_provider: str | None,
    ai_model: str | None,
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


@router.post("/start")
async def start_interview(
    data: InterviewStart,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await interview_service.start_interview(
            db=db,
            user_id=current_user.id,
            resume_id=data.resume_id,
            target_position=data.target_position,
            knowledge_base_id=data.knowledge_base_id,
            difficulty=data.difficulty,
            total_questions=data.total_questions,
            multi_interviewer_enabled=data.multi_interviewer_enabled,
            ai_config=_build_interview_runtime_config(
                current_user,
                data.ai_provider,
                data.ai_model,
            ),
        )
    except ValidationError:
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("Start interview endpoint database error: %s", exc)
        raise ValidationError(message=START_INTERVIEW_ROUTE_DB_ERROR_MESSAGE) from exc
    except Exception as exc:
        await db.rollback()
        logger.exception("Start interview endpoint unexpected error: %s", exc)
        raise ValidationError(message=START_INTERVIEW_ROUTE_ERROR_MESSAGE) from exc
    return ApiResponse.success(data=result)


@router.post("/{interview_id}/answer")
async def submit_answer(
    interview_id: int,
    data: AnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await interview_service.submit_answer(
        db=db,
        user_id=current_user.id,
        interview_id=interview_id,
        answer=data.answer,
        ai_config=deepseek_config_service.build_runtime_config(
            current_user,
            require_personal_key=True,
        ),
    )
    return ApiResponse.success(data=result)


@router.post("/{interview_id}/answer/stream")
async def submit_answer_stream(
    interview_id: int,
    data: AnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    generator = interview_service.submit_answer_stream(
        db=db,
        user_id=current_user.id,
        interview_id=interview_id,
        answer=data.answer,
        ai_config=deepseek_config_service.build_runtime_config(
            current_user,
            require_personal_key=True,
        ),
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{interview_id}/report")
async def get_report(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await interview_service.get_report(
        db=db,
        user_id=current_user.id,
        interview_id=interview_id,
    )
    return ApiResponse.success(data=result)


@router.get("/{interview_id}/messages")
async def get_messages(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await interview_service.get_interview_messages(
        db=db,
        user_id=current_user.id,
        interview_id=interview_id,
    )
    return ApiResponse.success(data=result)


@router.get("")
async def get_interviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await interview_service.get_interviews(
        db=db,
        user_id=current_user.id,
    )
    return ApiResponse.success(data=result)


@router.delete("/{interview_id}")
async def delete_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await interview_service.delete_interview(
        db=db,
        user_id=current_user.id,
        interview_id=interview_id,
    )
    return ApiResponse.success(data=result)
