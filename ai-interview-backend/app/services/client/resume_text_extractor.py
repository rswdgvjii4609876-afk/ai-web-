from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class ResumeTextExtractor:
    """Extract resume text from PDF files with diagnostics and OCR fallback hooks."""

    VERSION = "resume_text_extraction_v1"
    LOW_CHAR_THRESHOLD = 120

    SECTION_TERMS = {
        "education": ("教育", "学历", "学校", "大学", "学院", "bachelor", "master", "education"),
        "projects": ("项目", "project", "作品", "经历"),
        "skills": ("技能", "技术", "skill", "python", "java", "sql", "redis", "fastapi"),
        "experience": ("实习", "工作", "experience", "intern", "employment"),
        "awards": ("获奖", "奖项", "荣誉", "award", "honor"),
        "campus_experience": ("校园", "社团", "学生会", "志愿", "活动"),
    }

    @classmethod
    def extract(cls, file_path: str | Path, *, enable_ocr: bool = False) -> dict[str, Any]:
        path = Path(file_path)
        methods = [
            cls._extract_with_pdfplumber(path),
            cls._extract_with_pypdf(path),
        ]
        best = cls._choose_best(methods)
        low_reasons = cls._low_quality_reasons(best)
        ocr_used = False

        if low_reasons and enable_ocr:
            ocr_result = cls._extract_with_ocr(path)
            methods.append(ocr_result)
            if ocr_result.get("char_count", 0) > best.get("char_count", 0):
                best = ocr_result
                ocr_used = bool(ocr_result.get("text"))
                low_reasons = cls._low_quality_reasons(best)

        diagnostics = {
            "version": cls.VERSION,
            "file_name": path.name,
            "page_count": max((item.get("page_count") or 0 for item in methods), default=0),
            "best_method": best.get("method"),
            "char_count": best.get("char_count", 0),
            "section_hits": best.get("section_hits", {}),
            "contact_hits": best.get("contact_hits", {}),
            "ocr_enabled": enable_ocr,
            "ocr_used": ocr_used,
            "methods": [
                {key: value for key, value in item.items() if key != "text"}
                for item in methods
            ],
            "low_quality_reasons": low_reasons,
            "warnings": cls._warnings(best, enable_ocr, low_reasons),
        }
        parse_quality = cls._build_parse_quality(diagnostics)
        return {
            "text": best.get("text", ""),
            "diagnostics": diagnostics,
            "parse_quality": parse_quality,
        }

    @classmethod
    def normalize_text(cls, text: str | None) -> str:
        if not text:
            return ""
        value = text.replace("\r\n", "\n").replace("\r", "\n")
        replacements = [
            (r"(?i)P\s*D\s*\n\s*F", "PDF"),
            (r"(?i)D\s*O\s*\n\s*C\s*X", "DOCX"),
            (r"(?i)pdf2ima\s*\n\s*ge", "pdf2image"),
            (r"(?i)stream\s*\n\s*lit", "Streamlit"),
            (r"(?i)fast\s*\n\s*api", "FastAPI"),
        ]
        for pattern, replacement in replacements:
            value = re.sub(pattern, replacement, value)
        value = re.sub(r"([A-Za-z]{2,})-\n([A-Za-z]{2,})", r"\1\2", value)
        value = re.sub(r"([A-Za-z]{3,})\n([a-z]{2,})", r"\1\2", value)
        lines = []
        for line in value.split("\n"):
            line = re.sub(r"[ \t\u3000]+", " ", line).strip()
            if line:
                lines.append(line)
        return "\n".join(lines)

    @classmethod
    def _extract_with_pdfplumber(cls, path: Path) -> dict[str, Any]:
        try:
            import pdfplumber

            texts: list[str] = []
            page_count = 0
            with pdfplumber.open(str(path)) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    texts.append(page.extract_text() or "")
            return cls._diagnose("pdfplumber", "\n".join(texts), page_count=page_count)
        except Exception as exc:  # pragma: no cover - depends on PDF backend
            return cls._diagnose("pdfplumber", "", error=str(exc))

    @classmethod
    def _extract_with_pypdf(cls, path: Path) -> dict[str, Any]:
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(path))
            texts = [(page.extract_text() or "") for page in reader.pages]
            return cls._diagnose("pypdf", "\n".join(texts), page_count=len(reader.pages))
        except Exception as exc:  # pragma: no cover - depends on PDF backend
            return cls._diagnose("pypdf", "", error=str(exc))

    @classmethod
    def _extract_with_ocr(cls, path: Path) -> dict[str, Any]:
        try:
            import fitz

            doc = fitz.open(str(path))
            texts: list[str] = []
            for page in doc:
                text_page = page.get_textpage_ocr(language="chi_sim+eng", dpi=200, full=True)
                texts.append(page.get_text("text", textpage=text_page) or "")
            return cls._diagnose("ocr_tesseract", "\n".join(texts), page_count=len(doc))
        except Exception as exc:  # pragma: no cover - OCR is optional in most envs
            return cls._diagnose(
                "ocr_tesseract",
                "",
                error=f"OCR unavailable or failed: {exc}",
            )

    @classmethod
    def _diagnose(
        cls,
        method: str,
        text: str,
        *,
        page_count: int = 0,
        error: str | None = None,
    ) -> dict[str, Any]:
        normalized = cls.normalize_text(text)
        lowered = normalized.lower()
        section_hits = {
            name: any(term.lower() in lowered for term in terms)
            for name, terms in cls.SECTION_TERMS.items()
        }
        contact_hits = {
            "email": bool(re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", normalized)),
            "phone": bool(re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", normalized)),
        }
        hit_count = sum(1 for matched in section_hits.values() if matched)
        contact_count = sum(1 for matched in contact_hits.values() if matched)
        quality_score = len(normalized) + hit_count * 120 + contact_count * 50
        return {
            "method": method,
            "text": normalized,
            "page_count": page_count,
            "char_count": len(normalized),
            "section_hits": section_hits,
            "contact_hits": contact_hits,
            "quality_score": quality_score,
            "error": error,
        }

    @classmethod
    def _choose_best(cls, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        return max(candidates, key=lambda item: item.get("quality_score", 0), default={})

    @classmethod
    def _low_quality_reasons(cls, item: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        char_count = item.get("char_count", 0)
        if char_count <= 0:
            reasons.append("empty_text")
        elif char_count < cls.LOW_CHAR_THRESHOLD:
            reasons.append("too_few_characters")
        section_hits = item.get("section_hits", {})
        if sum(1 for matched in section_hits.values() if matched) < 2:
            reasons.append("few_resume_sections")
        return reasons

    @classmethod
    def _warnings(
        cls,
        item: dict[str, Any],
        enable_ocr: bool,
        low_reasons: list[str],
    ) -> list[str]:
        warnings: list[str] = []
        if low_reasons and not enable_ocr:
            warnings.append("Text extraction quality is low; OCR fallback is disabled.")
        if not any((item.get("contact_hits") or {}).values()):
            warnings.append("Contact information was not detected.")
        if item.get("error"):
            warnings.append(str(item["error"]))
        return warnings

    @classmethod
    def _build_parse_quality(cls, diagnostics: dict[str, Any]) -> dict[str, Any]:
        section_hits = diagnostics.get("section_hits") or {}
        contact_hits = diagnostics.get("contact_hits") or {}
        missing_fields = [
            label
            for key, label in (
                ("education", "education"),
                ("projects", "projects"),
                ("skills", "skills"),
            )
            if not section_hits.get(key)
        ]
        if not any(contact_hits.values()):
            missing_fields.append("contact")
        reasons = diagnostics.get("low_quality_reasons") or []
        if diagnostics.get("char_count", 0) <= 0:
            status = "failed"
        elif reasons:
            status = "low_quality"
        else:
            status = "usable"
        return {
            "version": "resume_parse_quality_v1",
            "status": status,
            "char_count": diagnostics.get("char_count", 0),
            "best_method": diagnostics.get("best_method"),
            "ocr_used": diagnostics.get("ocr_used", False),
            "missing_fields": missing_fields,
            "low_quality_reasons": reasons,
            "warnings": diagnostics.get("warnings", []),
        }
