from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - exercised only when optional dependency is missing.
    Image = None
    ImageOps = None


SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_images(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"input_dir does not exist: {input_dir}")
    return sorted(
        [
            item
            for item in input_dir.iterdir()
            if item.is_file() and item.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        ],
        key=lambda item: item.name.lower(),
    )


def _target_pdf_path(out_dir: Path, image_path: Path) -> Path:
    return out_dir / f"{image_path.stem}.converted_image.pdf"


def convert_image_to_pdf(image_path: Path, target_path: Path, *, overwrite: bool = False) -> dict[str, Any]:
    if Image is None or ImageOps is None:
        return {
            "source_file": str(image_path),
            "target_file": str(target_path),
            "status": "failed",
            "error": "pillow_not_installed",
            "ocr_status": "not_performed",
        }
    if target_path.exists() and not overwrite:
        return {
            "source_file": str(image_path),
            "source_sha256": _sha256(image_path),
            "target_file": str(target_path),
            "target_sha256": _sha256(target_path),
            "status": "skipped",
            "reason": "target_exists",
            "ocr_status": "not_performed",
            "text_extraction_note": "converted image PDF requires OCR before resume parsing",
        }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        normalized = ImageOps.exif_transpose(image)
        rgb_image = normalized.convert("RGB")
        rgb_image.save(target_path, "PDF", resolution=150.0)
    return {
        "source_file": str(image_path),
        "source_sha256": _sha256(image_path),
        "target_file": str(target_path),
        "target_sha256": _sha256(target_path),
        "status": "converted",
        "ocr_status": "not_performed",
        "text_extraction_note": "converted image PDF requires OCR before resume parsing",
    }


def convert_directory(input_dir: Path, out_dir: Path, *, overwrite: bool = False) -> dict[str, Any]:
    images = _scan_images(input_dir)
    records = [
        convert_image_to_pdf(image_path, _target_pdf_path(out_dir, image_path), overwrite=overwrite)
        for image_path in images
    ]
    payload = {
        "generated_at": _utc_now(),
        "input_dir": str(input_dir),
        "out_dir": str(out_dir),
        "total_images": len(images),
        "converted": sum(1 for item in records if item.get("status") == "converted"),
        "skipped": sum(1 for item in records if item.get("status") == "skipped"),
        "failed": sum(1 for item in records if item.get("status") == "failed"),
        "boundary": "JPG/PNG to PDF conversion does not perform OCR and does not create real human interview samples.",
        "records": records,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "conversion_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert resume image scans to image-based PDFs.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    args.input_dir = args.input_dir.resolve()
    args.out_dir = args.out_dir.resolve()
    return args


def main() -> int:
    args = parse_args()
    result = convert_directory(args.input_dir, args.out_dir, overwrite=args.overwrite)
    print(json.dumps({key: result[key] for key in ("total_images", "converted", "skipped", "failed")}, indent=2))
    print(f"manifest={args.out_dir / 'conversion_manifest.json'}")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
