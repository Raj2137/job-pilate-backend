"""Deterministic resume-to-job matching agent."""

from __future__ import annotations

import re
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.ai.llm_client import LlmCompletionRequest, LlmProviderError, complete_text
from app.models.job import Job
from app.models.user import User
from app.repositories.llm_key_repository import decrypt_llm_key, get_llm_key, mark_llm_key_used
from app.repositories.job_repository import list_match_candidates
from app.schemas.job import ResumeJobMatchItem, ResumeJobMatchRequest, ResumeJobMatchResponse
from app.schemas.llm_key import LlmProvider


STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "into",
    "the",
    "this",
    "that",
    "with",
    "you",
    "your",
    "will",
    "work",
    "using",
    "built",
    "build",
    "team",
    "role",
    "job",
    "experience",
    "india",
    "hyderabad",
    "bengaluru",
    "bangalore",
    "present",
    "july",
    "email",
    "github",
    "linkedin",
    "leetcode",
    "education",
    "technical",
    "technology",
    "project",
    "projects",
    "developer",
    "engineer",
    "engineering",
    "platform",
    "deployment",
    "integrated",
    "integrating",
    "application",
    "applications",
    "investment",
    "safety",
    "time",
}

IMPORTANT_TECH = {
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "node",
    "fastapi",
    "django",
    "flask",
    "sql",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "aws",
    "gcp",
    "azure",
    "docker",
    "kubernetes",
    "terraform",
    "spark",
    "airflow",
    "pandas",
    "machine",
    "learning",
    "ai",
    "llm",
    "backend",
    "frontend",
    "fullstack",
    "data",
    "devops",
    "cloud",
    "api",
}

TITLE_SIGNAL_STOPWORDS = STOPWORDS | {
    "api",
    "cloud",
    "data",
    "development",
    "devops",
    "llm",
    "agent",
    "automation",
    "code",
}

NON_ENGINEERING_TITLE_TERMS = (
    "account executive",
    "customer success",
    "sales",
    "auditor",
    "mechanical",
    "data center",
    "capital markets",
    "investment banking",
)

SENIOR_TITLE_TERMS = ("director", "head of", "manager", "principal", "staff", "architect", "lead", "senior")

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class MatchProfile:
    target_roles: list[str]
    years_experience: int | None


def match_jobs_for_resume(db: Session, payload: ResumeJobMatchRequest, user: User | None = None) -> ResumeJobMatchResponse:
    profile = _match_profile(payload)
    resume_keywords = _resume_keywords(payload, profile)
    query_terms = _query_terms(payload, profile, resume_keywords)
    candidates, filter_trace, relaxed = _find_candidates(db, payload, query_terms, profile)
    scored = [_score_job(job, payload, profile, resume_keywords) for job in candidates]
    scored.sort(key=lambda item: item.score, reverse=True)
    llm_used = False
    llm_status = None
    if payload.use_llm:
        scored, llm_used, llm_status = _maybe_llm_rerank(db, payload, user, scored)
    return ResumeJobMatchResponse(
        total_candidates=len(candidates),
        returned=min(payload.limit, len(scored)),
        resume_keywords=resume_keywords[:30],
        inferred_target_roles=profile.target_roles,
        inferred_years_experience=profile.years_experience,
        relaxed=relaxed,
        filter_trace=filter_trace,
        llm_used=llm_used,
        llm_status=llm_status,
        items=scored[: payload.limit],
    )


