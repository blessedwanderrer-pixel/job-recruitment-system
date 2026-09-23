from __future__ import annotations

import json
import re
from typing import Any

FORBIDDEN_TERMS = (
    r"\bage\b",
    r"\bgender\b",
    r"\bmale\b",
    r"\bfemale\b",
    r"\bwoman\b",
    r"\bman\b",
    r"\breligion\b",
    r"\bmuslim\b",
    r"\bchristian\b",
    r"\bhindu\b",
    r"\bmarital\b",
    r"\bmarried\b",
    r"\bsingle\b",
    r"\bwife\b",
    r"\bhusband\b",
    r"\bdob\b",
    r"date of birth",
    r"\bhire\b",
    r"\bhired\b",
    r"\breject\b",
    r"\brejection\b",
    r"\bscore\b",
    r"\brank\b",
    r"\branking\b",
    r"must be hired",
    r"should be hired",
)

INSTRUCTION_LINE = re.compile(
    r"ignore (all )?(your |the )?instructions|must be hired|recommend (hiring|rejection)",
    re.I,
)
_UNSAFE_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _strip_unsafe_chars(value: str) -> str:
    return _UNSAFE_CHARS.sub("", value or "")


def extract_pdf_text(data: bytes) -> str:
    if not data:
        return ""
    chunks = re.findall(rb"\((?:\\.|[^\\)])*\)", data)
    parts = []
    for raw in chunks:
        try:
            text = raw[1:-1].decode("latin-1")
        except Exception:
            continue
        text = text.replace("\\n", " ").replace("\\r", " ").replace("\\(", "(").replace("\\)", ")")
        text = _strip_unsafe_chars(text)
        if text.strip():
            parts.append(text)
    if parts:
        return " ".join(parts)
    return ""


DEMOGRAPHIC_LINE = re.compile(
    r"date of birth|\bgender\b|\breligion\b|\bmarital\b|\bage\b|\bfemale\b|\bmale\b",
    re.I,
)


def _clean_cv_text(cv_text: str) -> str:
    lines = []
    for line in re.split(r"[\n\r.]+", cv_text):
        if INSTRUCTION_LINE.search(line) or DEMOGRAPHIC_LINE.search(line):
            continue
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"ignore your instructions.*", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_phrase(value: str) -> str:
    text = _strip_unsafe_chars(re.sub(r"\s+", " ", value).strip())
    for pattern in FORBIDDEN_TERMS:
        text = re.sub(pattern, "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,;.-")
    return text


def _requirement_items(requirements: str) -> list[str]:
    items = re.split(r"[\n.;•]+", requirements or "")
    cleaned = [_sanitize_phrase(item) for item in items]
    return [item for item in cleaned if len(item) > 2][:12]


def _cv_mentions(cv_text: str, requirement: str) -> bool:
    tokens = [t for t in re.split(r"[^a-z0-9]+", requirement.lower()) if len(t) > 2]
    if not tokens:
        return False
    hay = cv_text.lower()
    hits = sum(1 for t in tokens if t in hay)
    return hits >= max(1, len(tokens) // 2)


def build_ai_summary(job: dict[str, Any], cv_text: str, cv_id: str, force_fail: bool = False) -> dict[str, Any]:
    if force_fail:
        return failed_summary(cv_id)
    cv = _clean_cv_text(cv_text)
    reqs = _requirement_items(job.get("requirements") or "")
    found = [r for r in reqs if _cv_mentions(cv, r)]
    missing = [r for r in reqs if r not in found]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cv) if len(s.strip()) > 12]
    bullets = []
    for sentence in sentences:
        cleaned = _sanitize_phrase(sentence)
        if cleaned and len(cleaned) > 8 and cleaned not in bullets:
            bullets.append(cleaned)
        if len(bullets) >= 5:
            break
    if len(bullets) < 3:
        title = _sanitize_phrase(job.get("title") or "this role")
        extras = [
            f"Candidate applied for {title} using the CV attached to this application.",
            "Experience and skills are taken only from the submitted CV text.",
            "No hiring recommendation is made; recruiters should review the CV directly.",
        ]
        for extra in extras:
            if extra not in bullets:
                bullets.append(extra)
            if len(bullets) >= 3:
                break
    bullets = bullets[:5]
    questions = [
        "Walk through a recent project from your CV that matches this job's main requirement.",
        "Which listed requirement would you want to demonstrate in a practical exercise, and how?",
        "What part of this role's requirements is newest for you, based on the CV you submitted?",
    ]
    if missing:
        questions[2] = f"How would you approach work involving: {missing[0]}?"
    questions = [_sanitize_phrase(q) for q in questions][:3]
    return {
        "status": "ready",
        "generated_by_ai": True,
        "label": "AI-generated",
        "cv_id": cv_id,
        "profile_bullets": bullets,
        "requirements_found": found,
        "requirements_missing": missing,
        "interview_questions": questions,
        "message": None,
    }


def failed_summary(cv_id: str | None = None) -> dict[str, Any]:
    return {
        "status": "failed",
        "generated_by_ai": True,
        "label": "AI-generated",
        "cv_id": cv_id,
        "profile_bullets": [],
        "requirements_found": [],
        "requirements_missing": [],
        "interview_questions": [],
        "message": "Summary not available",
    }


def pending_summary(cv_id: str) -> dict[str, Any]:
    return {
        "status": "pending",
        "generated_by_ai": True,
        "label": "AI-generated",
        "cv_id": cv_id,
        "profile_bullets": [],
        "requirements_found": [],
        "requirements_missing": [],
        "interview_questions": [],
        "message": None,
    }


def public_staff_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    status = row.get("status") or "failed"
    payload = {
        "status": status,
        "generated_by_ai": True,
        "label": "AI-generated",
        "cv_id": row.get("cv_id"),
        "profile_bullets": row.get("profile_bullets") or [],
        "requirements_found": row.get("requirements_found") or [],
        "requirements_missing": row.get("requirements_missing") or [],
        "interview_questions": row.get("interview_questions") or [],
        "message": row.get("message"),
    }
    if status != "ready":
        payload["message"] = payload.get("message") or "Summary not available"
    return payload


def row_from_summary(application_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "application_id": application_id,
        "cv_id": summary.get("cv_id"),
        "status": summary.get("status"),
        "generated_by_ai": True,
        "profile_bullets": summary.get("profile_bullets") or [],
        "requirements_found": summary.get("requirements_found") or [],
        "requirements_missing": summary.get("requirements_missing") or [],
        "interview_questions": summary.get("interview_questions") or [],
        "message": summary.get("message"),
    }


def as_json_list(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return []
    return value
