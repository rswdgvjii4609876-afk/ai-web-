from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session
from app.exceptions.http_exceptions import ValidationError
from app.models.resume import Resume
from app.models.user import User
from app.services.client.ai_service import AIService
from app.services.client.interview_service import InterviewService
from app.services.client.privacy_consent_service import privacy_consent_service
from app.services.client.resume_service import ResumeService
from app.services.client.resume_text_extractor import ResumeTextExtractor
from app.services.client.training_review_service import training_review_service
from app.services.common.deepseek_config_service import deepseek_config_service

SUPPORTED_SUFFIXES = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
}
POSITION_HINTS = {
    "Python后端开发工程师": [
        "python",
        "fastapi",
        "django",
        "flask",
        "redis",
        "postgresql",
        "mysql",
        "docker",
        "api",
        "后端",
    ],
    "产品助理/产品经理实习生": [
        "产品",
        "prd",
        "需求",
        "原型",
        "figma",
        "axure",
        "用户研究",
        "竞品",
        "数据分析",
    ],
    "人力资源专员": [
        "人力",
        "招聘",
        "面试",
        "候选人",
        "员工",
        "培训",
        "hr",
        "薪酬",
    ],
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""),
        encoding="utf-8",
    )


def _scan_resume_files(resume_dir: Path) -> list[Path]:
    if not resume_dir.exists():
        raise FileNotFoundError(f"resume_dir does not exist: {resume_dir}")
    return sorted(
        [
            item
            for item in resume_dir.iterdir()
            if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES
        ],
        key=lambda item: item.name.lower(),
    )


def recommend_target_position(text: str, file_name: str, override: str | None = None) -> dict[str, Any]:
    if override:
        return {"target_position": override, "score": None, "matched_terms": [], "source": "override"}
    file_payload = (file_name or "").lower()
    text_payload = (text or "").lower()
    scored: list[tuple[int, str, list[str]]] = []
    for position, terms in POSITION_HINTS.items():
        text_matches = [term for term in terms if term.lower() in text_payload]
        file_matches = [term for term in terms if term.lower() in file_payload]
        score = len(text_matches) + len(file_matches) * 8
        scored.append((score, position, list(dict.fromkeys(file_matches + text_matches))))
    scored.sort(key=lambda item: (-item[0], item[1]))
    top_score, position, matched_terms = scored[0]
    if top_score <= 0:
        return {
            "target_position": "产品助理/产品经理实习生",
            "score": 0,
            "matched_terms": [],
            "source": "fallback",
        }
    return {
        "target_position": position,
        "score": top_score,
        "matched_terms": matched_terms[:8],
        "source": "heuristic",
    }


def semi_synthetic_metadata(
    source_file: Path,
    file_hash: str,
    target_position: str,
    *,
    data_contribution_consent: bool = False,
) -> dict[str, Any]:
    contributed = bool(data_contribution_consent)
    return {
        "sample_origin": "simulated_from_resume",
        "candidate_answer_source": "ai_simulated",
        "for_real_sft": False,
        "for_training": False,
        "for_semi_synthetic_training": contributed,
        "for_competition_demo": True,
        "data_contribution_consent": contributed,
        "semi_synthetic_data_contribution": contributed,
        "source_file_name": source_file.name,
        "source_file_sha256": file_hash,
        "target_position": target_position,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": (
            "半合成样本只用于流程压测、演示和 SFT Preview；不能作为真实用户完整面试样本，"
            "不能进入真实 OpenAI SFT。"
        ),
    }


def _build_runtime_config_from_env() -> dict[str, Any] | None:
    api_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        return None
    return {
        "provider": "deepseek",
        "provider_label": "DeepSeek",
        "source": "env_deepseek",
        "api_key": api_key,
        "base_url": os.environ.get("DEEPSEEK_BASE_URL") or settings.DEEPSEEK_BASE_URL,
        "model": os.environ.get("DEEPSEEK_MODEL") or settings.DEEPSEEK_MODEL,
        "thinking": settings.DEEPSEEK_THINKING,
        "reasoning_effort": settings.DEEPSEEK_REASONING_EFFORT,
    }


async def _resolve_runtime_config(db, user: User) -> dict[str, Any]:
    env_config = _build_runtime_config_from_env()
    if env_config:
        return env_config
    return deepseek_config_service.build_runtime_config(
        user,
        require_personal_key=True,
        provider="deepseek",
    )