def _find_candidates(
    db: Session,
    payload: ResumeJobMatchRequest,
    query_terms: list[str],
    profile: MatchProfile,
) -> tuple[list[Job], list[str], bool]:
    effective_job_title = payload.job_title or (profile.target_roles[0] if profile.target_roles else None)
    attempts = [
        {
            "label": "strict preferences",
            "job_title": effective_job_title,
            "locations": payload.preferred_locations,
            "remote": payload.remote,
            "posted_since": _posted_since(payload),
            "require_jd": payload.require_jd,
        },
        {
            "label": "relaxed remote preference",
            "job_title": effective_job_title,
            "locations": payload.preferred_locations,
            "remote": None,
            "posted_since": _posted_since(payload),
            "require_jd": payload.require_jd,
        },
        {
            "label": "relaxed recency window",
            "job_title": effective_job_title,
            "locations": payload.preferred_locations,
            "remote": None,
            "posted_since": None,
            "require_jd": payload.require_jd,
        },
        {
            "label": "relaxed exact title",
            "job_title": None,
            "locations": payload.preferred_locations,
            "remote": None,
            "posted_since": None,
            "require_jd": payload.require_jd,
        },
        {
            "label": "relaxed location",
            "job_title": None,
            "locations": [],
            "remote": None,
            "posted_since": None,
            "require_jd": payload.require_jd,
        },
        {
            "label": "included jobs without JD",
            "job_title": None,
            "locations": [],
            "remote": None,
            "posted_since": None,
            "require_jd": False,
        },
    ]
    trace: list[str] = []
    for index, attempt in enumerate(attempts):
        candidates = list_match_candidates(
            db,
            query_terms=query_terms,
            job_title=attempt["job_title"],
            preferred_locations=attempt["locations"],
            remote=attempt["remote"],
            source=payload.source,
            posted_since=attempt["posted_since"],
            require_jd=attempt["require_jd"],
            latest_first=payload.latest_first,
            limit=payload.candidate_limit,
        )
        trace.append(f"{attempt['label']}: {len(candidates)} candidates")
        if candidates:
            return candidates, trace, index > 0
    return [], trace, False


def _match_profile(payload: ResumeJobMatchRequest) -> MatchProfile:
    explicit_roles = [_normalize_keyword(role) for role in [payload.job_title or "", *payload.target_roles] if role]
    inferred_roles = explicit_roles or _infer_target_roles(payload.resume_text)
    return MatchProfile(
        target_roles=list(dict.fromkeys(inferred_roles)),
        years_experience=payload.years_experience if payload.years_experience is not None else _extract_years(payload.resume_text),
    )


def _infer_target_roles(resume_text: str) -> list[str]:
    text = _text(resume_text).replace("-", " ")
    roles: list[str] = []
    if "full stack" in text or "fullstack" in text:
        roles.extend(["full stack developer", "backend engineer", "software engineer", "frontend engineer"])
    elif "backend" in text or "fastapi" in text or "node.js" in text or "express.js" in text:
        roles.extend(["backend engineer", "software engineer"])
    elif "frontend" in text or "react" in text or "angular" in text:
        roles.extend(["frontend engineer", "software engineer"])
    elif "software" in text or "developer" in text or "engineer" in text:
        roles.append("software engineer")

    if "ai agent" in text or "agentic" in text or "llm" in text or "openai" in text:
        roles.append("ai engineer")

    return list(dict.fromkeys(roles or ["software engineer", "backend engineer"]))


def _query_terms(payload: ResumeJobMatchRequest, profile: MatchProfile, resume_keywords: list[str]) -> list[str]:
    role_words: list[str] = []
    for role in profile.target_roles:
        role_words.extend(word for word in role.split() if word not in STOPWORDS and len(word) > 2)
    high_signal_keywords = [
        keyword
        for keyword in resume_keywords
        if keyword in IMPORTANT_TECH and keyword not in TITLE_SIGNAL_STOPWORDS
    ]
    return list(dict.fromkeys([*profile.target_roles, *role_words, *payload.skills, *high_signal_keywords[:12]]))


def _resume_keywords(payload: ResumeJobMatchRequest, profile: MatchProfile) -> list[str]:
    explicit = [_normalize_keyword(skill) for skill in [*profile.target_roles, *payload.skills]]
    explicit = [skill for skill in explicit if skill]
    words = [
        word
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}", payload.resume_text.lower())
        if word not in STOPWORDS and len(word) > 2
    ]
    counts = Counter(words)
    weighted = sorted(
        counts,
        key=lambda word: (
            word in IMPORTANT_TECH,
            counts[word],
            len(word),
        ),
        reverse=True,
    )
    return list(dict.fromkeys([*explicit, *weighted]))


