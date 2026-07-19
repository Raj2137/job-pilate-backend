"""Search URL builders for sources that need browser-based collection."""

from urllib.parse import urlencode


def build_linkedin_jobs_url(query: str, location: str | None = None) -> str:
    params = {"keywords": query}
    if location:
        params["location"] = location
    return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"


def build_indeed_jobs_url(query: str, location: str | None = None) -> str:
    params = {"q": query}
    if location:
        params["l"] = location
    return f"https://www.indeed.com/jobs?{urlencode(params)}"
