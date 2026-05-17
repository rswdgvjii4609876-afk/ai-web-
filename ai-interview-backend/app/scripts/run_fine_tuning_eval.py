from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings
from app.services.client.openai_fine_tuning_service import (
    DEFAULT_MIN_EVAL_SAMPLES,
    DEFAULT_OUTPUT_ROOT,
    OpenAIFineTuningDataError,
    build_openai_sft_provenance,
    load_jsonl_records,
    openai_api_key_from_env,
    resolve_fine_tuned_model_for_eval,
    validate_official_openai_base_url,
    validate_openai_fine_tuning_dataset_dir,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _extract_expected(record: Dict[str, Any]) -> Dict[str, Any]:
    assistant_messages = [item for item in record.get("messages") or [] if item.get("role") == "assistant"]
    if not assistant_messages:
        return {}
    content = assistant_messages[-1].get("content") or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"question": content}


def _prompt_messages(record: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"role": item["role"], "content": item.get("content") or ""}
        for item in record.get("messages") or []
        if item.get("role") in {"system", "user"}
    ]


def _split_terms(text: str) -> List[str]:
    terms = [text]
    for separator in ("与", "和", "、", "/", " ", "，", ",", "能力", "验证"):
        terms = [part for term in terms for part in term.split(separator)]
    return [term.strip() for term in terms if term.strip()]


def _score_response(content: str, expected: Dict[str, Any]) -> Dict[str, Any]:
    lowered = content.lower()
    target = str(expected.get("verification_target") or "")
    target_terms = [term for term in _split_terms(target) if len(term) >= 2]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {}
    has_question = bool(parsed.get("question") or "？" in content or "?" in content)
    target_hit = not target_terms or any(term.lower() in lowered for term in target_terms[:4])
    concrete_hit = any(term in content for term in ("场景", "行动", "结果", "指标", "如何", "为什么", "原因", "证明"))
    hallucination_guard = not any(
        phrase in content for phrase in ("你已经证明", "你负责了", "你主导了", "从你的简历可以看出你完成了")
    )
    score = sum([has_question, target_hit, concrete_hit, hallucination_guard])
    return {
        "score": score,
        "has_question": has_question,
        "target_hit": target_hit,
        "concrete_hit": concrete_hit,
        "hallucination_guard": hallucination_guard,
    }


def _chat_completion(client: OpenAI, model: str, messages: List[Dict[str, str]]) -> str:
    response = client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content or ""