def _score_job(
    job: Job,
    payload: ResumeJobMatchRequest,
    profile: MatchProfile,
    resume_keywords: list[str],
) -> ResumeJobMatchItem:
    title_text = _text(job.title)
    jd_text = _text(job.description)
    combined_text = f"{title_text} {jd_text} {_text(job.company)} {_text(job.location)}"
    important_keywords = resume_keywords[:40]

    title_matches = [
        keyword
        for keyword in important_keywords
        if keyword not in TITLE_SIGNAL_STOPWORDS and keyword in title_text
    ]
    jd_matches = [keyword for keyword in important_keywords if keyword in jd_text]
    matched = list(dict.fromkeys([*title_matches, *jd_matches]))
    missing = [keyword for keyword in important_keywords[:15] if keyword not in combined_text]

    score = 0.0
    reasons: list[str] = []
    role_score, role_reasons = _role_score(job, profile)
    score += role_score
    reasons.extend(role_reasons)
    if title_matches:
        score += min(20, len(title_matches) * 6)
        reasons.append(f"Title matches {', '.join(title_matches[:4])}.")
    if jd_matches:
        score += min(35, len(jd_matches) * 3)
        reasons.append(f"JD matches {len(jd_matches)} resume keywords.")
    if payload.preferred_locations and job.location:
        location_text = job.location.lower()
        if any(location.lower() in location_text for location in payload.preferred_locations):
            score += 10
            reasons.append("Location matches preference.")
    if payload.remote is not None and job.remote == payload.remote:
        score += 5
        reasons.append("Remote preference matches.")
    if payload.posted_within_days and job.posted_at:
        score += 5
        reasons.append(f"Posted within last {payload.posted_within_days} days.")

    experience_signal, experience_score = _experience_signal(job, profile)
    score += experience_score
    if experience_signal != "unknown":
        reasons.append(f"Experience signal: {experience_signal}.")

    red_flag_score, red_flag_reasons = _red_flag_score(job, profile)
    score += red_flag_score
    reasons.extend(red_flag_reasons)

    if not job.description:
        score -= 10
        reasons.append("JD is missing, so confidence is lower.")

    if not reasons:
        reasons.append("Matched through broad resume/catalog keyword overlap.")

    return ResumeJobMatchItem(
        job=job,
        score=round(max(0.0, min(score, 100.0)), 1),
        matched_keywords=matched[:20],
        missing_keywords=missing[:10],
        experience_signal=experience_signal,
        reasons=reasons,
    )


def _experience_signal(job: Job, profile: MatchProfile) -> tuple[str, float]:
    years = profile.years_experience
    if years is None:
        return "unknown", 0.0

    text = f"{job.title} {job.seniority_level or ''} {job.description or ''}".lower()
    required_years = _required_years(text)
    if required_years is not None:
        gap = required_years - years
        if gap >= 4:
            return f"too senior: asks {required_years}+ years, profile has {years}", -50.0
        if gap >= 2:
            return f"stretch: asks {required_years}+ years, profile has {years}", -30.0
        if gap >= 1:
            return f"slight stretch: asks {required_years}+ years, profile has {years}", -12.0
        return f"experience matches requirement of {required_years}+ years", 14.0

    if any(token in text for token in ("director", "head of", "manager", "principal", "staff", "architect")):
        return ("too senior for current experience", -45.0) if years < 7 else ("good for leadership/senior role", 10.0)
    if any(token in text for token in ("lead", "senior", "mid-senior")):
        return ("too senior for current experience", -35.0) if years < 5 else ("good for senior role", 10.0)
    if any(token in text for token in ("intern", "internship", "graduate", "entry level", "junior")):
        return ("too senior for entry-level role", -8.0) if years >= 4 else ("good for early-career role", 10.0)
    if 1 <= years <= 4:
        return "good for associate/mid-level role", 14.0
    if years >= 5:
        return "good for mid-level/general role", 8.0
    return "possible early-career fit", 3.0


