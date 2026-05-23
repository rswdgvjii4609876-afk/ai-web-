"""Extract image-heavy member interview experience documents into packages.

This script is intentionally file-only: it extracts DOCX text/images, runs OCR
when a local Tesseract binary is available, applies optional manual OCR/QA
overrides, and writes deployable ``knowledge_package_v1`` artifacts. It never
connects to the database.

Usage:
python -m app.scripts.extract_member_interview_experience --source-dir <raw-dir>
python -m app.scripts.extract_member_interview_experience --source-dir <raw-dir> --out-dir <package-dir>
python -m app.scripts.extract_member_interview_experience --source-dir <raw-dir> --dry-run
python -m app.scripts.extract_member_interview_experience --source-dir <raw-dir> --package-date 2026-05-23
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zipfile import ZipFile


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = APP_DIR / "data" / "knowledge_packages" / "member_submissions" / "2026-05-19"
PACKAGE_VERSION = "knowledge_package_v1"
MANIFEST_VERSION = "member_interview_experience_extraction_v1"
VALID_AUDIT_STATUSES = {"可入库", "仅参考", "待核验", "不采用"}
DEFAULT_PACKAGE_AUDIT_STATUSES = {"可入库", "仅参考"}
VALID_TARGET_POSITIONS = {
    "Python后端开发工程师",
    "Java后端开发工程师",
    "前端开发工程师",
    "算法工程师",
    "产品助理",
    "运营助理",
    "人力资源专员",
    "新媒体运营",
    "招聘助理",
    "行政管理助理",
}


@dataclass
class ImageRecord:
    source_docx: str
    image_index: int
    image_name: str
    image_path: str
    sha256: str
    byte_size: int
    ocr_status: str
    ocr_confidence: float | None = None
    ocr_text: str = ""
    cleaned_text: str = ""
    target_position: str = "待人工确认"
    audit_status: str = "待核验"
    notes: str = ""
    override_source: str = ""
    entered_package: bool = False
    needs_review: bool = True
    experiences: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class DocxMediaStats:
    docx_path: str
    media_image_count: int
    skipped_directory_entries: int


def _infer_package_date(out_dir: Path, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(out_dir))
    return match.group(0) if match else "unknown-date"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def _safe_stem(path: Path, index: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", path.stem).strip("_").lower()
    return slug or f"doc{index:02d}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_docx_text(path: Path) -> str:
    with ZipFile(path) as archive:
        try:
            xml = archive.read("word/document.xml")
        except KeyError:
            return ""
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        text = html.unescape("".join(parts)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs).strip()


def _copy_docx_images(
    path: Path,
    *,
    source_doc_index: int,
    images_dir: Path,
    write_files: bool = True,
) -> list[ImageRecord]:
    records: list[ImageRecord] = []
    with ZipFile(path) as archive:
        media_names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("word/media/") and not name.endswith("/")
        )
        doc_stem = _safe_stem(path, source_doc_index)
        for image_index, media_name in enumerate(media_names, start=1):
            data = archive.read(media_name)
            digest = _sha256_bytes(data)
            suffix = Path(media_name).suffix.lower() or ".bin"
            image_name = f"{source_doc_index:02d}_{doc_stem}_image_{image_index:03d}_{digest[:10]}{suffix}"
            target = images_dir / image_name
            if write_files:
                target.write_bytes(data)
            records.append(
                ImageRecord(
                    source_docx=str(path),
                    image_index=image_index,
                    image_name=image_name,
                    image_path=str(Path("source_images") / image_name).replace("\\", "/"),
                    sha256=digest,
                    byte_size=len(data),
                    ocr_status="pending",
                )
            )
    return records


def inspect_docx_media(path: Path) -> DocxMediaStats:
    with ZipFile(path) as archive:
        entries = [name for name in archive.namelist() if name.startswith("word/media/")]
        media_names = [name for name in entries if not name.endswith("/")]
        skipped = len(entries) - len(media_names)
    return DocxMediaStats(
        docx_path=str(path),
        media_image_count=len(media_names),
        skipped_directory_entries=skipped,
    )


def _preprocess_for_tesseract(image_path: Path, temp_dir: Path) -> Path:
    try:
        from PIL import Image, ImageEnhance, ImageFilter
    except Exception:
        return image_path
    try:
        image = Image.open(image_path).convert("L")
        width, height = image.size
        scale = 2 if max(width, height) < 1800 else 1
        if scale > 1:
            image = image.resize((width * scale, height * scale))
        image = ImageEnhance.Contrast(image).enhance(1.6)
        image = image.filter(ImageFilter.SHARPEN)
        out_path = temp_dir / f"{image_path.stem}_ocr.png"
        image.save(out_path)
        return out_path
    except Exception:
        return image_path


def _run_tesseract_ocr(image_path: Path, *, lang: str) -> tuple[str, float | None, str]:
    tesseract = shutil.which("tesseract")
    if not tesseract:
        return "", None, "ocr_unavailable"
    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        prepared = _preprocess_for_tesseract(image_path, temp_dir)
        output_base = temp_dir / "ocr_result"
        command = [tesseract, str(prepared), str(output_base), "-l", lang, "--psm", "6", "tsv"]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if result.returncode != 0:
            return "", None, "ocr_failed"
        tsv_path = output_base.with_suffix(".tsv")
        if not tsv_path.exists():
            return "", None, "ocr_failed"
        words: list[str] = []
        confidences: list[float] = []
        for line in tsv_path.read_text(encoding="utf-8", errors="ignore").splitlines()[1:]:
            cols = line.split("\t")
            if len(cols) < 12:
                continue
            text = cols[11].strip()
            if not text:
                continue
            words.append(text)
            try:
                conf = float(cols[10])
            except ValueError:
                continue
            if conf >= 0:
                confidences.append(conf)
        avg_conf = sum(confidences) / len(confidences) if confidences else None
        return _clean_text(" ".join(words)), avg_conf, "ocr_ok" if words else "ocr_empty"


def _load_overrides(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and "images" in payload:
        payload = payload["images"]
    if not isinstance(payload, dict):
        raise ValueError("OCR override file must be an object keyed by image_name")
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def _load_hash_overrides(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and "hashes" in payload:
        payload = payload["hashes"]
    if not isinstance(payload, dict):
        raise ValueError("Hash override file must be an object keyed by SHA256")
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def _hash_overrides_from_package_dir(package_dir: Path | None) -> dict[str, dict[str, Any]]:
    if not package_dir:
        return {}
    overrides: dict[str, dict[str, Any]] = {}
    images_dir = package_dir / "source_images"
    if images_dir.exists():
        for image_path in sorted(path for path in images_dir.iterdir() if path.is_file()):
            digest = _sha256_bytes(image_path.read_bytes())
            overrides[digest] = {
                "ocr_status": "reused_existing_image_by_hash",
                "audit_status": "待核验",
                "notes": f"matched existing image from {package_dir.name} by sha256",
                "experiences": [],
            }

    manifest_path = package_dir / "extraction_manifest.json"
    if not manifest_path.exists():
        return overrides
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return overrides

    for record in records:
        if not isinstance(record, dict):
            continue
        digest = _clean_text(record.get("sha256"))
        experiences = record.get("experiences")
        if not digest or not isinstance(experiences, list):
            continue
        if not experiences and digest in overrides:
            continue
        overrides[digest] = {
            "ocr_text": record.get("ocr_text", ""),
            "cleaned_text": record.get("cleaned_text", ""),
            "ocr_status": "reused_manual_visual_ocr_by_hash",
            "ocr_confidence": record.get("ocr_confidence"),
            "target_position": record.get("target_position"),
            "audit_status": record.get("audit_status"),
            "notes": f"reused from {package_dir.name} by sha256",
            "experiences": experiences,
        }
    return overrides


def _apply_override(record: ImageRecord, override: dict[str, Any]) -> None:
    if "ocr_text" in override:
        record.ocr_text = _clean_text(override.get("ocr_text"))
        record.cleaned_text = _clean_text(override.get("cleaned_text") or record.ocr_text)
        record.ocr_status = str(override.get("ocr_status") or "manual_visual_ocr")
        record.ocr_confidence = override.get("ocr_confidence")
    if override.get("target_position"):
        record.target_position = _clean_text(override["target_position"])
    if override.get("audit_status"):
        status = _clean_text(override["audit_status"])
        record.audit_status = status if status in VALID_AUDIT_STATUSES else "待核验"
    if override.get("notes"):
        record.notes = _clean_text(override["notes"])
    experiences = override.get("experiences")
    if isinstance(experiences, list):
        record.experiences = [item for item in experiences if isinstance(item, dict)]
    if override.get("override_source"):
        record.override_source = _clean_text(override["override_source"])


def _infer_target_position(text: str) -> str:
    normalized = _clean_text(text)
    if any(term in normalized for term in ("HR", "人力资源", "招聘", "候选人", "薪酬", "员工关系")):
        return "人力资源专员"
    if any(term in normalized for term in ("产品", "PRD", "需求", "原型", "用户", "指标")):
        return "产品助理"
    if any(term in normalized for term in ("运营", "活动", "转化", "留存", "社群")):
        return "运营助理"
    if any(term in normalized for term in ("新媒体", "内容", "公众号", "小红书", "短视频")):
        return "新媒体运营"
    return "待人工确认"


def _fallback_experience_from_text(record: ImageRecord) -> list[dict[str, Any]]:
    text = record.cleaned_text or record.ocr_text
    if not text or record.audit_status == "不采用":
        return []
    target_position = record.target_position if record.target_position != "待人工确认" else _infer_target_position(text)
    if target_position == "待人工确认":
        return []
    question = text[:120]
    if "？" in text:
        question = text.split("？", 1)[0] + "？"
    elif "?" in text:
        question = text.split("?", 1)[0] + "?"
    return [
        {
            "target_position": target_position,
            "question": _clean_text(question) or f"图片面经 {record.image_index}",
            "answer_points": _clean_text(text[:500]),
            "reflection": "由图片 OCR/视觉转写整理，需在面试中结合候选人真实项目继续追问，不得当作候选人经历。",
            "company_context": "成员提交图片型面试经验",
            "ability": "面试经验提炼",
            "difficulty": "待核验",
            "source": f"{Path(record.source_docx).name} / {record.image_name}",
            "audit_status": record.audit_status,
        }
    ]


def _normalize_experience(record: ImageRecord, item: dict[str, Any]) -> dict[str, Any] | None:
    question = _clean_text(item.get("question"))
    answer_points = _clean_text(item.get("answer_points"))
    target_position = _clean_text(item.get("target_position") or record.target_position)
    audit_status = _clean_text(item.get("audit_status") or record.audit_status or "待核验")
    if audit_status not in VALID_AUDIT_STATUSES:
        audit_status = "待核验"
    if not question or not answer_points or not target_position or target_position == "待人工确认":
        return None
    return {
        "target_position": target_position,
        "question": question,
        "answer_points": answer_points,
        "reflection": _clean_text(item.get("reflection"))
        or "由成员图片面经整理，正式使用前仍应结合岗位和候选人真实回答复核。",
        "company_context": _clean_text(item.get("company_context")) or "成员提交图片型面试经验",
        "ability": _clean_text(item.get("ability")) or "岗位面试经验",
        "difficulty": _clean_text(item.get("difficulty")) or "待核验",
        "source": _clean_text(item.get("source")) or f"{Path(record.source_docx).name} / {record.image_name}",
        "audit_status": audit_status,
    }


def _group_experiences(
    records: list[ImageRecord],
    *,
    package_audit_statuses: set[str],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        raw_items = record.experiences or _fallback_experience_from_text(record)
        for raw_item in raw_items:
            item = _normalize_experience(record, raw_item)
            if not item:
                continue
            if item["audit_status"] not in package_audit_statuses:
                continue
            key = (item["target_position"], item["question"], item["source"])
            if key in seen:
                continue
            seen.add(key)
            grouped.setdefault(item["target_position"], []).append(
                {k: v for k, v in item.items() if k != "target_position"}
            )
    return grouped


def _sections_for_position(target_position: str) -> dict[str, str]:
    return {
        "job_requirements": (
            f"本批资料仅补充 {target_position} 的图片型面试经验，不替代标准岗位要求。"
            "导入后应与原有标准岗位画像合并使用。"
        ),
        "ability_model": (
            "能力模型沿用标准岗位画像；本批面经主要用于补充真实问题、回答要点、复盘反思、"
            "公司/场景、能力项和难度标签。"
        ),
        "followup_rules": (
            "图片面经只作为岗位追问方向和回答评价参考，不能写成候选人真实经历。"
            "遇到 OCR/视觉转写为待核验的内容，应优先追问候选人自己的项目、职责、行动和结果。"
        ),
    }


def build_package(
    records: list[ImageRecord],
    *,
    package_date: str,
    package_audit_statuses: set[str],
) -> dict[str, Any]:
    grouped = _group_experiences(records, package_audit_statuses=package_audit_statuses)
    included_identities = {
        (
            target_position,
            _clean_text(experience.get("question")),
            _clean_text(experience.get("source")),
        )
        for target_position, experiences in grouped.items()
        for experience in experiences
    }
    for record in records:
        raw_items = record.experiences or _fallback_experience_from_text(record)
        record.entered_package = any(
            (
                _clean_text(item.get("target_position") or record.target_position),
                _clean_text(item.get("question")),
                _clean_text(item.get("source")) or f"{Path(record.source_docx).name} / {record.image_name}",
            )
            in included_identities
            for item in raw_items
            if isinstance(item, dict)
        )
        record.needs_review = not record.entered_package
    items = []
    for target_position in sorted(grouped):
        if target_position not in VALID_TARGET_POSITIONS:
            continue
        experiences = grouped[target_position]
        if not experiences:
            continue
        items.append(
            {
                "title": f"{target_position}图片面试经验补充包",
                "target_position": target_position,
                "sections": _sections_for_position(target_position),
                "interview_experiences": experiences,
                "focus_points": "图片面经补充：真实问题、参考回答、追问方向、复盘反思和来源审核。",
                "interviewer_prompt": (
                    "使用图片面经时只校准岗位追问方向，不得把资料内容当作候选人真实经历；"
                    "对待核验资料需继续追问证据。"
                ),
            }
        )
    return {
        "version": PACKAGE_VERSION,
        "description": f"{package_date} 根据成员图片型面试经验 DOCX 抽取、OCR/视觉转写并整理的候选入库包。",
        "source_materials": sorted({record.source_docx for record in records}),
        "items": items,
        "review_notes": [
            "图片已解包并保留来源 hash。",
            "OCR/视觉转写内容只作为岗位面经知识，不作为候选人真实经历。",
            "待人工确认岗位的图片不会进入 package items。",
        ],
    }


def render_extracted_markdown(records: list[ImageRecord], doc_texts: dict[str, str], *, package_date: str) -> str:
    lines = [
        f"# {package_date} 图片型面试经验抽取记录",
        "",
        "本文件由 `extract_member_interview_experience` 生成。图片内容必须经过 OCR/视觉转写后，才能进入结构化知识包。",
        "",
        "## DOCX 正文抽取",
        "",
    ]
    for source, text in doc_texts.items():
        lines.extend(
            [
                f"### {Path(source).name}",
                "",
                text or "（无可用正文，主要内容为图片）",
                "",
            ]
        )
    lines.extend(["## 图片与 OCR/转写结果", ""])
    for record in records:
        lines.extend(
            [
                f"### 图片 {record.image_index}: {record.image_name}",
                "",
                f"- 来源：`{record.source_docx}`",
                f"- SHA256：`{record.sha256}`",
                f"- OCR 状态：`{record.ocr_status}`",
                f"- OCR 置信度：`{record.ocr_confidence if record.ocr_confidence is not None else ''}`",
                f"- 目标岗位：{record.target_position}",
                f"- 审核状态：{record.audit_status}",
                f"- 复用来源：{record.override_source}",
                f"- 是否进入 package：{record.entered_package}",
                f"- 是否需要复核：{record.needs_review}",
                f"- 图片：![{record.image_name}]({record.image_path})",
                "",
                "#### OCR 原文",
                "",
                record.ocr_text or "（无 OCR 原文）",
                "",
                "#### 清洗后文本",
                "",
                record.cleaned_text or "（无清洗文本）",
                "",
                "#### 结构化候选问答",
                "",
            ]
        )
        items = record.experiences or _fallback_experience_from_text(record)
        if not items:
            lines.append("- 暂无可入库结构化问答。")
        for item in items:
            lines.extend(
                [
                    f"- 岗位：{_clean_text(item.get('target_position') or record.target_position)}",
                    f"- 问题：{_clean_text(item.get('question'))}",
                    f"- 回答要点：{_clean_text(item.get('answer_points'))}",
                    f"- 复盘：{_clean_text(item.get('reflection'))}",
                    f"- 能力：{_clean_text(item.get('ability'))}",
                    f"- 来源：{_clean_text(item.get('source')) or record.image_name}",
                    "",
                ]
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_new_images_review(records: list[ImageRecord], *, package_date: str) -> str:
    new_records = [record for record in records if not record.override_source]
    lines = [
        f"# {package_date} 新增图片复核清单",
        "",
        "本文件只列出未通过 hash 复用旧批次转写的新增图片。新增图片默认需要人工/LLM 视觉复核后再进入结构化知识包。",
        "",
        f"- 新增图片数：`{len(new_records)}`",
        "",
    ]
    for record in new_records:
        lines.extend(
            [
                f"## 图片 {record.image_index}: {record.image_name}",
                "",
                f"- 来源：`{record.source_docx}`",
                f"- SHA256：`{record.sha256}`",
                f"- OCR 状态：`{record.ocr_status}`",
                f"- OCR 置信度：`{record.ocr_confidence if record.ocr_confidence is not None else ''}`",
                f"- 当前岗位：{record.target_position}",
                f"- 当前审核状态：{record.audit_status}",
                f"- 是否进入 package：{record.entered_package}",
                f"- 图片：![{record.image_name}](source_images/{record.image_name})",
                "",
                "### 待复核项",
                "",
                "- 目标岗位：",
                "- 真实问题：",
                "- 参考回答要点：",
                "- 考察能力：",
                "- 难度：",
                "- 审核状态：",
                "",
                "### OCR/清洗文本",
                "",
                record.cleaned_text or record.ocr_text or "（无可用 OCR 文本）",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_preview(package: dict[str, Any], *, package_date: str) -> str:
    lines = [
        f"# {package_date} 成员图片面试经验入库预览",
        "",
        f"- version: `{package.get('version')}`",
        f"- items: `{len(package.get('items') or [])}`",
        "",
    ]
    for item in package.get("items") or []:
        lines.extend(
            [
                f"## {item['target_position']}",
                "",
                f"- 标题：{item['title']}",
                f"- 面经数：{len(item.get('interview_experiences') or [])}",
                "",
            ]
        )
        for index, exp in enumerate(item.get("interview_experiences") or [], start=1):
            lines.extend(
                [
                    f"### 面经 {index}：{exp.get('question')}",
                    "",
                    f"- 参考回答要点：{exp.get('answer_points')}",
                    f"- 复盘反思：{exp.get('reflection')}",
                    f"- 公司/场景：{exp.get('company_context')}",
                    f"- 考察能力：{exp.get('ability')}",
                    f"- 难度：{exp.get('difficulty')}",
                    f"- 来源说明：{exp.get('source')}",
                    f"- 审核状态：{exp.get('audit_status')}",
                    "",
                ]
            )
    return "\n".join(lines).strip() + "\n"


def render_readme(package_date: str) -> str:
    compact_date = package_date.replace("-", "")
    return f"""# {package_date} 图片面试经验候选入库包

