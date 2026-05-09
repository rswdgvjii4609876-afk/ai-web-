from fastapi import APIRouter

from app.constants.competition import COMPETITION_DEMO_ASSETS
from app.schemas.response import ApiResponse
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


# 创建PDF并在后台处理
@router.post("")
async def demo():
    return ApiResponse.success_without_data()


@router.get("/competition")
async def get_competition_demo_assets():
    return ApiResponse.success(data=COMPETITION_DEMO_ASSETS)
