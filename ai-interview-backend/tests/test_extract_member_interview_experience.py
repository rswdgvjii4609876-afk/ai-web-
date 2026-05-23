import json
import hashlib
from pathlib import Path
from zipfile import ZipFile

from app.scripts.extract_member_interview_experience import (
    extract_member_interview_experience,
)
from app.scripts.import_member_knowledge_packages import build_import_plans


def _make_docx(path: Path, *, image_name: str = "image1.png") -> None:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>面试经验</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr(f"word/media/{image_name}", b"fake-image-bytes")


def test_extract_docx_images_writes_markdown_manifest_and_valid_package(tmp_path, monkeypatch):
    source = tmp_path / "raw"
    source.mkdir()
    _make_docx(source / "面试经历.docx")
    out_dir = tmp_path / "package"

    def fake_ocr(image_path, *, lang):
        return "请说明如何处理候选人失联？回答要点：多渠道触达，记录跟进节奏并复盘原因。", 88.0, "ocr_ok"

    monkeypatch.setattr(
        "app.scripts.extract_member_interview_experience._run_tesseract_ocr",
        fake_ocr,
    )

    manifest = extract_member_interview_experience(source, out_dir, package_date="2026-05-23")

    assert manifest["image_count"] == 1
    assert manifest["source_date"] == "2026-05-23"
    assert (out_dir / "source_images").is_dir()
    markdown = (out_dir / "extracted_interview_experience.md").read_text(encoding="utf-8")
    assert "![01_" in markdown
    assert "候选人失联" in markdown
    assert "2026-05-23 图片型面试经验抽取记录" in markdown
    assert "2026-05-19" not in markdown

    package_path = out_dir / "member_interview_experience_package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert package["version"] == "knowledge_package_v1"
    assert "2026-05-23" in package["description"]
    assert package["items"][0]["target_position"] == "人力资源专员"
    plans = build_import_plans([package_path])
    assert plans[0].enabled_experiences == 1


def test_extract_low_confidence_ocr_is_kept_for_review(tmp_path, monkeypatch):
    source = tmp_path / "raw"
    source.mkdir()
    _make_docx(source / "面试经历.docx")
    out_dir = tmp_path / "package"

    def fake_ocr(image_path, *, lang):
        return "运营活动复盘题：如何判断活动效果？", 12.0, "ocr_ok"

    monkeypatch.setattr(
        "app.scripts.extract_member_interview_experience._run_tesseract_ocr",
        fake_ocr,
    )

    extract_member_interview_experience(source, out_dir, min_confidence=45.0)

    manifest = json.loads((out_dir / "extraction_manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"][0]["audit_status"] == "待核验"
    assert manifest["records"][0]["entered_package"] is False
    package = json.loads((out_dir / "member_interview_experience_package.json").read_text(encoding="utf-8"))
    assert package["items"] == []


def test_extract_override_can_mark_image_as_rejected(tmp_path, monkeypatch):
    source = tmp_path / "raw"
    source.mkdir()
    _make_docx(source / "面试经历.docx")
    out_dir = tmp_path / "package"
    image_name = "01_doc01_image_001_673c4f8bc0.png"
    override = {
        image_name: {
            "ocr_text": "来源不清，不采用。",
            "target_position": "产品助理",
            "audit_status": "不采用",
            "experiences": [
                {
                    "target_position": "产品助理",
                    "question": "不采用样例",
                    "answer_points": "不应进入启用切片。",
                    "audit_status": "不采用",
                }
            ],
        }
    }

    def fake_ocr(image_path, *, lang):
        return "", None, "ocr_unavailable"

    monkeypatch.setattr(
        "app.scripts.extract_member_interview_experience._run_tesseract_ocr",
        fake_ocr,
    )

    # First run to discover deterministic extracted image name, then apply an override.
    extract_member_interview_experience(source, out_dir)
    actual_name = json.loads((out_dir / "extraction_manifest.json").read_text(encoding="utf-8"))["records"][0]["image_name"]
    (out_dir / "ocr_overrides.json").write_text(
        json.dumps({actual_name: next(iter(override.values()))}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    extract_member_interview_experience(source, out_dir)

    package_path = out_dir / "member_interview_experience_package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert package["items"] == []
    manifest = json.loads((out_dir / "extraction_manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"][0]["audit_status"] == "不采用"
    assert manifest["records"][0]["entered_package"] is False


def test_dry_run_counts_docx_media_without_writing_outputs(tmp_path):
    source = tmp_path / "raw"
    source.mkdir()
    docx_path = source / "面试经历.docx"
    with ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" />")
        archive.writestr("word/media/", b"")
        archive.writestr("word/media/image1.png", b"fake-image-1")
        archive.writestr("word/media/image2.jpeg", b"fake-image-2")
    out_dir = tmp_path / "package"

    manifest = extract_member_interview_experience(
        source,
        out_dir,
        package_date="2026-05-23",
        dry_run=True,
    )

    assert manifest["source_date"] == "2026-05-23"
    assert manifest["media_image_count"] == 2
    assert manifest["skipped_directory_entries"] == 1
    assert manifest["image_count"] == 2
    assert manifest["docx_files"] == [str(docx_path.resolve())]
    assert not out_dir.exists()


def test_extract_reuses_previous_visual_transcription_by_hash(tmp_path, monkeypatch):
    source = tmp_path / "raw"
    source.mkdir()
    _make_docx(source / "面试经历.docx")
    out_dir = tmp_path / "package"
    previous = tmp_path / "2026-05-22"
    previous.mkdir()
    digest = hashlib.sha256(b"fake-image-bytes").hexdigest()
    (previous / "extraction_manifest.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "sha256": digest,
                        "ocr_text": "产品助理面试题：如何做需求优先级排序？",
                        "cleaned_text": "产品助理面试题：如何做需求优先级排序？",
                        "ocr_confidence": None,
                        "target_position": "产品助理",
                        "audit_status": "可入库",
                        "experiences": [
                            {
                                "target_position": "产品助理",
                                "question": "如何做需求优先级排序？",
                                "answer_points": "结合用户价值、业务目标、实现成本和风险进行排序，并说明取舍。",
                                "audit_status": "可入库",
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def fake_ocr(image_path, *, lang):
        return "", None, "ocr_unavailable"

    monkeypatch.setattr(
        "app.scripts.extract_member_interview_experience._run_tesseract_ocr",
        fake_ocr,
    )

    manifest = extract_member_interview_experience(
        source,
        out_dir,
        package_date="2026-05-23",
        reuse_overrides_from=previous,
    )

    assert manifest["reused_hash_count"] == 1
    assert manifest["new_image_count"] == 0
    assert manifest["records"][0]["override_source"] == "hash_override"
    package = json.loads((out_dir / "member_interview_experience_package.json").read_text(encoding="utf-8"))
    assert package["items"][0]["target_position"] == "产品助理"
    assert package["items"][0]["interview_experiences"][0]["question"] == "如何做需求优先级排序？"
