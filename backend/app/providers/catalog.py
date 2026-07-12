"""Launch catalogue controls for global job collection."""

from enum import StrEnum


class MajorAtsPlatform(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"
    WORKDAY = "workday"
    GENERIC = "generic"
    CUSTOM = "custom"
    ORACLE = "oracle"
    ICIMS = "icims"
    PHENOM = "phenom"
    EIGHTFOLD = "eightfold"
    SUCCESSFACTORS = "successfactors"
    AVATURE = "avature"


SUPPORTED_COMPANY_ATS = {
    MajorAtsPlatform.GREENHOUSE,
    MajorAtsPlatform.LEVER,
    MajorAtsPlatform.ASHBY,
    MajorAtsPlatform.SMARTRECRUITERS,
    MajorAtsPlatform.WORKDAY,
}


class LaunchCompany(StrEnum):
    AMAZON = "amazon"
    MICROSOFT = "microsoft"
    GOOGLE = "google"
    APPLE = "apple"
    META = "meta"
    NETFLIX = "netflix"
    NVIDIA = "nvidia"
    SALESFORCE = "salesforce"
    ADOBE = "adobe"
    ORACLE = "oracle"
    IBM = "ibm"
    CISCO = "cisco"
    INTEL = "intel"
    UBER = "uber"
    AIRBNB = "airbnb"
    STRIPE = "stripe"
    CLOUDFLARE = "cloudflare"
    DATADOG = "datadog"
    NOTION = "notion"
    FIGMA = "figma"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    ATLASSIAN = "atlassian"
    SHOPIFY = "shopify"
    GITHUB = "github"
    JPMORGAN_CHASE = "jpmorgan_chase"
    GOLDMAN_SACHS = "goldman_sachs"
    MORGAN_STANLEY = "morgan_stanley"
    BANK_OF_AMERICA = "bank_of_america"
    CITI = "citi"
    WELLS_FARGO = "wells_fargo"
    HSBC = "hsbc"
    BARCLAYS = "barclays"
    VISA = "visa"
    MASTERCARD = "mastercard"
    PAYPAL = "paypal"
    BLOCK = "block"
    RAZORPAY = "razorpay"
    PHONEPE = "phonepe"
    WALMART = "walmart"
    FLIPKART = "flipkart"
    SWIGGY = "swiggy"
    ZOMATO = "zomato"
    ACCENTURE = "accenture"
    DELOITTE = "deloitte"
    INFOSYS = "infosys"
    TCS = "tcs"
    WIPRO = "wipro"
    BOSCH = "bosch"
    TESLA = "tesla"


COMPANY_SLUGS_BY_ENUM = {
    LaunchCompany.AMAZON: "amazon",
    LaunchCompany.MICROSOFT: "microsoft",
    LaunchCompany.GOOGLE: "google",
    LaunchCompany.APPLE: "apple",
    LaunchCompany.META: "meta",
    LaunchCompany.NETFLIX: "netflix",
    LaunchCompany.NVIDIA: "nvidia",
    LaunchCompany.SALESFORCE: "salesforce",
    LaunchCompany.ADOBE: "adobe",
    LaunchCompany.ORACLE: "oracle",
    LaunchCompany.IBM: "ibm",
    LaunchCompany.CISCO: "cisco",
    LaunchCompany.INTEL: "intel",
    LaunchCompany.UBER: "uber",
    LaunchCompany.AIRBNB: "airbnb",
    LaunchCompany.STRIPE: "stripe",
    LaunchCompany.CLOUDFLARE: "cloudflare",
    LaunchCompany.DATADOG: "datadog",
    LaunchCompany.NOTION: "notion",
    LaunchCompany.FIGMA: "figma",
    LaunchCompany.OPENAI: "openai",
    LaunchCompany.ANTHROPIC: "anthropic",
    LaunchCompany.ATLASSIAN: "atlassian",
    LaunchCompany.SHOPIFY: "shopify",
    LaunchCompany.GITHUB: "github",
    LaunchCompany.JPMORGAN_CHASE: "jpmorgan-chase",
    LaunchCompany.GOLDMAN_SACHS: "goldman-sachs",
    LaunchCompany.MORGAN_STANLEY: "morgan-stanley",
    LaunchCompany.BANK_OF_AMERICA: "bank-of-america",
    LaunchCompany.CITI: "citi",
    LaunchCompany.WELLS_FARGO: "wells-fargo",
    LaunchCompany.HSBC: "hsbc",
    LaunchCompany.BARCLAYS: "barclays",
    LaunchCompany.VISA: "visa",
    LaunchCompany.MASTERCARD: "mastercard",
    LaunchCompany.PAYPAL: "paypal",
    LaunchCompany.BLOCK: "block",
    LaunchCompany.RAZORPAY: "razorpay",
    LaunchCompany.PHONEPE: "phonepe",
    LaunchCompany.WALMART: "walmart",
    LaunchCompany.FLIPKART: "flipkart",
    LaunchCompany.SWIGGY: "swiggy",
    LaunchCompany.ZOMATO: "zomato",
    LaunchCompany.ACCENTURE: "accenture",
    LaunchCompany.DELOITTE: "deloitte",
    LaunchCompany.INFOSYS: "infosys",
    LaunchCompany.TCS: "tcs",
    LaunchCompany.WIPRO: "wipro",
    LaunchCompany.BOSCH: "bosch",
    LaunchCompany.TESLA: "tesla",
}


DEFAULT_LINKEDIN_SEARCHES = [
    ("software engineer", "India"),
    ("backend engineer", "India"),
    ("frontend engineer", "India"),
    ("full stack engineer", "India"),
    ("data engineer", "India"),
    ("machine learning engineer", "India"),
    ("software engineer", "United States"),
    ("software engineer", "United Kingdom"),
    ("software engineer", "Canada"),
    ("software engineer", "Germany"),
    ("software engineer", "Singapore"),
    ("software engineer", "United Arab Emirates"),
]


DEFAULT_FULL_COVERAGE_SEARCHES = [
    ("software engineer", "India"),
    ("backend engineer", "India"),
    ("frontend engineer", "India"),
    ("full stack engineer", "India"),
    ("data engineer", "India"),
    ("data analyst", "India"),
    ("machine learning engineer", "India"),
    ("ai engineer", "India"),
    ("devops engineer", "India"),
    ("site reliability engineer", "India"),
    ("cloud engineer", "India"),
    ("product manager", "India"),
    ("designer", "India"),
    ("qa engineer", "India"),
    ("software engineer intern", "India"),
    ("software engineer", "United States"),
    ("backend engineer", "United States"),
    ("frontend engineer", "United States"),
    ("data engineer", "United States"),
    ("machine learning engineer", "United States"),
    ("software engineer", "United Kingdom"),
    ("software engineer", "Canada"),
    ("software engineer", "Germany"),
    ("software engineer", "Singapore"),
    ("software engineer", "United Arab Emirates"),
]
