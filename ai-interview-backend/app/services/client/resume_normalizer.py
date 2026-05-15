from __future__ import annotations

import re
from typing import Any


SECTION_HEADINGS = {
    "education": ("教育经历", "教育背景", "学历", "Education"),
    "projects": ("项目经历", "项目经验", "项目", "Projects"),
    "experience": ("实习经历", "工作经历", "实践经历", "Experience"),
    "skills": ("专业技能", "技能", "技术栈", "Skills"),
    "awards": ("获奖经历", "荣誉奖项", "奖项", "Awards"),
    "campus_experience": ("校园经历", "校园活动", "社团经历", "Campus"),
}

KNOWN_SKILLS = (
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "C#",
    "SQL",
    "MySQL",
    "PostgreSQL",
    "Redis",
    "FastAPI",
    "Django",
    "Flask",
    "Spring",
    "Vue",
    "React",
    "Streamlit",
    "OCR",
    "PDF",
    "DOCX",
    "Docker",
    "Linux",
    "Git",
    "Excel",
    "Power BI",
)


def normalize_parsed_resume(payload: Any, *, source_text: str = "") -> dict[str, Any]:
    """Return legacy-compatible parsed resume plus a stable normalized_resume block."""

    data = payload if isinstance(payload, dict) else {}
    raw_sections = _extract_raw_sections(source_text)
    profile = _profile_from(data, source_text)

    education = _normalize_section_items(data.get("education"), raw_sections.get("education"))
    projects = _normalize_project_items(data.get("projects"), raw_sections.get("projects"))
    experience = _normalize_section_items(data.get("experience"), raw_sections.get("experience"))
    awards = _normalize_section_items(data.get("awards"), raw_sections.get("awards"))
    campus_experience = _normalize_section_items(
        data.get("campus_experience") or data.get("campus"),
        raw_sections.get("campus_experience"),
    )
    skills = _normalize_skill_items(data.get("skills"), raw_sections.get("skills"), source_text)

    normalized_resume = {
        "version": "normalized_resume_v1",
        "profile": profile,
        "education": education,
        "projects": projects,
        "experience": experience,
        "skills": skills,
        "awards": awards,
        "campus_experience": campus_experience,
        "raw_sections": raw_sections,
        "completeness": {
            "has_contact": bool(profile.get("email") or profile.get("phone")),
            "has_education": bool(education),
            "has_projects": bool(projects),
            "has_experience": bool(experience),
            "has_skills": bool(skills),
        },
    }
    normalized_resume["missing_fields"] = [
        label
        for key, label in (
            ("has_contact", "contact"),
            ("has_education", "education"),
            ("has_projects", "projects"),
            ("has_skills", "skills"),
        )
        if not normalized_resume["completeness"].get(key)
    ]

    legacy = {
        "name": profile.get("name", ""),
        "education": [_item_text(item) for item in education],
        "skills": [item.get("name") or item.get("source_text", "") for item in skills],
        "experience": [_item_text(item) for item in experience],
        "projects": [_project_text(item) for item in projects],
        "summary": _safe_text(data.get("summary")) or _build_summary(profile, skills, projects, experience),
        "awards": [_item_text(item) for item in awards],
        "campus_experience": [_item_text(item) for item in campus_experience],
        "profile": profile,
        "normalized_resume": normalized_resume,
    }
    for key, value in data.items():
        legacy.setdefault(key, value)
    return legacy


def _profile_from(data: dict[str, Any], source_text: str) -> dict[str, str]:
    text = source_text or _safe_text(data)
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    phone_match = re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text)
    name = _safe_text(data.get("name"))
    if not name:
        for line in text.splitlines():
            candidate = line.strip()
            if candidate and len(candidate) <= 12 and not re.search(r"[@\d:：|]", candidate):
                if not any(term in candidate for terms in SECTION_HEADINGS.values() for term in terms):
                    name = candidate
                    break
    return {
        "name": name,
        "email": email_match.group(0) if email_match else _safe_text(data.get("email")),
        "phone": phone_match.group(0) if phone_match else _safe_text(data.get("phone")),
        "target_position": _safe_text(data.get("target_position")),
    }


