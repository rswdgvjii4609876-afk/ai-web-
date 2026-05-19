import asyncio
import json

import pytest

from app.services.client.openai_fine_tuning_service import (
    OpenAIFineTuningDataError,
    DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES,
    assert_job_record_matches,
    build_openai_fine_tuning_dataset,
    convert_internal_record_to_openai_chat,
    load_json_records,
    load_jsonl_records,
    load_constructed_seed_records,
    resolve_fine_tuned_model_for_eval,
    validate_official_openai_base_url,
    validate_openai_fine_tuning_dataset_dir,
    validate_real_authorized_records,
    write_openai_fine_tuning_bundle,
    _validate_upload_record,
)


def make_record(
    index=1,
    *,
    consent=True,
    origin="real_authorized",
    pii=False,
    hallucination=False,
    reviewed=True,
    quality=True,
):
    metadata = {
        "target_position": "Python后端开发工程师",
        "quality_tier": "high",
        "is_high_quality": quality,
        "has_hallucination": hallucination,
        "followup_worthy": quality,
        "report_actionable": quality,
        "review_status": "reviewed" if reviewed else "pending",
        "reviewed_at": "2026-05-17T00:00:00+00:00" if reviewed else None,
        "reviewer_present": bool(reviewed),
        "reviewer_hash": f"reviewer-hash-{index}" if reviewed else "",
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
            "previous_question": f"你如何使用 Redis？case={index}",
            "candidate_answer": f"我用 Redis 缓存热点数据。case={index}" if not pii else "我用 Redis 缓存热点数据，邮箱：demo@example.com。",
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
    assert manifest["reviewer_present"] is True
    assert manifest["reviewer_hash"]


@pytest.mark.unit
def test_convert_rejects_unauthorized_pii_and_hallucination_samples():
    with pytest.raises(OpenAIFineTuningDataError, match="data_contribution_consent"):
        convert_internal_record_to_openai_chat(make_record(consent=False))
    with pytest.raises(OpenAIFineTuningDataError, match="direct personal identifier"):
        convert_internal_record_to_openai_chat(make_record(pii=True))
    with pytest.raises(OpenAIFineTuningDataError, match="hallucination"):
        convert_internal_record_to_openai_chat(make_record(hallucination=True))


@pytest.mark.unit
def test_convert_rejects_formatted_phone_and_resume_filename_pii():
    formatted_phone = make_record()
    formatted_phone["input"]["candidate_answer"] = "我的联系方式是 +86 138-1234-5678。"
    with pytest.raises(OpenAIFineTuningDataError, match="direct personal identifier"):
        convert_internal_record_to_openai_chat(formatted_phone)

    resume_filename = make_record()
    resume_filename["input"]["evidence_summary"] = ["附件来自 zhangsan_resume.pdf"]
    with pytest.raises(OpenAIFineTuningDataError, match="direct personal identifier"):
        convert_internal_record_to_openai_chat(resume_filename)


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
    real_records = [make_record(index=index) for index in range(1, 16)]
    constructed_records = []

    bundle = build_openai_fine_tuning_dataset(real_records, constructed_records)
    summary = bundle["summary"]

    assert summary["ready_for_openai_job"] is True
    assert summary["counts"]["real_authorized_samples"] == 15
    assert summary["counts"]["constructed_samples"] == 0
    assert summary["counts"]["train_samples"] == 10
    assert summary["counts"]["validation_samples"] == 5
    assert summary["counts"]["validation_real_authorized_samples"] == 5

    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 11)]
    mixed = build_openai_fine_tuning_dataset(real_records[:3], constructed_records)
    assert mixed["summary"]["ready_for_openai_job"] is False
    assert any("constructed samples" in item for item in mixed["summary"]["blockers"])
    constructed_only = build_openai_fine_tuning_dataset([], constructed_records + [make_record(index=99, origin="constructed")])
    assert constructed_only["summary"]["ready_for_openai_job"] is False
    assert "真实授权样本不足" in constructed_only["summary"]["blockers"][0]


