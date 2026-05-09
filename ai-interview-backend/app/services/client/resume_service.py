import json
import logging
import os
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, Optional, List, Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.exceptions.http_exceptions import NotFoundError, ValidationError
from app.models.resume import Resume
from app.models.user import User
from app.services.client.ai_service import AIService
from app.services.client.embedding_match_service import embedding_match_service
from app.services.client.matching_engine import matching_engine
from app.services.common.deepseek_config_service import deepseek_config_service

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads/resumes"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ResumeService:
    @staticmethod
    def _build_analysis_payload(
        analysis: Optional[Dict],
        resume_evidence: Optional[Dict] = None,
    ) -> Dict:
        payload = dict(analysis or {})
        if resume_evidence:
            payload["resume_evidence"] = resume_evidence
            payload["evidence_summary"] = resume_evidence.get("evidence_summary") or []
        return payload

    @staticmethod
    def _extract_evidence_fields(analysis_payload: Optional[Dict]) -> tuple[Optional[Dict], Optional[list]]:
        if not isinstance(analysis_payload, dict):
            return None, None
        resume_evidence = analysis_payload.get("resume_evidence")
        if not isinstance(resume_evidence, dict):
            resume_evidence = None
        evidence_summary = analysis_payload.get("evidence_summary")
        if not isinstance(evidence_summary, list) and resume_evidence:
            evidence_summary = resume_evidence.get("evidence_summary")
        if not isinstance(evidence_summary, list):
            evidence_summary = None
        return resume_evidence, evidence_summary

    @staticmethod
    async def create_resume_upload(
        db: AsyncSession,
        user_id: int,
        file_content: bytes,
        file_name: str,
        target_position: str,
    ) -> Dict:
        safe_name = Path(file_name or "resume.pdf").name or "resume.pdf"
        file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{uuid4().hex}_{safe_name}")

        try:
            with open(file_path, "wb") as file_obj:
                file_obj.write(file_content)
        except OSError as exc:
            logger.exception("Save resume file failed: %s", exc)
            raise ValidationError(message="简历文件保存失败，请稍后重试") from exc

        resume = Resume(
            user_id=user_id,
            file_url=file_path,
            file_name=safe_name,
            target_position=target_position,
            status="queued",
        )
        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        return {
            "resume_id": resume.id,
            "status": resume.status,
            "message": "简历上传成功，已进入解析队列",
        }

    @staticmethod
    async def process_resume(
        resume_id: int,
        ai_config: Optional[Dict] = None,
    ) -> None:
        async with async_session() as db:
            result = await db.execute(select(Resume).where(Resume.id == resume_id))
            resume = result.scalar_one_or_none()
            if not resume:
                logger.warning("Resume %s not found for async processing", resume_id)
                return

            await ResumeService._process_resume_record(db, resume, ai_config=ai_config)

    @staticmethod
    async def _process_resume_record(
        db: AsyncSession,
        resume: Resume,
        ai_config: Optional[Dict] = None,
    ) -> None:
        if ai_config is None:
            try:
                ai_config = await ResumeService._build_runtime_config(db, resume)
            except ValidationError as exc:
                await ResumeService._mark_resume_failed(db, resume, exc.detail)
                return
            except Exception as exc:
                logger.exception(
                    "Build runtime config failed for resume %s: %s", resume.id, exc
                )
                await ResumeService._mark_resume_failed(
                    db,
                    resume,
                    "无法读取当前账号的 AI 配置，请先在个人中心确认 API 设置后重试",
                )
                return

        logger.info(
            "Resume processing started: resume_id=%s provider=%s model=%s",
            resume.id,
            (ai_config or {}).get("provider"),
            (ai_config or {}).get("model"),
        )

        await ResumeService._update_status(db, resume, "extracting")
        try:
            resume_text = ResumeService._extract_pdf_text(resume.file_url or "")
            if not resume_text.strip():
                raise ValidationError(message="无法从 PDF 中提取文本内容")
        except ValidationError as exc:
            await ResumeService._mark_resume_failed(db, resume, exc.detail)
            return
        except Exception as exc:
            logger.exception("PDF parse failed for resume %s: %s", resume.id, exc)
            await ResumeService._mark_resume_failed(db, resume, f"PDF 解析失败: {str(exc)}")
            return

        await ResumeService._update_status(db, resume, "parsing")
        try:
            parsed = await AIService.parse_resume(resume_text, ai_config=ai_config)
            resume.parsed_content = json.dumps(parsed, ensure_ascii=False)
            await db.commit()
            await db.refresh(resume)
        except ValidationError as exc:
            await ResumeService._mark_resume_failed(db, resume, exc.detail)
            return
        except JSONDecodeError as exc:
            logger.exception("Resume parse JSON decode failed for resume %s: %s", resume.id, exc)
            await ResumeService._mark_resume_failed(
                db,
                resume,
                "AI 返回的简历解析结果格式异常，请稍后重试或更换模型",
            )
            return
        except Exception as exc:
            logger.exception("Resume parse failed for resume %s: %s", resume.id, exc)
            await ResumeService._mark_resume_failed(
                db,
                resume,
                "简历结构化解析失败，请稍后重试",
            )
            return

        await ResumeService._update_status(db, resume, "evidencing")
        try:
            resume_evidence = await AIService.extract_resume_evidence(
                parsed,
                resume.target_position or "",
                ai_config=ai_config,
            )
        except Exception as exc:
            logger.warning(
                "Resume evidence extraction failed for resume %s, fallback to deterministic evidence: %s",
                resume.id,
                exc,
            )
            resume_evidence = AIService.build_resume_evidence_fallback(parsed)

        await ResumeService._update_status(db, resume, "analyzing")
        try:
            analysis = await AIService.analyze_resume(
                parsed,
                resume.target_position or "",
                resume_evidence=resume_evidence,
                ai_config=ai_config,
            )
            analysis = await ResumeService._attach_matching_metrics(
                analysis,
                parsed_resume=parsed,
                target_position=resume.target_position or "",
                resume_evidence=resume_evidence,
                db=db,
                user_id=resume.user_id,
            )
            resume.analysis = json.dumps(
                ResumeService._build_analysis_payload(analysis, resume_evidence),
                ensure_ascii=False,
            )
            resume.status = "completed"
            await db.commit()
            await db.refresh(resume)
        except ValidationError as exc:
            await ResumeService._mark_resume_failed(db, resume, exc.detail)
        except JSONDecodeError as exc:
            logger.exception("Resume analysis JSON decode failed for resume %s: %s", resume.id, exc)
            await ResumeService._mark_resume_failed(
                db,
                resume,
                "AI 返回的简历分析结果格式异常，请稍后重试或更换模型",
            )
        except Exception as exc:
            logger.exception("Resume analysis failed for resume %s: %s", resume.id, exc)
            await ResumeService._mark_resume_failed(
                db,
                resume,
                "简历分析服务异常，请稍后重试",
            )

    @staticmethod
    async def _attach_matching_metrics(
        analysis: Optional[Dict],
        parsed_resume: Dict,
        target_position: str,
        resume_evidence: Optional[Dict] = None,
        db: Optional[AsyncSession] = None,
        user_id: Optional[int] = None,
    ) -> Dict:
        payload = dict(analysis or {})
        metrics = matching_engine.evaluate(
            parsed_resume=parsed_resume,
            target_position=target_position,
            llm_analysis=payload,
            resume_evidence=resume_evidence,
        )
        embedding_candidates: list[Dict] = []
        if db is not None and user_id is not None:
            user = await db.get(User, user_id)
            embedding_candidates = deepseek_config_service.build_embedding_candidates(user)
        metrics = await embedding_match_service.enrich_metrics(
            metrics=metrics,
            parsed_resume=parsed_resume,
            target_position=target_position,
            embedding_candidates=embedding_candidates,
        )
        payload["matching_metrics"] = metrics
        payload["keyword_coverage"] = metrics["keyword_coverage"]
        payload["semantic_score"] = metrics["semantic_score"]
        payload["rule_score"] = metrics["rule_score"]
        payload["final_score"] = metrics["final_score"]
        payload["evidence_basis"] = metrics["evidence_basis"]
        payload["ability_gap_profile"] = metrics.get("ability_gap_profile")
        payload["learning_priority_summary"] = metrics.get("learning_priority_summary") or []
        return payload

    @staticmethod
    async def _build_runtime_config(db: AsyncSession, resume: Resume) -> Dict:
        user = await db.get(User, resume.user_id)
        if not user:
            raise ValidationError(message="上传简历的用户不存在")
        return deepseek_config_service.build_runtime_config(
            user,
            require_personal_key=True,
        )

    @staticmethod
    async def _update_status(db: AsyncSession, resume: Resume, status: str) -> None:
        resume.status = status
        await db.commit()
        await db.refresh(resume)

    @staticmethod
    async def _mark_resume_failed(
        db: AsyncSession,
        resume: Resume,
        error_message: str,
    ) -> None:
        resume.status = "failed"
        resume.analysis = json.dumps({"error_message": error_message}, ensure_ascii=False)
        await db.commit()
        await db.refresh(resume)

    @staticmethod
    def _extract_pdf_text(file_path: str) -> str:
        import pdfplumber

        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

    @staticmethod
    async def get_resume(db: AsyncSession, resume_id: int, user_id: int) -> Dict:
        query = select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == user_id,
        )
        result = await db.execute(query)
        resume = result.scalar_one_or_none()

        if not resume:
            raise NotFoundError(message="简历不存在")

        parsed_content = None
        if resume.parsed_content:
            try:
                parsed_content = json.loads(resume.parsed_content)
            except json.JSONDecodeError:
                parsed_content = None

        analysis = None
        error_message = None
        resume_evidence = None
        evidence_summary = None
        if resume.analysis:
            try:
                analysis = json.loads(resume.analysis)
                if isinstance(analysis, dict):
                    error_message = analysis.get("error_message")
                    resume_evidence, evidence_summary = ResumeService._extract_evidence_fields(analysis)
            except json.JSONDecodeError:
                analysis = None

        return {
            "resume_id": resume.id,
            "status": resume.status,
            "file_name": resume.file_name,
            "target_position": resume.target_position,
            "parsed_content": parsed_content,
            "analysis": analysis,
            "resume_evidence": resume_evidence,
            "evidence_summary": evidence_summary,
            "error_message": error_message,
            "created_at": resume.created_at.isoformat() if resume.created_at else None,
        }

    @staticmethod
    async def get_user_resumes(db: AsyncSession, user_id: int) -> list:
        query = select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
        result = await db.execute(query)
        resumes = result.scalars().all()

        return [
            {
                "resume_id": item.id,
                "file_name": item.file_name,
                "target_position": item.target_position,
                "status": item.status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in resumes
        ]


resume_service = ResumeService()
