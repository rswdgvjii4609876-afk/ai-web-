from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.backoffice.deps import get_current_admin
from app.api.client.v1 import competition as client_competition

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/demo-cases")
async def list_demo_cases():
    return await client_competition.list_demo_cases()


@router.get("/agent-trace/{case_id}")
async def get_agent_trace(case_id: str):
    return await client_competition.get_agent_trace(case_id)


@router.get("/eval-preview/{case_id}")
async def get_eval_preview(case_id: str):
    return await client_competition.get_eval_preview(case_id)


@router.get("/sft-preview")
async def get_sft_preview():
    return await client_competition.get_sft_preview()