@pytest.mark.unit
def test_write_bundle_outputs_upload_safe_jsonl_and_local_manifest(tmp_path):
    real_records = [make_record(index=index) for index in range(1, 16)]
    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 11)]
    bundle = build_openai_fine_tuning_dataset(real_records, [])

    paths = write_openai_fine_tuning_bundle(bundle, tmp_path)
    train_line = paths["train"].read_text(encoding="utf-8").splitlines()[0]
    manifest_line = paths["manifest"].read_text(encoding="utf-8").splitlines()[0]

    assert set(json.loads(train_line).keys()) == {"messages"}
    assert json.loads(manifest_line)["sample_origin"] in {"real_authorized", "constructed"}
    assert paths["summary"].exists()
    assert paths["readme"].exists()


@pytest.mark.unit
def test_real_records_require_manual_review_quality_and_true_origin():
    with pytest.raises(OpenAIFineTuningDataError, match="review_status=reviewed"):
        convert_internal_record_to_openai_chat(make_record(reviewed=False))
    with pytest.raises(OpenAIFineTuningDataError, match="quality signal"):
        convert_internal_record_to_openai_chat(make_record(quality=False))
    missing_reviewer = make_record()
    missing_reviewer["metadata"]["reviewer_hash"] = ""
    with pytest.raises(OpenAIFineTuningDataError, match="reviewer_hash"):
        convert_internal_record_to_openai_chat(missing_reviewer)

    masquerading = make_record()
    masquerading["metadata"]["sample_origin"] = "constructed"
    with pytest.raises(OpenAIFineTuningDataError, match="must not be marked as constructed"):
        validate_real_authorized_records([masquerading])


@pytest.mark.unit
def test_preflight_validates_jsonl_manifest_hashes_and_counts(tmp_path):
    real_records = [make_record(index=index) for index in range(1, 16)]
    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 16)]
    bundle = build_openai_fine_tuning_dataset(real_records, [])
    write_openai_fine_tuning_bundle(bundle, tmp_path)

    preflight = validate_openai_fine_tuning_dataset_dir(tmp_path, require_ready=True, require_validation=True)
    assert preflight["dataset_fingerprint"]["train_records"] == 10
    assert preflight["dataset_fingerprint"]["validation_records"] == 5

    train_path = tmp_path / "train_openai.jsonl"
    first, *rest = train_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(first)
    tampered["messages"][-1]["content"] = json.dumps({"question": "tampered"}, ensure_ascii=False)
    train_path.write_text("\n".join([json.dumps(tampered, ensure_ascii=False), *rest]) + "\n", encoding="utf-8")

    with pytest.raises(OpenAIFineTuningDataError, match="sample_hash|dataset_fingerprint"):
        validate_openai_fine_tuning_dataset_dir(tmp_path, require_ready=True)


@pytest.mark.unit
def test_preflight_does_not_allow_lowering_default_training_gate(tmp_path):
    constructed_records = [make_record(index=index, origin="constructed") for index in range(1, 11)]
    bundle = build_openai_fine_tuning_dataset(
        [],
        constructed_records,
        min_real_authorized_samples=0,
        min_training_samples=1,
    )
    assert bundle["summary"]["ready_for_openai_job"] is False
    write_openai_fine_tuning_bundle(bundle, tmp_path)

    with pytest.raises(OpenAIFineTuningDataError, match=f"0 < {DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES}"):
        validate_openai_fine_tuning_dataset_dir(tmp_path, require_ready=True)


@pytest.mark.unit
def test_preflight_rejects_pii_in_upload_jsonl(tmp_path):
    real_records = [make_record(index=index) for index in range(1, 16)]
    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 11)]
    bundle = build_openai_fine_tuning_dataset(real_records, [])
    write_openai_fine_tuning_bundle(bundle, tmp_path)

    train_path = tmp_path / "train_openai.jsonl"
    first, *rest = train_path.read_text(encoding="utf-8").splitlines()
    tainted = json.loads(first)
    tainted["messages"][1]["content"] += " email: leaked@example.com"
    train_path.write_text("\n".join([json.dumps(tainted, ensure_ascii=False), *rest]) + "\n", encoding="utf-8")

    with pytest.raises(OpenAIFineTuningDataError, match="personal identifier"):
        validate_openai_fine_tuning_dataset_dir(tmp_path, require_ready=True)


