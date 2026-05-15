from pathlib import Path

import pytest

from app.services.client.resume_text_extractor import ResumeTextExtractor


@pytest.mark.unit
def test_resume_text_extractor_selects_best_method_and_repairs_broken_words(monkeypatch, tmp_path):
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    def fake_pdfplumber(path: Path):
        return ResumeTextExtractor._diagnose(
            "pdfplumber",
            (
                "詹已誉\n教育经历\n项目经历\nHireMate AI 招聘审核\n"
                "支持 PD\nF/DOCX 解析链路、OCR、pdf2ima\nge，"
                "包含简历解析、岗位评分、AI 面试、学习任务和训练复盘。"
                "专业技能\nPython Streamlit SQL PostgreSQL Redis Docker FastAPI。"
            ),
            page_count=1,
        )

    def fake_pypdf(path: Path):
        return ResumeTextExtractor._diagnose("pypdf", "Python", page_count=1)

    monkeypatch.setattr(ResumeTextExtractor, "_extract_with_pdfplumber", fake_pdfplumber)
    monkeypatch.setattr(ResumeTextExtractor, "_extract_with_pypdf", fake_pypdf)

    result = ResumeTextExtractor.extract(pdf_path)

    assert result["diagnostics"]["best_method"] == "pdfplumber"
    assert "PDF/DOCX" in result["text"]
    assert "pdf2image" in result["text"]
    assert result["parse_quality"]["status"] == "usable"


@pytest.mark.unit
def test_resume_text_extractor_uses_ocr_only_when_enabled(monkeypatch, tmp_path):
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    def empty_result(method):
        return lambda path: ResumeTextExtractor._diagnose(method, "", page_count=1)

    def fake_ocr(path: Path):
        return ResumeTextExtractor._diagnose(
            "ocr_tesseract",
            "教育经历\n项目经历\nOCR extracted Python Redis SQL backend project\n专业技能",
            page_count=1,
        )

    monkeypatch.setattr(ResumeTextExtractor, "_extract_with_pdfplumber", empty_result("pdfplumber"))
    monkeypatch.setattr(ResumeTextExtractor, "_extract_with_pypdf", empty_result("pypdf"))
    monkeypatch.setattr(ResumeTextExtractor, "_extract_with_ocr", fake_ocr)

    disabled = ResumeTextExtractor.extract(pdf_path, enable_ocr=False)
    assert disabled["text"] == ""
    assert disabled["diagnostics"]["ocr_used"] is False
    assert "empty_text" in disabled["parse_quality"]["low_quality_reasons"]

    enabled = ResumeTextExtractor.extract(pdf_path, enable_ocr=True)
    assert enabled["diagnostics"]["best_method"] == "ocr_tesseract"
    assert enabled["diagnostics"]["ocr_used"] is True
    assert "Python" in enabled["text"]
