from fastapi import APIRouter, Depends, Header
from app.models.user import User
from app.api.client.deps import require_base_privacy_consent
from app.exceptions.http_exceptions import APIException
from typing import Optional

router = APIRouter()


@router.get("/temporary-credentials")
async def get_temporary_credentials(
    language: str = Header(None),
    current_user: User = Depends(require_base_privacy_consent)
):
    """Temporary credential export is disabled; use server-side upload proxy instead."""
    raise APIException(
        status_code=410,
        message="Temporary AWS credentials are disabled for security. Use server-side upload or presigned scoped URLs.",
        language=language,
    )
