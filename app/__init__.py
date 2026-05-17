from __future__ import annotations

from pathlib import Path

_BACKEND_APP = Path(__file__).resolve().parents[1] / "ai-interview-backend" / "app"
if _BACKEND_APP.exists():
    __path__.append(str(_BACKEND_APP))
