"""Job source definitions."""

from enum import StrEnum


class JobSource(StrEnum):
    CAREER_PAGES = "career_pages"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"
    WORKDAY = "workday"
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    NAUKRI = "naukri"
    FOUNDIT = "foundit"
    WELLFOUND = "wellfound"
    YC_JOBS = "yc_jobs"
    INSTAHYRE = "instahyre"
    CUTSHORT = "cutshort"
    HIRIST = "hirist"


DEFAULT_SELECTED_SOURCES = [
    JobSource.CAREER_PAGES,
    JobSource.LINKEDIN,
]


SOURCE_METADATA = {
    JobSource.CAREER_PAGES: {
        "label": "Company Career Pages",
        "category": "career_page",
        "status": "partial",
        "notes": "Runs supported ATS connectors such as Greenhouse and Lever.",
    },
    JobSource.GREENHOUSE: {
        "label": "Greenhouse",
        "category": "ats",
        "status": "active",
        "notes": "Stable public job board JSON endpoint for configured company boards.",
    },
    JobSource.LEVER: {
        "label": "Lever",
        "category": "ats",
        "status": "active",
        "notes": "Stable public postings JSON endpoint for configured company sites.",
    },
    JobSource.ASHBY: {
        "label": "Ashby",
        "category": "ats",
        "status": "active",
        "notes": "Public Ashby job-board API with descriptions and application URLs.",
    },
    JobSource.SMARTRECRUITERS: {
        "label": "SmartRecruiters",
        "category": "ats",
        "status": "active",
        "notes": "Public SmartRecruiters posting API with bounded detail enrichment.",
    },
    JobSource.WORKDAY: {
        "label": "Workday",
        "category": "ats",
        "status": "active",
        "notes": "Public Workday external-career-site adapter with bounded pagination.",
    },
    JobSource.LINKEDIN: {
        "label": "LinkedIn",
        "category": "job_board",
        "status": "best_effort",
        "notes": "High coverage public job discovery source; stores visible guest search results when available.",
    },
    JobSource.INDEED: {
        "label": "Indeed",
        "category": "job_board",
        "status": "excluded",
        "notes": "Excluded from the current collection architecture.",
    },
    JobSource.NAUKRI: {
        "label": "Naukri",
        "category": "job_board",
        "status": "planned",
        "notes": "Important for Indian job market coverage.",
    },
    JobSource.FOUNDIT: {
        "label": "Foundit",
        "category": "job_board",
        "status": "planned",
        "notes": "Important for Indian and APAC job market coverage.",
    },
    JobSource.WELLFOUND: {
        "label": "Wellfound",
        "category": "job_board",
        "status": "planned",
        "notes": "Useful for startup roles.",
    },
    JobSource.YC_JOBS: {
        "label": "YC Jobs",
        "category": "job_board",
        "status": "planned",
        "notes": "Useful for startup roles from Y Combinator companies.",
    },
    JobSource.INSTAHYRE: {
        "label": "Instahyre",
        "category": "job_board",
        "status": "planned",
        "notes": "Useful for Indian tech hiring.",
    },
    JobSource.CUTSHORT: {
        "label": "Cutshort",
        "category": "job_board",
        "status": "planned",
        "notes": "Useful for Indian startup and tech hiring.",
    },
    JobSource.HIRIST: {
        "label": "Hirist",
        "category": "job_board",
        "status": "planned",
        "notes": "Useful for Indian tech roles.",
    },
}
