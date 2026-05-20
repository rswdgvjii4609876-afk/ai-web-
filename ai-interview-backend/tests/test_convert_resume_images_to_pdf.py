import json

import pytest
from PIL import Image

from app.scripts.convert_resume_images_to_pdf import convert_directory


@pytest.mark.unit
def test_convert_resume_image_to_pdf_writes_manifest(tmp_path):
    input_dir = tmp_path / "raw"
    out_dir = tmp_path / "converted"
    input_dir.mkdir()

    image_path = input_dir / "scan.jpg"
    Image.new("RGB", (120, 160), color=(255, 255, 255)).save(image_path)

    result = convert_directory(input_dir, out_dir, overwrite=True)

    pdf_path = out_dir / "scan.converted_image.pdf"
    manifest_path = out_dir / "conversion_manifest.json"

    assert result["total_images"] == 1
    assert result["converted"] == 1
    assert pdf_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["records"][0]
    assert record["status"] == "converted"
    assert record["ocr_status"] == "not_performed"
    assert record["source_sha256"]
    assert record["target_sha256"]
    assert "API" not in manifest_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_convert_resume_image_to_pdf_reports_empty_directory(tmp_path):
    input_dir = tmp_path / "raw"
    out_dir = tmp_path / "converted"
    input_dir.mkdir()

    result = convert_directory(input_dir, out_dir, overwrite=True)

    assert result["total_images"] == 0
    assert result["converted"] == 0
    assert json.loads((out_dir / "conversion_manifest.json").read_text(encoding="utf-8"))["records"] == []
