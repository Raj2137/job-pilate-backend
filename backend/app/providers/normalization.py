"""Shared normalization helpers for public job connectors."""

from __future__ import annotations

from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self.parts.append("\n- ")
        elif tag in {"br", "p", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"li", "p", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_html(value: str | None) -> str | None:
    if not value:
        return None
    parser = _TextParser()
    parser.feed(value)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    text = "\n".join(line for line in lines if line)
    return unescape(text).strip() or None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(normalized[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def details_status(description: str | None, *, minimum_length: int = 120) -> str:
    return "complete" if description and len(description.strip()) >= minimum_length else "partial"


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