def _extract_raw_sections(text: str) -> dict[str, str]:
    if not text:
        return {}
    matches: list[tuple[int, int, str]] = []
    for key, headings in SECTION_HEADINGS.items():
        for heading in headings:
            match = re.search(re.escape(heading), text, re.IGNORECASE)
            if match:
                matches.append((match.start(), match.end(), key))
                break
    matches.sort(key=lambda item: item[0])
    sections: dict[str, str] = {}
    for index, (_, end, key) in enumerate(matches):
        next_start = matches[index + 1][0] if index + 1 < len(matches) else len(text)
        content = text[end:next_start].strip(" \n:：|")
        if content:
            sections[key] = content
    return sections


def _normalize_section_items(value: Any, fallback_text: str | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in _as_list(value):
        if isinstance(entry, dict):
            source = _safe_text(entry.get("source_text") or entry.get("evidence") or entry)
            item = {key: _safe_text(val) for key, val in entry.items() if val is not None}
            item.setdefault("source_text", source)
            items.append(item)
        else:
            text = _safe_text(entry)
            if text:
                items.append({"source_text": text})
    if not items and fallback_text:
        for block in _split_blocks(fallback_text):
            items.append({"source_text": block})
    return items


def _normalize_project_items(value: Any, fallback_text: str | None = None) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for entry in _as_list(value):
        if isinstance(entry, dict):
            source = _safe_text(entry.get("source_text") or entry.get("evidence") or entry.get("description") or entry)
            title = _safe_text(entry.get("title") or entry.get("name")) or _first_line(source)
            projects.append(
                {
                    "title": title,
                    "description": _safe_text(entry.get("description") or entry.get("evidence") or source),
                    "technologies": _extract_known_skills(source),
                    "source_text": source,
                }
            )
        else:
            text = _safe_text(entry)
            if text:
                projects.append(
                    {
                        "title": _first_line(text),
                        "description": text,
                        "technologies": _extract_known_skills(text),
                        "source_text": text,
                    }
                )
    if not projects and fallback_text:
        for block in _split_blocks(fallback_text):
            projects.append(
                {
                    "title": _first_line(block),
                    "description": block,
                    "technologies": _extract_known_skills(block),
                    "source_text": block,
                }
            )
    return projects


def _normalize_skill_items(value: Any, fallback_text: str | None = None, source_text: str = "") -> list[dict[str, str]]:
    skills: dict[str, dict[str, str]] = {}
    for entry in _as_list(value):
        if isinstance(entry, dict):
            name = _safe_text(entry.get("skill") or entry.get("name") or entry.get("title"))
            evidence = _safe_text(entry.get("evidence") or entry.get("source_text") or entry)
        else:
            name = _safe_text(entry)
            evidence = name
        if name:
            skills[name] = {"name": name, "evidence": evidence, "source_text": evidence}
    for skill in _extract_known_skills("\n".join([fallback_text or "", source_text or ""])):
        skills.setdefault(skill, {"name": skill, "evidence": "Detected in resume text", "source_text": skill})
    return list(skills.values())


def _extract_known_skills(text: str) -> list[str]:
    lowered = text.lower()
    detected = []
    for skill in KNOWN_SKILLS:
        if skill.lower() in lowered:
            detected.append(skill)
    return detected


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return " ".join(_safe_text(item) for item in value.values() if item is not None).strip()
    if isinstance(value, (list, tuple)):
        return " ".join(_safe_text(item) for item in value if item is not None).strip()
    return str(value).strip()


def _split_blocks(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n{2,}|(?=\n[-•*])", text or "") if block.strip()]
    if len(blocks) <= 1:
        lines = [line.strip(" -•*") for line in (text or "").splitlines() if line.strip()]
        return ["\n".join(lines)] if lines else []
    return blocks


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip(" -•*|")
        if line:
            return line[:80]
    return ""


def _item_text(item: dict[str, Any]) -> str:
    return _safe_text(item.get("source_text") or item)


def _project_text(item: dict[str, Any]) -> str:
    title = _safe_text(item.get("title"))
    description = _safe_text(item.get("description") or item.get("source_text"))
    return f"{title}: {description}" if title and description and title not in description else description or title


def _build_summary(
    profile: dict[str, str],
    skills: list[dict[str, str]],
    projects: list[dict[str, Any]],
    experience: list[dict[str, Any]],
) -> str:
    parts = []
    if profile.get("name"):
        parts.append(profile["name"])
    if skills:
        parts.append("Skills: " + ", ".join(item.get("name", "") for item in skills[:8] if item.get("name")))
    if projects:
        parts.append("Projects: " + "; ".join(item.get("title", "") for item in projects[:3] if item.get("title")))
    if experience:
        parts.append("Experience evidence available")
    return " | ".join(part for part in parts if part)