async def generate_simulated_answer(
    *,
    resume_text: str,
    target_position: str,
    question: str,
    round_index: int,
    ai_config: dict[str, Any],
) -> str:
    prompt = f"""
你正在扮演一名求职者，必须严格基于下面简历文本回答面试官问题。

要求：
1. 不要编造简历里没有的公司、项目、证书、时间、百分比或技术经历。
2. 如果简历没有证据，回答要承认“这部分经历较少”，并说明会如何补充学习。
3. 回答 120-220 字，使用第一人称，包含场景、行动和结果，但结果不能写虚假量化指标。
4. 这是半合成流程压测样本，不能冒充真实用户回答。

目标岗位：{target_position}
第 {round_index + 1} 轮问题：{question}
简历文本：
{resume_text[:4500]}
""".strip()
    try:
        answer = await AIService._chat(
            [
                {"role": "system", "content": "你是谨慎的面试者模拟器，只能根据简历证据回答。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            ai_config=ai_config,
        )
        return answer.strip() or _fallback_simulated_answer(target_position, question)
    except Exception:
        return _fallback_simulated_answer(target_position, question)


def _fallback_simulated_answer(target_position: str, question: str) -> str:
    return (
        f"针对{target_position}这个方向，我会先基于简历中已有的项目和技能回答。"
        f"这个问题是：{question[:80]}。如果简历里没有直接证据，我不会把岗位要求说成真实经历，"
        "会说明自己目前证据不足，并补充下一步会通过小项目、复盘和练习来补齐。"
    )


def build_preview_record(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "metadata": {
            **item["metadata"],
            "record_type": "semi_synthetic_closed_loop_preview",
        },
        "resume": {
            "resume_id": item.get("resume_id"),
            "file_name": item.get("file_name"),
            "target_position": item.get("target_position"),
            "parse_quality": item.get("parse_quality"),
        },
        "interview": {
            "interview_id": item.get("interview_id"),
            "rounds": item.get("rounds"),
            "status": item.get("interview_status"),
            "overall_score": item.get("overall_score"),
        },
        "outputs": {
            "polish_generated": bool(item.get("polish_result")),
            "report_generated": bool(item.get("report")),
            "training_review_saved": bool(item.get("training_review")),
        },
    }


def dry_run(resume_dir: Path, out_dir: Path, *, target_position: str | None, limit: int | None) -> dict[str, Any]:
    files = _scan_resume_files(resume_dir)
    if limit:
        files = files[:limit]
    manifest: list[dict[str, Any]] = []
    for file_path in files:
        extraction = ResumeTextExtractor.extract(file_path, enable_ocr=settings.ENABLE_RESUME_OCR)
        text = extraction.get("text") or ""
        recommendation = recommend_target_position(text, file_path.name, override=target_position)
        suffix = file_path.suffix.lower()
        blocked_reason = None
        if suffix in {".jpg", ".jpeg", ".png"} and not text.strip():
            blocked_reason = "image_ocr_unavailable_or_disabled"
        elif not text.strip():
            blocked_reason = "text_extraction_empty"
        manifest.append(
            {
                "file_name": file_path.name,
                "file_type": SUPPORTED_SUFFIXES.get(suffix),
                "sha256": _sha256(file_path),
                "char_count": len(text),
                "parse_quality": extraction.get("parse_quality"),
                "recommended_position": recommendation,
                "status": "blocked" if blocked_reason else "ready",
                "blocked_reason": blocked_reason,
                "metadata": semi_synthetic_metadata(
                    file_path,
                    _sha256(file_path),
                    recommendation["target_position"],
                ),
            }
        )
    summary = {
        "mode": "dry_run",
        "resume_dir": str(resume_dir),
        "total_files": len(files),
        "ready_files": sum(1 for item in manifest if item["status"] == "ready"),
        "blocked_files": sum(1 for item in manifest if item["status"] == "blocked"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary": "Dry-run does not call DeepSeek, write DB records, or create real SFT samples.",
    }
    _write_json(out_dir / "manifest.preview.json", manifest)
    _write_json(out_dir / "summary.preview.json", summary)
    _write_jsonl(out_dir / "semi_synthetic.preview.jsonl", [item["metadata"] for item in manifest])
    (out_dir / "README.md").write_text(
        "# 半合成简历闭环 dry-run\n\n"
        f"- total_files: {summary['total_files']}\n"
        f"- ready_files: {summary['ready_files']}\n"
        f"- blocked_files: {summary['blocked_files']}\n"
        "- 该目录不包含 API Key，不可作为真实 OpenAI SFT 输入。\n",
        encoding="utf-8",
    )
    return {"summary": summary, "manifest": manifest}


async def _load_user(db, *, user_id: int | None, user_email: str | None) -> User:
    if user_id is not None:
        user = await db.get(User, user_id)
    elif user_email:
        result = await db.execute(select(User).where(User.email == user_email))
        user = result.scalar_one_or_none()
    else:
        result = await db.execute(select(User).order_by(User.id.asc()).limit(1))
        user = result.scalar_one_or_none()
    if not user:
        raise ValidationError(message="未找到用于跑测的用户，请传 --user-id 或 --user-email")
    return user


async def run_actual(args: argparse.Namespace, out_dir: Path) -> dict[str, Any]:
    files = _scan_resume_files(args.resume_dir)
    if args.limit:
        files = files[: args.limit]
    results: list[dict[str, Any]] = []
    preview_records: list[dict[str, Any]] = []
    async with async_session() as db:
        user = await _load_user(db, user_id=args.user_id, user_email=args.user_email)
        if args.apply_personal_mode_consent:
            privacy_consent_service.apply_base_consent(user, agreed=True)
            await db.commit()
            await db.refresh(user)
        ai_config = await _resolve_runtime_config(db, user)
        safe_ai_config = {
            "provider": ai_config.get("provider"),
            "model": ai_config.get("model"),
            "base_url": ai_config.get("base_url"),
            "source": ai_config.get("source"),
        }
        for file_path in files:
            file_hash = _sha256(file_path)
            extraction = ResumeTextExtractor.extract(file_path, enable_ocr=settings.ENABLE_RESUME_OCR)
            resume_text = extraction.get("text") or ""
            recommendation = recommend_target_position(resume_text, file_path.name, override=args.target_position)
            target_position = recommendation["target_position"]
            metadata = semi_synthetic_metadata(
                file_path,
                file_hash,
                target_position,
                data_contribution_consent=bool(args.contribute_semi_synthetic),
            )
            item: dict[str, Any] = {
                "file_name": file_path.name,
                "sha256": file_hash,
                "target_position": target_position,
                "parse_quality": extraction.get("parse_quality"),
                "metadata": metadata,
                "status": "started",
            }
            if not resume_text.strip():
                item.update({"status": "blocked", "blocked_reason": "text_extraction_empty"})
                results.append(item)
                continue
            try:
                semi_synthetic_consent = bool(args.contribute_semi_synthetic)
                privacy_snapshot = privacy_consent_service.build_snapshot(
                    user,
                    data_contribution_consent=semi_synthetic_consent,
                    source="semi_synthetic_resume_batch",
                )
                privacy_snapshot.update(metadata)
                upload_result = await ResumeService.create_resume_upload(
                    db=db,
                    user_id=user.id,
                    file_content=file_path.read_bytes(),
                    file_name=file_path.name,
                    target_position=target_position,
                    data_contribution_consent=semi_synthetic_consent,
                    privacy_consent_snapshot=privacy_snapshot,
                )
                resume = await db.get(Resume, upload_result["resume_id"])
                if not resume:
                    raise ValidationError(message="简历记录创建后未找到")
                await ResumeService._process_resume_record(db, resume, ai_config=ai_config)
                await db.refresh(resume)
                item["resume_id"] = resume.id
                item["resume_status"] = resume.status
                if resume.status != "completed":
                    item.update({"status": "failed", "error": "resume_processing_failed"})
                    results.append(item)
                    continue

                polish_result = await ResumeService.polish_resume(
                    db=db,
                    resume_id=resume.id,
                    user_id=user.id,
                    target_position=target_position,
                    ai_config=ai_config,
                )
                item["polish_result"] = {
                    "generated": True,
                    "summary": polish_result.get("summary") or polish_result.get("overall_advice"),
                }

                interview_result = await InterviewService.start_interview(
                    db=db,
                    user_id=user.id,
                    resume_id=resume.id,
                    target_position=target_position,
                    knowledge_base_id=None,
                    difficulty=args.difficulty,
                    total_questions=args.rounds,
                    ai_config=ai_config,
                    data_contribution_consent=semi_synthetic_consent,
                    privacy_consent_snapshot={**privacy_snapshot, "source": "semi_synthetic_interview_batch"},
                )
                interview_id = interview_result["interview_id"]
                item["interview_id"] = interview_id
                question = interview_result["first_question"]
                question_index = int(interview_result.get("question_index") or 0)
                answers: list[dict[str, Any]] = []
                for round_index in range(args.rounds):
                    answer = await generate_simulated_answer(
                        resume_text=resume_text,
                        target_position=target_position,
                        question=question,
                        round_index=round_index,
                        ai_config=ai_config,
                    )
                    submit_result = await InterviewService.submit_answer(
                        db=db,
                        user_id=user.id,
                        interview_id=interview_id,
                        answer=answer,
                        question_index=question_index,
                        ai_config=ai_config,
                    )
                    answers.append(
                        {
                            "question_index": question_index,
                            "candidate_answer_source": "ai_simulated",
                            "score": submit_result.get("score"),
                        }
                    )
                    if submit_result.get("is_finished"):
                        break
                    question = submit_result.get("next_question") or ""
                    question_index = int(submit_result.get("question_index", question_index)) + 1

                review = await training_review_service.upsert_review(
                    db=db,
                    user_id=user.id,
                    interview_id=interview_id,
                    data={
                        "self_rating": "半合成",
                        "notes": "半合成闭环跑测：AI 根据简历模拟候选人回答，仅用于流程压测和展示。",
                        "next_goal": "人工复核后再决定是否转为真实授权样本；默认不得进入真实 SFT。",
                    },
                )
                interview_payload = await InterviewService.get_report(db, user.id, interview_id)
                item.update(
                    {
                        "status": "completed",
                        "rounds": len(answers),
                        "interview_status": "completed",
                        "overall_score": interview_payload.get("overall_score"),
                        "report": bool(interview_payload.get("report")),
                        "training_review": review,
                    }
                )
                preview_records.append(build_preview_record(item))
            except Exception as exc:
                item.update({"status": "failed", "error": str(exc)})
            results.append(item)

    summary = {
        "mode": "actual",
        "resume_dir": str(args.resume_dir),
        "total_files": len(files),
        "completed": sum(1 for item in results if item.get("status") == "completed"),
        "failed": sum(1 for item in results if item.get("status") == "failed"),
        "blocked": sum(1 for item in results if item.get("status") == "blocked"),
        "ai_runtime": safe_ai_config if "safe_ai_config" in locals() else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "semi_synthetic_data_contribution": bool(args.contribute_semi_synthetic),
        "boundary": (
            "All records are contributed semi-synthetic samples; sample_origin=simulated_from_resume, "
            "candidate_answer_source=ai_simulated, and for_real_sft=false."
            if args.contribute_semi_synthetic
            else "All records are semi-synthetic and for_real_sft=false."
        ),
    }
    _write_json(out_dir / "run_result.json", results)
    _write_json(out_dir / "summary.json", summary)
    _write_jsonl(out_dir / "semi_synthetic.preview.jsonl", preview_records)
    if args.contribute_semi_synthetic:
        _write_jsonl(out_dir / "semi_synthetic.contributed.jsonl", preview_records)
    return {"summary": summary, "results": results}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run semi-synthetic resume closed-loop batch tests.")
    parser.add_argument("--resume-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-api-cost", action="store_true")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--user-email", default=None)
    parser.add_argument("--target-position", default=None)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--difficulty", default="medium")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--contribute-semi-synthetic", dest="contribute_semi_synthetic", action="store_true")
    parser.add_argument("--no-contribute-semi-synthetic", dest="contribute_semi_synthetic", action="store_false")
    parser.add_argument("--no-apply-personal-mode-consent", dest="apply_personal_mode_consent", action="store_false")
    parser.set_defaults(apply_personal_mode_consent=True, contribute_semi_synthetic=True)
    args = parser.parse_args()
    args.resume_dir = args.resume_dir.resolve()
    if args.out is None:
        args.out = _repo_root() / "logs" / "semi_synthetic_resume_runs" / _utc_stamp()
    else:
        args.out = args.out.resolve()
    if args.rounds < 1:
        parser.error("--rounds must be >= 1")
    if not args.dry_run and not args.confirm_api_cost:
        parser.error("actual API run requires --confirm-api-cost; use --dry-run for inspection")
    return args


def main() -> int:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        result = dry_run(args.resume_dir, args.out, target_position=args.target_position, limit=args.limit)
    else:
        result = asyncio.run(run_actual(args, args.out))
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"report_dir={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