def _extract_years(text: str) -> int | None:
    normalized = text.lower()
    explicit_matches = re.findall(r"(\d{1,2})\+?\s*(?:years|yrs)", normalized)
    found = [int(match) for match in explicit_matches]

    month_names = "|".join(MONTHS)
    range_pattern = re.compile(
        rf"(?:(?P<start_month>{month_names})\.?\s+)?(?P<start_year>20\d{{2}}|19\d{{2}})\s*[-–]\s*"
        rf"(?:(?P<end_month>{month_names})\.?\s+)?(?P<end_year>20\d{{2}}|19\d{{2}}|present|current|now)"
    )
    now = datetime.now(UTC)
    for match in range_pattern.finditer(normalized):
        before = normalized[max(0, match.start() - 120) : match.start()]
        end_year_text = match.group("end_year")
        if end_year_text not in {"present", "current", "now"} and any(
            token in before for token in ("education", "bachelor", "intermediate", "college", "university")
        ):
            continue
        start_year = int(match.group("start_year"))
        start_month = MONTHS.get(match.group("start_month") or "", 1)
        if end_year_text in {"present", "current", "now"}:
            end_year = now.year
            end_month = now.month
        else:
            end_year = int(end_year_text)
            end_month = MONTHS.get(match.group("end_month") or "", 12)
        months = (end_year - start_year) * 12 + (end_month - start_month)
        if months >= 6:
            found.append(max(1, round(months / 12)))

    return max(found) if found else None


def _required_years(text: str) -> int | None:
    patterns = [
        r"minimum\s+(\d{1,2})\+?\s*(?:years|yrs)",
        r"at least\s+(\d{1,2})\+?\s*(?:years|yrs)",
        r"(\d{1,2})\+\s*(?:years|yrs)",
        r"(\d{1,2})\s*[-–]\s*\d{1,2}\s*(?:years|yrs)",
        r"(\d{1,2})\s*(?:years|yrs)\s+of",
    ]
    found: list[int] = []
    for pattern in patterns:
        found.extend(int(match) for match in re.findall(pattern, text))
    return max(found) if found else None


def _role_score(job: Job, profile: MatchProfile) -> tuple[float, list[str]]:
    title = _text(job.title).replace("-", " ")
    normalized_targets = [_normalize_keyword(term).replace("-", " ") for term in profile.target_roles if term]
    if not normalized_targets:
        return 0.0, []

    reasons: list[str] = []
    for target in normalized_targets:
        target_words = [word for word in target.split() if word not in STOPWORDS and len(word) > 2]
        if not target_words:
            continue
        matched_words = [word for word in target_words if word in title]
        if target in title:
            reasons.append(f"Role closely matches '{target}'.")
            return 22.0, reasons
        if matched_words:
            score = min(16.0, len(matched_words) * 6.0)
            reasons.append(f"Role partially matches '{target}'.")
            return score, reasons
    return -8.0, ["Role title is not a close match to preferences."]


def _red_flag_score(job: Job, profile: MatchProfile) -> tuple[float, list[str]]:
    title = _text(job.title).replace("-", " ")
    text = f"{title} {_text(job.seniority_level)}"
    reasons: list[str] = []
    score = 0.0

    if any(term in title for term in NON_ENGINEERING_TITLE_TERMS):
        score -= 35.0
        reasons.append("Red flag: role family looks outside software/full-stack/backend engineering.")

    if profile.years_experience is not None and profile.years_experience < 5:
        senior_terms = [term for term in SENIOR_TITLE_TERMS if term in text]
        if senior_terms:
            score -= 20.0
            reasons.append(f"Red flag: seniority marker '{senior_terms[0]}' is high for this profile.")

    role_text = " ".join(profile.target_roles)
    if ("backend" in role_text or "full stack" in role_text or "software" in role_text) and "devops" in title:
        score -= 12.0
        reasons.append("Red flag: DevOps/platform focus is weaker than target role.")

    return score, reasons


def _posted_since(payload: ResumeJobMatchRequest) -> datetime | None:
    if payload.posted_within_days is None:
        return None
    return (datetime.now(UTC) - timedelta(days=payload.posted_within_days)).replace(tzinfo=None)


