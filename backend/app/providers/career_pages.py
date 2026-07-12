"""Curated company career page targets.

Career pages are not one source. They are thousands of company-owned pages,
many backed by ATS platforms such as Greenhouse, Lever, Ashby, and Workday.
This file is the first version of our maintained company index.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CareerPageTarget:
    company: str
    ats: str
    identifier: str


DEFAULT_CAREER_PAGE_TARGETS = [
    CareerPageTarget(company="Netlify", ats="lever", identifier="netlify"),
]


def split_career_page_targets(targets: list[CareerPageTarget]) -> tuple[list[str], list[str]]:
    greenhouse_boards: list[str] = []
    lever_sites: list[str] = []

    for target in targets:
        if target.ats == "greenhouse":
            greenhouse_boards.append(target.identifier)
        elif target.ats == "lever":
            lever_sites.append(target.identifier)

    return greenhouse_boards, lever_sites