本目录保存从成员 DOCX 图片型面经中抽取、OCR/视觉转写并结构化后的候选入库包。

## 文件说明

- `source_images/`：DOCX 解包图片。
- `extracted_interview_experience.md`：图片引用、OCR 原文、清洗文本和候选问答。
- `new_images_review.md`：未按 hash 复用旧批次转写的新增图片复核清单。
- `member_interview_experience_package.json`：`knowledge_package_v1` 正式候选包。
- `member_interview_experience_preview.md`：人工预览。
- `extraction_manifest.json`：来源、hash、OCR 状态、岗位映射和审核状态。
- `ocr_overrides.json`：当本地 OCR 不可用或低置信时的人工视觉转写/复核覆盖。

## 入库命令

```bash
cd /opt/apps/ai-interview
./scripts/import_member_knowledge_server.sh --package-date {package_date}
./scripts/import_member_knowledge_server.sh --package-date {package_date} --execute
./scripts/import_member_knowledge_server.sh --package-date {package_date} --verify-only
```

日志路径：`ai-interview-backend/logs/member_knowledge_imports/{compact_date}_<mode>_<timestamp>.log`。

## 边界

- 图片内容只作为岗位面经知识和追问方向，不是候选人真实经历。
- `不采用` 资料不生成启用切片。
- `待核验` 资料只保留在 Markdown/manifest，默认不进入正式 package；人工确认后再补入。
- `可入库` 可进入标准岗位画像；`仅参考` 可进入低优先级参考切片。
"""


def extract_member_interview_experience(
    source_dir: Path,
    out_dir: Path,
    *,
    package_date: str | None = None,
    ocr_lang: str = "chi_sim+eng",
    min_confidence: float = 45.0,
    package_audit_statuses: set[str] | None = None,
    dry_run: bool = False,
    overrides_path: Path | None = None,
    hash_overrides_path: Path | None = None,
    reuse_overrides_from: Path | None = None,
) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    out_dir = out_dir.resolve()
    package_date = _infer_package_date(out_dir, package_date)
    package_audit_statuses = package_audit_statuses or set(DEFAULT_PACKAGE_AUDIT_STATUSES)
    images_dir = out_dir / "source_images"
    docx_paths = sorted(source_dir.rglob("*.docx"), key=lambda path: str(path))
    if not docx_paths:
        raise FileNotFoundError(f"No DOCX files found under {source_dir}")

    records: list[ImageRecord] = []
    doc_texts: dict[str, str] = {}
    media_stats = [inspect_docx_media(path) for path in docx_paths]
    if not dry_run:
        images_dir.mkdir(parents=True, exist_ok=True)
    for source_doc_index, path in enumerate(docx_paths, start=1):
        doc_texts[str(path)] = extract_docx_text(path)
        records.extend(
            _copy_docx_images(
                path,
                source_doc_index=source_doc_index,
                images_dir=images_dir,
                write_files=not dry_run,
            )
        )

    overrides = _load_overrides(overrides_path or (out_dir / "ocr_overrides.json"))
    hash_overrides = _hash_overrides_from_package_dir(reuse_overrides_from)
    hash_overrides.update(_load_hash_overrides(hash_overrides_path or (out_dir / "hash_overrides.json")))
    for record in records:
        if dry_run:
            record.ocr_status = "dry_run_not_ocr"
        else:
            image_abs = out_dir / record.image_path
            ocr_text, confidence, status = _run_tesseract_ocr(image_abs, lang=ocr_lang)
            record.ocr_text = ocr_text
            record.cleaned_text = ocr_text
            record.ocr_confidence = confidence
            record.ocr_status = status
            if status == "ocr_ok" and confidence is not None and confidence >= min_confidence:
                record.audit_status = "可入库"
            elif confidence is not None and confidence < min_confidence:
                record.audit_status = "待核验"
            if status in {"ocr_empty", "ocr_failed", "ocr_unavailable"}:
                record.audit_status = "待核验"
        if record.sha256 in hash_overrides:
            hash_override = dict(hash_overrides[record.sha256])
            hash_override.setdefault("override_source", "hash_override")
            _apply_override(record, hash_override)
        if record.image_name in overrides:
            _apply_override(record, overrides[record.image_name])
        if record.target_position == "待人工确认":
            record.target_position = _infer_target_position(record.cleaned_text or record.ocr_text)

    package = build_package(
        records,
        package_date=package_date,
        package_audit_statuses=package_audit_statuses,
    )
    manifest = {
        "version": MANIFEST_VERSION,
        "source_date": package_date,
        "source_dir": str(source_dir),
        "out_dir": str(out_dir),
        "docx_files": [str(path) for path in docx_paths],
        "docx_media_stats": [stats.__dict__ for stats in media_stats],
        "media_image_count": sum(stats.media_image_count for stats in media_stats),
        "skipped_directory_entries": sum(stats.skipped_directory_entries for stats in media_stats),
        "image_count": len(records),
        "reused_hash_count": sum(1 for record in records if record.override_source),
        "new_image_count": sum(1 for record in records if not record.override_source),
        "entered_package_count": sum(1 for record in records if record.entered_package),
        "needs_review_count": sum(1 for record in records if record.needs_review),
        "package_audit_statuses": sorted(package_audit_statuses),
        "package_item_count": len(package.get("items") or []),
        "records": [record.__dict__ for record in records],
    }

    if dry_run:
        return manifest

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "extraction_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "extracted_interview_experience.md").write_text(
            render_extracted_markdown(records, doc_texts, package_date=package_date),
            encoding="utf-8",
        )
        (out_dir / "new_images_review.md").write_text(
            render_new_images_review(records, package_date=package_date),
            encoding="utf-8",
        )
        (out_dir / "member_interview_experience_package.json").write_text(
            json.dumps(package, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "member_interview_experience_preview.md").write_text(
            render_preview(package, package_date=package_date),
            encoding="utf-8",
        )
        (out_dir / "README.md").write_text(render_readme(package_date), encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract image-heavy member interview experience DOCX files.")
    parser.add_argument("--source-dir", required=True, help="Raw member material directory.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output package directory.")
    parser.add_argument("--package-date", help="Batch label used in generated Markdown, manifest, README and package.")
    parser.add_argument("--ocr-lang", default="chi_sim+eng", help="Tesseract language expression.")
    parser.add_argument("--min-confidence", type=float, default=45.0, help="Confidence threshold for review flagging.")
    parser.add_argument("--ocr-overrides", help="Optional JSON override keyed by extracted image file name.")
    parser.add_argument("--hash-overrides", help="Optional JSON override keyed by image SHA256.")
    parser.add_argument(
        "--reuse-overrides-from",
        help="Existing package directory whose extraction_manifest.json is used for hash-based reuse.",
    )
    parser.add_argument(
        "--package-audit-statuses",
        default="可入库,仅参考",
        help="Comma-separated audit statuses allowed into package items.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Inspect DOCX files without writing outputs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = extract_member_interview_experience(
        Path(args.source_dir),
        Path(args.out_dir),
        package_date=args.package_date,
        ocr_lang=args.ocr_lang,
        min_confidence=args.min_confidence,
        package_audit_statuses={
            item.strip()
            for item in str(args.package_audit_statuses).split(",")
            if item.strip()
        },
        dry_run=args.dry_run,
        overrides_path=Path(args.ocr_overrides) if args.ocr_overrides else None,
        hash_overrides_path=Path(args.hash_overrides) if args.hash_overrides else None,
        reuse_overrides_from=Path(args.reuse_overrides_from) if args.reuse_overrides_from else None,
    )
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in (
                    "version",
                    "source_date",
                    "source_dir",
                    "out_dir",
                    "media_image_count",
                    "skipped_directory_entries",
                    "image_count",
                    "reused_hash_count",
                    "new_image_count",
                    "entered_package_count",
                    "package_item_count",
                )
                if k in manifest
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