def _normalize_keyword(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _text(value: str | None) -> str:
    return (value or "").lower()


def _maybe_llm_rerank(
    db: Session,
    payload: ResumeJobMatchRequest,
    user: User | None,
    scored: list[ResumeJobMatchItem],
) -> tuple[list[ResumeJobMatchItem], bool, str]:
    if user is None:
        return scored, False, "LLM skipped: user context is required."
    if payload.llm_key_id is None:
        return scored, False, "LLM skipped: llm_key_id is required when use_llm is true."
    record = get_llm_key(db, user, payload.llm_key_id)
    if record is None:
        return scored, False, "LLM skipped: key not found."
    if not record.is_active:
        return scored, False, "LLM skipped: key is inactive."
    if not scored:
        return scored, False, "LLM skipped: no candidates to rerank."

    top = scored[: payload.llm_top_k]
    try:
        text = complete_text(
            LlmCompletionRequest(
                provider=LlmProvider(record.provider),
                api_key=decrypt_llm_key(record),
                model=record.default_model or "",
                system_prompt=_llm_system_prompt(),
                user_prompt=_llm_user_prompt(payload, top),
                max_tokens=1800,
                temperature=0.1,
            )
        )
        reranked = _apply_llm_rerank(scored, text)
    except (LlmProviderError, ValueError, json.JSONDecodeError) as exc:
        return scored, False, f"LLM fallback: {exc}"

    mark_llm_key_used(db, record)
    return reranked, True, "LLM rerank applied."


def _llm_system_prompt() -> str:
    return (
        "You are a careful job-fit evaluator. Return only valid JSON. "
        "Favor roles matching the candidate's years of experience. Penalize senior, lead, staff, principal, "
        "director, manager, and jobs requiring more years than the candidate has. "
        "Use resume skills, role fit, JD evidence, location, remote preference, and red flags."
    )


def _llm_user_prompt(payload: ResumeJobMatchRequest, items: list[ResumeJobMatchItem]) -> str:
    compact_jobs = []
    for index, item in enumerate(items, start=1):
        job = item.job
        compact_jobs.append(
            {
                "rank_id": index,
                "job_id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "remote": job.remote,
                "seniority_level": job.seniority_level,
                "score_before_llm": item.score,
                "experience_signal": item.experience_signal,
                "jd_excerpt": (job.description or "")[:1200],
            }
        )
    return json.dumps(
        {
            "candidate": {
                "resume_text": payload.resume_text[:5000],
                "job_title": payload.job_title,
                "target_roles": payload.target_roles,
                "skills": payload.skills,
                "preferred_locations": payload.preferred_locations,
                "years_experience": payload.years_experience,
                "remote": payload.remote,
            },
            "jobs": compact_jobs,
            "return_schema": {
                "items": [
                    {
                        "job_id": "integer",
                        "score": "0-100 number",
                        "reasons": ["short reason strings"],
                        "red_flags": ["short red flag strings"],
                    }
                ]
            },
        },
        ensure_ascii=True,
    )


def _apply_llm_rerank(scored: list[ResumeJobMatchItem], text: str) -> list[ResumeJobMatchItem]:
    payload = _extract_json(text)
    by_id = {item.job.id: item for item in scored}
    reordered: list[ResumeJobMatchItem] = []
    seen: set[int] = set()
    for row in payload.get("items", []):
        job_id = int(row["job_id"])
        item = by_id.get(job_id)
        if item is None:
            continue
        reasons = [str(reason) for reason in row.get("reasons", [])][:5]
        red_flags = [f"Red flag: {flag}" for flag in row.get("red_flags", [])][:5]
        updated = item.model_copy(
            update={
                "score": round(float(row.get("score", item.score)), 1),
                "reasons": [*reasons, *red_flags] or item.reasons,
            }
        )
        reordered.append(updated)
        seen.add(job_id)
    remaining = [item for item in scored if item.job.id not in seen]
    reordered.extend(remaining)
    reordered.sort(key=lambda item: item.score, reverse=True)
    return reordered


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM did not return JSON")
    return json.loads(cleaned[start : end + 1])