def _build_markdown(result: Dict[str, Any]) -> str:
    lines = [
        "# 职启智评 OpenAI SFT Eval 对比报告",
        "",
        f"生成时间 UTC：`{result.get('generated_at_utc')}`",
        f"Base model：`{result.get('base_model')}`",
        f"Fine-tuned model：`{result.get('fine_tuned_model')}`",
        f"样本数：`{result.get('evaluated_items')}`",
        "",
        "## 结果概览",
        "",
        f"- Base 平均分：`{result.get('base_average_score')}`",
        f"- Fine-tuned 平均分：`{result.get('fine_tuned_average_score')}`",
        f"- 结论：`{result.get('conclusion')}`",
        "",
        "## 明细",
        "",
    ]
    for item in result.get("items") or []:
        lines.extend(
            [
                f"### 样本 {item.get('index')}",
                f"- 期望追问：{item.get('expected_question')}",
                f"- Base 分：`{item.get('base_score', {}).get('score')}`",
                f"- Fine-tuned 分：`{item.get('fine_tuned_score', {}).get('score')}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare base and fine-tuned models on the prepared holdout set.")
    parser.add_argument("--dataset-dir", default=str(DEFAULT_OUTPUT_ROOT / "latest"))
    parser.add_argument("--base-model", default="")
    parser.add_argument("--job-id", default="")
    parser.add_argument("--fine-tuned-model", default="")
    parser.add_argument("--max-items", type=int, default=DEFAULT_MIN_EVAL_SAMPLES)
    parser.add_argument("--allow-different-base", action="store_true")
    parser.add_argument("--confirm-cost", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    try:
        preflight = validate_openai_fine_tuning_dataset_dir(
            dataset_dir,
            require_ready=True,
            require_validation=True,
            min_eval_samples=DEFAULT_MIN_EVAL_SAMPLES,
        )
        base_url = validate_official_openai_base_url(os.getenv("OPENAI_BASE_URL", settings.OPENAI_BASE_URL))
        model_info = resolve_fine_tuned_model_for_eval(
            dataset_dir,
            requested_model=args.fine_tuned_model,
            requested_job_id=args.job_id,
            require_succeeded=not args.dry_run,
            preflight=preflight,
        )
    except OpenAIFineTuningDataError as exc:
        raise SystemExit(str(exc)) from exc

    validation_path = dataset_dir / "validation_openai.jsonl"
    if not validation_path.exists():
        raise SystemExit(f"Validation file not found: {validation_path}")
    records = load_jsonl_records(validation_path.read_text(encoding="utf-8"))
    if len(records) < DEFAULT_MIN_EVAL_SAMPLES:
        raise SystemExit(f"Need at least {DEFAULT_MIN_EVAL_SAMPLES} validation samples for eval; current={len(records)}.")

    recorded_base_model = str((model_info.get("job_record") or {}).get("base_model") or "")
    requested_base_model = args.base_model or recorded_base_model or settings.OPENAI_FINE_TUNE_BASE_MODEL or settings.OPENAI_MODEL
    if (
        args.base_model
        and recorded_base_model
        and args.base_model != recorded_base_model
        and not args.allow_different_base
    ):
        raise SystemExit(
            f"--base-model does not match job_record.json: requested={args.base_model}, recorded={recorded_base_model}. "
            "Use --allow-different-base only for explicit diagnostic comparisons."
        )

    fine_tuned_model = model_info.get("fine_tuned_model") or args.fine_tuned_model
    if not fine_tuned_model and not args.dry_run:
        raise SystemExit("Fine-tuned model id is required via --fine-tuned-model or job_status.json.")
    provenance = build_openai_sft_provenance(
        dataset_dir,
        preflight=preflight,
        base_model=requested_base_model,
        base_url=base_url,
    )
    if args.dry_run:
        result = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "dataset_dir": str(dataset_dir),
            "job_id": model_info.get("job_id"),
            "base_model": requested_base_model,
            "fine_tuned_model": fine_tuned_model,
            "evaluated_items": min(args.max_items, len(records)),
            "dry_run": True,
            "provenance": provenance,
            "message": "Eval preflight passed; no OpenAI API call was made.",
        }
        _write_json(dataset_dir / "eval_preflight.json", result)
        print("PASS: eval preflight passed; dry_run=true, no OpenAI API call was made.")
        return 0
    if not args.confirm_cost:
        raise SystemExit("Refusing to run paid OpenAI eval without --confirm-cost.")
    try:
        api_key = openai_api_key_from_env()
    except OpenAIFineTuningDataError as exc:
        raise SystemExit(str(exc)) from exc

    client = OpenAI(api_key=api_key, base_url=base_url)
    items = []
    for index, record in enumerate(records[: args.max_items], start=1):
        messages = _prompt_messages(record)
        expected = _extract_expected(record)
        base_content = _chat_completion(client, requested_base_model, messages)
        fine_tuned_content = _chat_completion(client, fine_tuned_model, messages)
        items.append(
            {
                "index": index,
                "expected_question": expected.get("question"),
                "base_response": base_content,
                "fine_tuned_response": fine_tuned_content,
                "base_score": _score_response(base_content, expected),
                "fine_tuned_score": _score_response(fine_tuned_content, expected),
            }
        )
    base_average = sum(item["base_score"]["score"] for item in items) / len(items)
    fine_tuned_average = sum(item["fine_tuned_score"]["score"] for item in items) / len(items)
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_dir": str(dataset_dir),
        "job_id": model_info.get("job_id"),
        "base_model": requested_base_model,
        "fine_tuned_model": fine_tuned_model,
        "evaluated_items": len(items),
        "base_average_score": round(base_average, 3),
        "fine_tuned_average_score": round(fine_tuned_average, 3),
        "conclusion": "fine_tuned_better_or_equal" if fine_tuned_average >= base_average else "base_better_on_heuristic",
        "provenance": provenance,
        "items": items,
    }
    _write_json(dataset_dir / "eval_result.json", result)
    (dataset_dir / "eval_result.md").write_text(_build_markdown(result), encoding="utf-8")
    print(f"PASS: eval completed. base={base_average:.3f}, fine_tuned={fine_tuned_average:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
