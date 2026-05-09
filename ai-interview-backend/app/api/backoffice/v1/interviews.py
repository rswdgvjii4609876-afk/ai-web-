import json
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.backoffice.deps import get_current_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.models.interview import Interview
from app.models.interview_message import InterviewMessage
from app.models.user import User
from app.schemas.backoffice.interview import TrainingSampleReviewUpdate
from app.schemas.response import ApiResponse
from app.services.client.interview_service import interview_service

router = APIRouter()


@router.get("")
async def list_interviews(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """List interview records for backoffice review."""
    query = (
        select(Interview, User.email)
        .outerjoin(User, Interview.user_id == User.id)
        .order_by(Interview.created_at.desc())
    )
    count_query = select(func.count()).select_from(Interview)

    if status:
        query = query.where(Interview.status == status)
        count_query = count_query.where(Interview.status == status)

    total = await db.scalar(count_query)
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rows = result.all()

    items = [
        {
            "id": interview.id,
            "user_email": email or f"用户ID {interview.user_id}",
            "target_position": interview.target_position,
            "difficulty": interview.difficulty,
            "total_questions": interview.total_questions,
            "overall_score": float(interview.overall_score) if interview.overall_score else None,
            "status": interview.status,
            "training_sample_review": interview_service.get_training_sample_review(interview.panel_snapshot),
            "created_at": interview.created_at.isoformat() if interview.created_at else None,
        }
        for interview, email in rows
    ]

    return ApiResponse.success(data={"items": items, "total": total, "page": page, "per_page": per_page})


@router.get("/training-samples/export")
async def export_training_samples(
    limit: int = 20,
    min_score: Optional[float] = None,
    include_user_email: bool = False,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Export completed interviews as versioned training samples."""
    safe_limit = min(max(int(limit or 20), 1), 100)
    samples = await interview_service.get_completed_training_samples(
        db=db,
        include_user_email=include_user_email,
        min_score=min_score,
        limit=safe_limit,
    )

    return ApiResponse.success(
        data={
            "sample_version": "ai-interview.training-sample.v1",
            "items": samples,
            "total": len(samples),
            "limit": safe_limit,
            "min_score": min_score,
            "pii_included": include_user_email,
        }
    )


@router.get("/evaluation-datasets/preview")
async def get_evaluation_dataset_preview(
    include_user_email: bool = False,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Preview offline evaluation datasets derived from reviewed interview samples."""
    samples = await interview_service.get_completed_training_samples(
        db=db,
        include_user_email=include_user_email,
    )
    bundle = interview_service.build_evaluation_dataset_bundle(
        samples=samples,
        include_user_email=include_user_email,
    )
    return ApiResponse.success(data=bundle["preview"])


@router.get("/evaluation-datasets/export")
async def export_evaluation_datasets(
    include_user_email: bool = False,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Export offline evaluation datasets as ZIP + JSONL files."""
    samples = await interview_service.get_completed_training_samples(
        db=db,
        include_user_email=include_user_email,
    )
    bundle = interview_service.build_evaluation_dataset_bundle(
        samples=samples,
        include_user_email=include_user_email,
    )
    zip_bytes = interview_service.build_evaluation_dataset_zip(bundle)
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="ai-interview-evaluation-datasets.zip"',
        },
    )


@router.get("/{interview_id}")
async def get_interview_detail(
    interview_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Get one interview record with messages and report."""
    interview = await db.get(Interview, interview_id)
    if not interview:
        return ApiResponse.failed(message="面试记录不存在", body_code=404, http_code=404)

    msg_query = (
        select(InterviewMessage)
        .where(InterviewMessage.interview_id == interview_id)
        .order_by(InterviewMessage.id)
    )
    msg_result = await db.execute(msg_query)
    messages = msg_result.scalars().all()

    report = {}
    if interview.report:
        try:
            report = json.loads(interview.report)
        except json.JSONDecodeError:
            report = {}
    training_sample_review = interview_service.get_training_sample_review(interview.panel_snapshot)

    return ApiResponse.success(
        data={
            "id": interview.id,
            "target_position": interview.target_position,
            "difficulty": interview.difficulty,
            "total_questions": interview.total_questions,
            "overall_score": float(interview.overall_score) if interview.overall_score else None,
            "status": interview.status,
            "interview_mode": interview.interview_mode,
            "report": report,
            "training_sample_review": training_sample_review,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "question_index": m.question_index,
                    "score": float(m.score) if m.score else None,
                    "feedback": m.feedback,
                }
                for m in messages
            ],
            "created_at": interview.created_at.isoformat() if interview.created_at else None,
        }
    )


@router.put("/{interview_id}/training-sample-review")
async def update_interview_training_sample_review(
    interview_id: int,
    payload: TrainingSampleReviewUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Save manual review signals for one interview training sample."""
    review = await interview_service.update_training_sample_review(
        db=db,
        interview_id=interview_id,
        review_data=payload.model_dump(),
        reviewer_email=current_admin.email,
    )
    return ApiResponse.success(message="训练样本标注已保存", data=review)


@router.get("/{interview_id}/training-sample")
async def get_interview_training_sample(
    interview_id: int,
    include_user_email: bool = False,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Export one interview as a versioned training sample."""
    result = await db.execute(
        select(Interview, User.email)
        .join(User, Interview.user_id == User.id)
        .where(Interview.id == interview_id)
    )
    row = result.first()
    if not row:
        return ApiResponse.failed(message="面试记录不存在", body_code=404, http_code=404)

    interview, email = row
    msg_result = await db.execute(
        select(InterviewMessage)
        .where(InterviewMessage.interview_id == interview_id)
        .order_by(InterviewMessage.id)
    )
    sample = interview_service.build_training_sample(
        interview=interview,
        messages=msg_result.scalars().all(),
        user_email=email,
        include_user_email=include_user_email,
    )
    return ApiResponse.success(data=sample)


@router.delete("/{interview_id}")
async def delete_interview(
    interview_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Delete one interview record from backoffice."""
    result = await interview_service.delete_interview_admin(db, interview_id)
    return ApiResponse.success(data=result)
