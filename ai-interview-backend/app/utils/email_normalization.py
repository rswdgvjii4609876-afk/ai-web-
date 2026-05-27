def normalize_email(value: str | None) -> str:
    """Normalize account emails before lookup or persistence."""
    return (str(value or "")).strip().lower()
