from fastapi import APIRouter, Depends
from app.api.backoffice.deps import get_current_admin
from app.exceptions.http_exceptions import APIException
from app.models.admin import Admin

router = APIRouter()


@router.get("/temporary-credentials")
async def get_temporary_credentials(
    current_admin: Admin = Depends(get_current_admin),
):
    """Temporary credential export is disabled; use server-side upload proxy instead."""
    raise APIException(
        status_code=410,
        message="Temporary AWS credentials are disabled for security. Use server-side upload or presigned scoped URLs.",
    )