@pytest.mark.unit
def test_jsonl_loader_rejects_non_object_lines():
    with pytest.raises(OpenAIFineTuningDataError, match="expected object"):
        load_jsonl_records("[1, 2, 3]\n")


@pytest.mark.unit
def test_json_loader_rejects_non_object_items(tmp_path):
    path = tmp_path / "samples.json"
    path.write_text(json.dumps([make_record(), "bad-item"], ensure_ascii=False), encoding="utf-8")

    with pytest.raises(OpenAIFineTuningDataError, match="expected object"):
        load_json_records(path)

    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(json.dumps({"items": [make_record(), 3]}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(OpenAIFineTuningDataError, match="expected object"):
        load_json_records(wrapped)


@pytest.mark.unit
def test_upload_record_requires_assistant_final_message():
    upload_record, _ = convert_internal_record_to_openai_chat(make_record())
    malformed = {"messages": [*upload_record["messages"], {"role": "user", "content": "extra"}]}

    with pytest.raises(OpenAIFineTuningDataError, match="final message must be assistant"):
        _validate_upload_record(malformed, label="record")


@pytest.mark.unit
def test_official_base_url_gate():
    assert validate_official_openai_base_url("https://api.openai.com/v1/") == "https://api.openai.com/v1"
    with pytest.raises(OpenAIFineTuningDataError, match="official OpenAI base_url"):
        validate_official_openai_base_url("https://relay.example.com/v1")


@pytest.mark.unit
def test_job_record_and_status_must_match_dataset_job_id(tmp_path):
    record = {
        "job_id": "ftjob_123",
        "fine_tuning_job": {"id": "ftjob_123", "status": "running"},
    }
    (tmp_path / "job_record.json").write_text(json.dumps(record), encoding="utf-8")

    _, job_id = assert_job_record_matches(tmp_path, "ftjob_123")
    assert job_id == "ftjob_123"
    with pytest.raises(OpenAIFineTuningDataError, match="does not match"):
        assert_job_record_matches(tmp_path, "ftjob_other")

    status = {
        "job_id": "ftjob_123",
        "fine_tuning_job": {
            "id": "ftjob_123",
            "status": "succeeded",
            "fine_tuned_model": "ft:gpt:test",
        },
    }
    (tmp_path / "job_status.json").write_text(json.dumps(status), encoding="utf-8")
    model_info = resolve_fine_tuned_model_for_eval(tmp_path, requested_job_id="ftjob_123")
    assert model_info["fine_tuned_model"] == "ft:gpt:test"

    status["job_id"] = "ftjob_other"
    (tmp_path / "job_status.json").write_text(json.dumps(status), encoding="utf-8")
    with pytest.raises(OpenAIFineTuningDataError, match="job id does not match"):
        resolve_fine_tuned_model_for_eval(tmp_path, requested_job_id="ftjob_123")


@pytest.mark.unit
def test_job_record_must_match_current_dataset_fingerprint(tmp_path):
    real_records = [make_record(index=index) for index in range(1, 16)]
    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 11)]
    bundle = build_openai_fine_tuning_dataset(real_records, [])
    write_openai_fine_tuning_bundle(bundle, tmp_path)
    preflight = validate_openai_fine_tuning_dataset_dir(tmp_path, require_ready=True)
    fingerprint = {**preflight["dataset_fingerprint"], "train_sha256": "bad"}
    (tmp_path / "job_record.json").write_text(
        json.dumps(
            {
                "job_id": "ftjob_123",
                "dataset_fingerprint": fingerprint,
                "fine_tuning_job": {"id": "ftjob_123"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(OpenAIFineTuningDataError, match="dataset_fingerprint"):
        assert_job_record_matches(tmp_path, "ftjob_123", preflight=preflight)


@pytest.mark.unit
def test_job_status_provenance_must_match_current_dataset_fingerprint(tmp_path):
    real_records = [make_record(index=index) for index in range(1, 16)]
    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 11)]
    bundle = build_openai_fine_tuning_dataset(real_records, [])
    write_openai_fine_tuning_bundle(bundle, tmp_path)
    preflight = validate_openai_fine_tuning_dataset_dir(tmp_path, require_ready=True)
    (tmp_path / "job_record.json").write_text(
        json.dumps(
            {
                "job_id": "ftjob_123",
                "dataset_fingerprint": preflight["dataset_fingerprint"],
                "fine_tuning_job": {"id": "ftjob_123"},
            }
        ),
        encoding="utf-8",
    )
    bad_fingerprint = {**preflight["dataset_fingerprint"], "manifest_sha256": "bad"}
    (tmp_path / "job_status.json").write_text(
        json.dumps(
            {
                "job_id": "ftjob_123",
                "provenance": {"dataset_fingerprint": bad_fingerprint},
                "fine_tuning_job": {
                    "id": "ftjob_123",
                    "status": "succeeded",
                    "fine_tuned_model": "ft:gpt:test",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(OpenAIFineTuningDataError, match="job_status.json provenance"):
        resolve_fine_tuned_model_for_eval(tmp_path, requested_job_id="ftjob_123", preflight=preflight)


@pytest.mark.unit
def test_create_job_dry_run_is_idempotent_unless_forced(tmp_path, monkeypatch):
    from app.scripts import create_openai_fine_tuning_job as create_script

    real_records = [make_record(index=index) for index in range(1, 16)]
    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 11)]
    bundle = build_openai_fine_tuning_dataset(real_records, [])
    write_openai_fine_tuning_bundle(bundle, tmp_path)
    (tmp_path / "job_record.json").write_text(
        json.dumps({"job_id": "ftjob_existing", "fine_tuning_job": {"id": "ftjob_existing"}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(
        "sys.argv",
        ["create", "--dry-run", "--dataset-dir", str(tmp_path), "--model", "gpt-test"],
    )
    with pytest.raises(SystemExit, match="job_record.json already exists"):
        create_script.main()

    monkeypatch.setattr(
        "sys.argv",
        ["create", "--dry-run", "--force-new-job", "--dataset-dir", str(tmp_path), "--model", "gpt-test"],
    )
    assert create_script.main() == 0
    preflight = json.loads((tmp_path / "job_preflight.json").read_text(encoding="utf-8"))
    assert preflight["previous_job_id"] == "ftjob_existing"
    assert preflight["previous_job_record_path"].endswith("job_record.json")


@pytest.mark.unit
def test_eval_rejects_base_model_mismatch_without_explicit_override(tmp_path, monkeypatch):
    from app.scripts import run_fine_tuning_eval as eval_script

    real_records = [make_record(index=index) for index in range(1, 16)]
    constructed_records = [make_record(index=index, origin="constructed") for index in range(4, 16)]
    bundle = build_openai_fine_tuning_dataset(real_records, [])
    write_openai_fine_tuning_bundle(bundle, tmp_path)
    preflight = validate_openai_fine_tuning_dataset_dir(tmp_path, require_ready=True, require_validation=True)
    (tmp_path / "job_record.json").write_text(
        json.dumps(
            {
                "job_id": "ftjob_123",
                "base_model": "gpt-recorded",
                "dataset_fingerprint": preflight["dataset_fingerprint"],
                "fine_tuning_job": {"id": "ftjob_123"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(
        "sys.argv",
        ["eval", "--dry-run", "--dataset-dir", str(tmp_path), "--base-model", "gpt-other"],
    )
    with pytest.raises(SystemExit, match="base-model does not match"):
        eval_script.main()


@pytest.mark.unit
def test_prepare_dataset_rejects_untrusted_real_jsonl(tmp_path, monkeypatch):
    from app.scripts import prepare_openai_fine_tuning_dataset as prepare_script

    real_jsonl = tmp_path / "fine_tuning_sft.jsonl"
    real_jsonl.write_text(json.dumps(make_record(), ensure_ascii=False) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "prepare",
            "--dry-run",
            "--skip-db",
            "--real-jsonl",
            str(real_jsonl),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )

    with pytest.raises(SystemExit, match="--real-jsonl is disabled"):
        asyncio.run(prepare_script.main())


@pytest.mark.unit
def test_constructed_seed_file_has_ten_marked_samples():
    records = load_constructed_seed_records()

    assert len(records) >= 10
    assert all((record.get("metadata") or {}).get("sample_origin") == "constructed" for record in records)
    positions = {(record.get("metadata") or {}).get("target_position") for record in records}
    assert {"Python后端开发工程师", "产品助理/产品经理实习生", "人力资源专员"} <= positions
