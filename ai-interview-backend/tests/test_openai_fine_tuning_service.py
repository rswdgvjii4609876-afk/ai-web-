import json

import pytest

from app.services.client.openai_fine_tuning_service import (
    OpenAIFineTuningDataError,
    build_openai_fine_tuning_dataset,
    convert_internal_record_to_openai_chat,
    load_constructed_seed_records,
    write_openai_fine_tuning_bundle,
)


def make_record(index=1, *, consent=True, origin="real_authorized", pii=False, hallucination=False):
    metadata = {
        "target_position": "Python后端开发工程师",
        "quality_tier": "high",
        "is_high_quality": True,
        "has_hallucination": hallucination,
        "followup_worthy": True,
        "report_actionable": True,
        "data_contribution_consent": consent,
        "interview_id": index,
    }
    if origin == "constructed":
        metadata["sample_origin"] = "constructed"
        metadata["constructed_for"] = "unit_test"
        metadata["data_contribution_consent"] = False
    return {
        "schema_version": "ai-interview.fine-tuning-sample.v1",
        "task_type": "followup_generation",
        "instruction": "根据岗位画像和证据状态生成追问。",
        "input": {
            "target_position": "Python后端开发工程师",
            "ability_gap": "Redis 缓存设计",
            "evidence_status": "claimed_only",
            "question_reason": "缺少项目指标证据。",
            "evidence_summary": ["简历只写熟悉 Redis。"],
            "rag_context": ["岗位要求能说明缓存策略。"],
            "previous_question": "你如何使用 Redis？",
            "candidate_answer": "我用 Redis 缓存热点数据。" if not pii else "我用 Redis 缓存热点数据，邮箱：demo@example.com。",
            "feedback": "需要验证具体动作。",
            "report_gaps": ["缓存证据不足"],
            "report_training_priorities": ["补充命中率和一致性案例"],
        },
        "output": {
            "question": "请说明一个实际接口的缓存数据、过期策略、命中率变化和一致性处理。",
            "verification_target": "Redis 缓存设计能力",
            "expected_constraints": ["不得编造经历", "要求具体场景、行动和结果"],
        },
        "metadata": metadata,
    }


@pytest.mark.unit
def test_convert_authorized_real_record_to_openai_chat_jsonl_shape():
    upload_record, manifest = convert_internal_record_to_openai_chat(make_record())

    assert set(upload_record.keys()) == {"messages"}
    assert [message["role"] for message in upload_record["messages"]] == ["system", "user", "assistant"]
    assert "metadata" not in upload_record
    assistant_payload = json.loads(upload_record["messages"][-1]["content"])
    assert assistant_payload["question"].startswith("请说明一个实际接口")
    assert manifest["sample_origin"] == "real_authorized"
    assert manifest["data_contribution_consent"] is True


@pytest.mark.unit
def test_convert_rejects_unauthorized_pii_and_hallucination_samples():
    with pytest.raises(OpenAIFineTuningDataError, match="data_contribution_consent"):
        convert_internal_record_to_openai_chat(make_record(consent=False))
    with pytest.raises(OpenAIFineTuningDataError, match="direct personal identifier"):
        convert_internal_record_to_openai_chat(make_record(pii=True))
    with pytest.raises(OpenAIFineTuningDataError, match="hallucination"):
        convert_internal_record_to_openai_chat(make_record(hallucination=True))


@pytest.mark.unit
def test_constructed_samples_must_declare_origin_and_are_counted_separately():
    constructed = make_record(index=11, origin="constructed")
    upload_record, manifest = convert_internal_record_to_openai_chat(
        constructed,
        sample_origin="constructed",
    )

    assert upload_record["messages"][0]["role"] == "system"
    assert manifest["sample_origin"] == "constructed"
    assert manifest["data_contribution_consent"] is False

    malformed = make_record(index=12, consent=False)
    with pytest.raises(OpenAIFineTuningDataError, match="sample_origin=constructed"):
        convert_internal_record_to_openai_chat(malformed, sample_origin="constructed")


@pytest.mark.unit
def test_dataset_ready_requires_three_real_authorized_and_ten_train_samples():
    real_records = [make_record(index=index) for index in range(1, 4)]
    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 11)]

    bundle = build_openai_fine_tuning_dataset(real_records, constructed_records)
    summary = bundle["summary"]

    assert summary["ready_for_openai_job"] is True
    assert summary["counts"]["real_authorized_samples"] == 3
    assert summary["counts"]["constructed_samples"] == 7
    assert summary["counts"]["train_samples"] == 10
    assert summary["counts"]["validation_samples"] == 0

    constructed_only = build_openai_fine_tuning_dataset([], constructed_records + [make_record(index=99, origin="constructed")])
    assert constructed_only["summary"]["ready_for_openai_job"] is False
    assert "真实授权样本不足" in constructed_only["summary"]["blockers"][0]


@pytest.mark.unit
def test_write_bundle_outputs_upload_safe_jsonl_and_local_manifest(tmp_path):
    real_records = [make_record(index=index) for index in range(1, 4)]
    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 11)]
    bundle = build_openai_fine_tuning_dataset(real_records, constructed_records)

    paths = write_openai_fine_tuning_bundle(bundle, tmp_path)
    train_line = paths["train"].read_text(encoding="utf-8").splitlines()[0]
    manifest_line = paths["manifest"].read_text(encoding="utf-8").splitlines()[0]

    assert set(json.loads(train_line).keys()) == {"messages"}
    assert json.loads(manifest_line)["sample_origin"] in {"real_authorized", "constructed"}
    assert paths["summary"].exists()
    assert paths["readme"].exists()


@pytest.mark.unit
def test_constructed_seed_file_has_ten_marked_samples():
    records = load_constructed_seed_records()

    assert len(records) >= 10
    assert all((record.get("metadata") or {}).get("sample_origin") == "constructed" for record in records)
    positions = {(record.get("metadata") or {}).get("target_position") for record in records}
    assert {"Python后端开发工程师", "产品助理/产品经理实习生", "人力资源专员"} <= positions
