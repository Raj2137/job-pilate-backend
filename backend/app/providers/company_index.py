"""Curated cross-industry launch company registry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CompanySeed:
    name: str
    domain: str
    careers_url: str
    industry: str
    ats_type: str = "auto"
    ats_identifier: str | None = None


COMPANY_SEEDS = [
    CompanySeed("Amazon", "amazon.jobs", "https://www.amazon.jobs", "technology", "custom"),
    CompanySeed("Microsoft", "microsoft.com", "https://jobs.careers.microsoft.com", "technology", "custom"),
    CompanySeed("Google", "google.com", "https://www.google.com/about/careers/applications/jobs/results", "technology", "custom"),
    CompanySeed("Apple", "apple.com", "https://jobs.apple.com/en-us/search", "technology", "custom"),
    CompanySeed("Meta", "metacareers.com", "https://www.metacareers.com/jobs", "technology", "custom"),
    CompanySeed(
        "Netflix",
        "netflix.com",
        "https://explore.jobs.netflix.net/careers/search?domain=netflix.com&query=%2A",
        "technology",
        "custom",
    ),
    CompanySeed("NVIDIA", "nvidia.com", "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite", "technology"),
    CompanySeed("Salesforce", "salesforce.com", "https://careers.salesforce.com/en/jobs/", "saas", "custom"),
    CompanySeed("Adobe", "adobe.com", "https://careers.adobe.com/us/en/search-results", "technology", "custom"),
    CompanySeed("Oracle", "oracle.com", "https://careers.oracle.com/en/sites/jobsearch/jobs", "technology", "oracle"),
    CompanySeed("IBM", "ibm.com", "https://www.ibm.com/careers/search", "technology", "custom"),
    CompanySeed("Cisco", "cisco.com", "https://jobs.cisco.com/jobs/SearchJobs/", "technology", "custom"),
    CompanySeed("Intel", "intel.com", "https://jobs.intel.com/en/search-jobs", "semiconductors", "custom"),
    CompanySeed("Uber", "uber.com", "https://www.uber.com/us/en/careers/list/", "technology", "custom"),
    CompanySeed("Airbnb", "airbnb.com", "https://careers.airbnb.com/positions/", "technology", "custom"),
    CompanySeed("Stripe", "stripe.com", "https://job-boards.greenhouse.io/stripe", "fintech"),
    CompanySeed("Cloudflare", "cloudflare.com", "https://job-boards.greenhouse.io/cloudflare", "cloud"),
    CompanySeed("Datadog", "datadoghq.com", "https://careers.datadoghq.com/", "cloud", "custom"),
    CompanySeed("Notion", "notion.so", "https://jobs.ashbyhq.com/notion", "saas"),
    CompanySeed("Figma", "figma.com", "https://job-boards.greenhouse.io/figma", "saas"),
    CompanySeed("OpenAI", "openai.com", "https://jobs.ashbyhq.com/openai", "artificial-intelligence"),
    CompanySeed("Anthropic", "anthropic.com", "https://job-boards.greenhouse.io/anthropic", "artificial-intelligence"),
    CompanySeed("Atlassian", "atlassian.com", "https://www.atlassian.com/company/careers/all-jobs", "saas", "custom"),
    CompanySeed("Shopify", "shopify.com", "https://www.shopify.com/careers", "ecommerce", "custom"),
    CompanySeed("GitHub", "github.com", "https://www.github.careers/careers-home/jobs", "developer-tools", "custom"),
    CompanySeed("JPMorgan Chase", "jpmorganchase.com", "https://careers.jpmorgan.com/global/en/search-results", "banking", "custom"),
    CompanySeed("Goldman Sachs", "goldmansachs.com", "https://higher.gs.com/results", "banking", "custom"),
    CompanySeed("Morgan Stanley", "morganstanley.com", "https://www.morganstanley.com/careers/career-opportunities-search", "banking", "custom"),
    CompanySeed("Bank of America", "bankofamerica.com", "https://careers.bankofamerica.com/en-us/job-search", "banking", "custom"),
    CompanySeed("Citi", "citi.com", "https://jobs.citi.com/search-jobs", "banking", "custom"),
    CompanySeed("Wells Fargo", "wellsfargojobs.com", "https://www.wellsfargojobs.com/en/jobs/", "banking", "custom"),
    CompanySeed("HSBC", "hsbc.com", "https://www.hsbc.com/careers/find-a-job", "banking", "custom"),
    CompanySeed("Barclays", "barclays.com", "https://search.jobs.barclays/", "banking", "custom"),
    CompanySeed("Visa", "visa.com", "https://careers.smartrecruiters.com/Visa", "payments"),
    CompanySeed("Mastercard", "mastercard.com", "https://careers.mastercard.com/us/en/search-results", "payments", "custom"),
    CompanySeed("PayPal", "paypal.com", "https://careers.pypl.com/home/", "payments", "custom"),
    CompanySeed("Block", "block.xyz", "https://block.xyz/careers/jobs", "fintech", "custom"),
    CompanySeed("Razorpay", "razorpay.com", "https://razorpay.com/careers/", "fintech", "custom"),
    CompanySeed("PhonePe", "phonepe.com", "https://www.phonepe.com/careers/jobs/", "fintech", "custom"),
    CompanySeed("Walmart", "walmart.com", "https://careers.walmart.com/results", "retail", "custom"),
    CompanySeed("Flipkart", "flipkartcareers.com", "https://www.flipkartcareers.com/#!/joblist", "ecommerce", "custom"),
    CompanySeed("Swiggy", "swiggy.com", "https://careers.swiggy.com/", "ecommerce", "custom"),
    CompanySeed("Zomato", "zomato.com", "https://www.zomato.com/careers", "ecommerce", "custom"),
    CompanySeed("Accenture", "accenture.com", "https://www.accenture.com/us-en/careers/jobsearch", "consulting", "custom"),
    CompanySeed("Deloitte", "deloitte.com", "https://apply.deloitte.com/careers/SearchJobs", "consulting", "custom"),
    CompanySeed("Infosys", "infosys.com", "https://digitalcareers.infosys.com/global-careers", "consulting", "custom"),
    CompanySeed("TCS", "tcs.com", "https://ibegin.tcsapps.com/candidate/jobs/search", "consulting", "custom"),
    CompanySeed("Wipro", "wipro.com", "https://careers.wipro.com/careers-home/jobs", "consulting", "custom"),
    CompanySeed("Bosch", "bosch.com", "https://careers.smartrecruiters.com/BoschGroup", "manufacturing"),
    CompanySeed("Tesla", "tesla.com", "https://www.tesla.com/careers/search/", "automotive", "custom"),
]
