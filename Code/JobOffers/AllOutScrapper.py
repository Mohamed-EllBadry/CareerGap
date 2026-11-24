#!/home/mo2/Projects/CareerGap/.venv/bin/python
import sys
import json
import time
import re
import math
import hashlib
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
from jobspy import scrape_jobs

OUTPUT_JSON_FILE = Path(__file__).with_name("jobs_data.json")
OUTPUT_CSV_FILE = Path(__file__).with_name("jobs_data.csv")
OUTPUT_LINKS_FILE = Path(__file__).with_name("job_links.json")
SCRAPER_STATE_FILE = Path(__file__).with_name("scraper_state.json")

LOCATION = "Egypt"
COUNTRY_CODE = "EG"

# Indeed uses these 45 specific queries + offset pagination to go deeper each run
INDEED_SEARCH_QUERIES = [
    # Roles
    "Software Engineer", "Backend Developer", "Frontend Developer", "Full Stack Developer",
    "Mobile Developer", "Android Developer", "iOS Developer", "React Developer",
    "Node.js Developer", "Python Developer", "Java Developer", ".NET Developer",
    "PHP Developer", "Flutter Developer", "Embedded Systems Engineer",
    # Data & AI
    "Data Analyst", "Data Scientist", "Data Engineer", "Business Intelligence",
    "Machine Learning Engineer", "AI Engineer", "NLP Engineer",
    # Infrastructure & Cloud
    "DevOps Engineer", "Cloud Engineer", "AWS Engineer", "Site Reliability Engineer",
    "Linux Administrator", "System Administrator", "Network Engineer",
    "Database Administrator", "IT Support",
    # Security
    "Cybersecurity Engineer", "Information Security", "Penetration Tester",
    # Design & Product
    "UI UX Designer", "Product Manager", "Scrum Master", "Agile Coach",
    # QA
    "QA Engineer", "Test Automation Engineer", "Software Tester",
    # Management & Other
    "IT Manager", "Technical Lead", "Solution Architect", "ERP Consultant",
    "CRM Developer", "Odoo Developer"
]

# LinkedIn uses only broad umbrella queries — kept small to avoid bans
LINKEDIN_SEARCH_QUERIES = [
    "Software Engineer",
    "Data",
    "DevOps",
    "Cybersecurity",
    "UI UX",
    "IT Manager",
    "QA Engineer",
    "Mobile Developer"
]

# Controls which platforms to scrape in this run
ENABLE_WUZZUF = True
ENABLE_INDEED = True
ENABLE_LINKEDIN = True

WUZZUF_MAX_PAGES = None     # None = crawl ALL available pages across Egypt
INDEED_RESULTS_PER_QUERY = 25   # Results per keyword per run (safe limit)
INDEED_OFFSET_STEP = 25         # How much offset advances each run (= INDEED_RESULTS_PER_QUERY)
LINKEDIN_RESULTS_PER_QUERY = 15 # Keep LinkedIn conservative to avoid bans

# Verification of active links
VERIFY_ACTIVE_LINKS = True
# VERIFY_ACTIVE_LINKS = False

TECH_KEYWORDS = [
    # Languages
    "Python", "C++", "C#", "C", "Java", "JavaScript", "TypeScript", "Go", "Golang",
    "Rust", "PHP", "Ruby", "Swift", "Kotlin", "Scala", "Dart", "R", "MATLAB",
    # Frameworks & Libraries
    "React", "React Native", "Angular", "Vue", "Node.js", "Django", "FastAPI",
    "Flask", "Spring Boot", ".NET", "ASP.NET", "Express", "Laravel", "Next.js",
    "Tailwind", "Bootstrap", "jQuery", "Pandas", "NumPy", "PyTorch", "TensorFlow",
    # Databases & Caching
    "SQL", "NoSQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Oracle",
    "SQLite", "Elasticsearch", "Cassandra", "DynamoDB", "Firebase",
    # Cloud & DevOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Linux", "Git", "GitHub",
    "GitLab", "CI/CD", "Jenkins", "Terraform", "Ansible", "Nginx",
    # Core Concepts
    "OOP", "REST API", "GraphQL", "Microservices", "Data Structures", "Algorithms",
    "Machine Learning", "Deep Learning", "AI", "Agile", "Scrum", "DevOps"
]

def clean_val(val):
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val

def clean_html(raw_html: str) -> str:
    """Strips HTML markup and converts tags into clean readable text."""
    if not raw_html:
        return ""
    text = re.sub(r"</?(?:li|p|h\d|div|section|ul)[^>]*>", "\n", raw_html)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)

def extract_skills(text: str, extra_skills=None) -> list:
    """Extracts tech skills from text and merges with any platform tags."""
    found = set()
    if extra_skills and isinstance(extra_skills, list):
        found.update(extra_skills)
    
    if text:
        for skill in TECH_KEYWORDS:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                found.add(skill)
    return sorted(list(found))

def extract_experience(text: str) -> dict:
    """Extracts minimum and maximum years of experience from text."""
    if not text:
        return {"min": None, "max": None}
    
    # Matches: '3-5 years', '3 to 5 years', '3 - 5 yrs'
    range_match = re.search(
        r'(\d+)\s*(?:-|to)\s*(\d+)\s*\+?\s*(?:years?|yrs?)(?:\s+of\s+experience)?',
        text, re.IGNORECASE
    )
    if range_match:
        return {"min": int(range_match.group(1)), "max": int(range_match.group(2))}
    
    # Matches: '3+ years', '3 years of experience'
    min_match = re.search(
        r'(\d+)\+?\s*(?:years?|yrs?)(?:\s+of\s+experience)?',
        text, re.IGNORECASE
    )
    if min_match:
        return {"min": int(min_match.group(1)), "max": None}
    
    return {"min": None, "max": None}

def extract_education(text: str) -> str:
    """Extracts minimum degree requirement from text."""
    if not text:
        return "Unspecified"
    patterns = [
        (r'\b(?:phd|doctorate)\b', "PhD / Doctorate"),
        (r'\b(?:master\'?s?|msc|mba)\b', "Master's Degree"),
        (r'\b(?:bachelor\'?s?|bsc|bs|b\.a\.|b\.sc|b\.e\.|undergraduate)\b', "Bachelor's Degree"),
        (r'\b(?:diploma|associate degree)\b', "Diploma / Associate"),
        (r'\b(?:high school)\b', "High School")
    ]
    for pattern, label in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return "Unspecified"

def extract_seniority(title: str, board_level: str = "") -> str:
    """Normalizes seniority level across all platforms."""
    title_lower = title.lower()
    if any(k in title_lower for k in ["intern", "internship", "trainee"]):
        return "Internship"
    if any(k in title_lower for k in ["junior", "fresh", "entry"]):
        return "Entry Level"
    if any(k in title_lower for k in ["team lead", "tech lead", "lead", "principal", "staff"]):
        return "Lead / Principal"
    if any(k in title_lower for k in ["senior", "sr."]):
        return "Senior Level"
    if any(k in title_lower for k in ["mid", "middle"]):
        return "Mid Level"

    level = str(board_level or "").strip()
    if level and level.lower() not in ["none", "nan", "unspecified"]:
        return level.title()

    return "Experienced"

def get_consistent_job_id(url: str, existing_url_map: dict) -> str:
    """Returns a deterministic, non-random job_id."""
    if url in existing_url_map:
        return existing_url_map[url]
    match = re.search(r'/jobs/p/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]

def check_link_live(url: str, platform: str) -> bool:
    """Lightweight HTTP check to determine if a job link is still active."""
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                return False
            final_url = resp.geturl()
            # If Wuzzuf redirected away from the job page
            if platform == "wuzzuf" and "/jobs/p/" not in final_url:
                return False
            
            content = resp.read().decode("utf-8", errors="ignore")
            
            if platform == "wuzzuf":
                if '"status":"closed"' in content or '"status":"expired"' in content or "This job has expired" in content:
                    return False
            elif platform == "indeed":
                if "job has expired" in content.lower() or "job is closed" in content.lower():
                    return False
            elif platform == "linkedin":
                if "no longer accepting applications" in content.lower() or "job is closed" in content.lower():
                    return False
            return True
    except urllib.error.HTTPError as e:
        if e.code in [404, 410]:
            return False
        return True
    except Exception:
        return True

def verify_and_clean_links(existing_jobs: dict, current_links: list) -> list:
    """
    Checks if links are still accessible.
    If closed/expired:
      - Purges the URL from job_links.json so users never see expired offers
      - Preserves all historical details in jobs_data.json and sets is_active=False
    """
    print("\n" + "="*50)
    print("▶ Verifying Active Job Links & Cleaning Expired...")
    print("="*50)
    
    active_links = []
    purged_count = 0

    for idx, item in enumerate(current_links, start=1):
        url = item.get("url", "")
        job_id = item.get("job_id", "")
        platform = item.get("platform", "unknown")

        print(f"[{idx}/{len(current_links)}] Checking ({platform}): {job_id}...", end=" ", flush=True)
        is_live = check_link_live(url, platform)

        if is_live:
            print("ACTIVE")
            active_links.append(item)
            if job_id in existing_jobs:
                existing_jobs[job_id]["is_active"] = True
        else:
            print("EXPIRED / CLOSED -> Purging from links")
            purged_count += 1
            if job_id in existing_jobs:
                # Keep all data for dashboard analysis, mark as inactive
                existing_jobs[job_id]["is_active"] = False

        time.sleep(0.3)

    print(f"\n✓ Link Verification Done: {len(active_links)} active links retained. {purged_count} expired links purged.")
    return active_links

# ==============================================================================
# Scraper Part 1: Wuzzuf (Playwright)
# ==============================================================================
def scrape_wuzzuf(existing_jobs: dict, url_registry: dict) -> list:
    print("\n" + "="*50)
    print("▶ Starting Wuzzuf Scraper...")
    print("="*50)

    chromium_path = shutil.which("chromium") or shutil.which("google-chrome")
    collected_jobs = []
    wuzzuf_links = []

    with sync_playwright() as p:
        launch_kwargs = {"headless": False}
        if chromium_path:
            launch_kwargs["executable_path"] = chromium_path

        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page()

        # Step 1: Collect Links
        print("Collecting all IT & Software Development job links across Egypt from Wuzzuf...")
        page_num = 0
        while True:
            if WUZZUF_MAX_PAGES and page_num >= WUZZUF_MAX_PAGES:
                print(f"Reached page limit ({WUZZUF_MAX_PAGES} pages).")
                break

            url = f"https://wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt?start={page_num}&filters%5Broles%5D%5B0%5D=IT%2FSoftware%20Development&ref=browse-jobs"
            page.goto(url, wait_until="domcontentloaded")
            
            first_try = page.locator("a.css-o171kl").evaluate_all(
                """elements => elements.map(e => e.href).filter(h => h.includes("/jobs/p/"))"""
            )
            time.sleep(1.5)
            second_try = page.locator("a.css-o171kl").evaluate_all(
                """elements => elements.map(e => e.href).filter(h => h.includes("/jobs/p/"))"""
            )

            links = list(dict.fromkeys(first_try + second_try))
            if not links:
                break

            wuzzuf_links.extend(links)
            page_num += 1

        wuzzuf_links = list(dict.fromkeys(wuzzuf_links))
        print(f"Found {len(wuzzuf_links)} Wuzzuf job links.")

        # Step 2: Visit Each Job & Extract Data
        for idx, job_url in enumerate(wuzzuf_links, start=1):
            job_id = get_consistent_job_id(job_url, url_registry)
            url_registry[job_url] = job_id

            if job_id in existing_jobs:
                print(f"[{idx}/{len(wuzzuf_links)}] Wuzzuf: Skipping {job_id} (already saved).")
                continue

            print(f"[{idx}/{len(wuzzuf_links)}] Wuzzuf: Scraping {job_id}...")
            try:
                page.goto(job_url, wait_until="domcontentloaded", timeout=25000)
                html_content = page.content()

                # Extract JSON-LD
                job_posting = None
                for script in re.findall(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', html_content, re.DOTALL):
                    try:
                        d = json.loads(script)
                        if d.get('@type') == 'JobPosting':
                            job_posting = d
                            break
                    except Exception:
                        pass

                # Extract State
                job_attr = {}
                for line in html_content.split('\n'):
                    if '"entities"' in line and '"job"' in line and '"collection"' in line:
                        start = line.find('{')
                        end = line.rfind('}')
                        if start != -1 and end != -1:
                            try:
                                state_data = json.loads(line[start:end+1])
                                jobs_col = state_data.get('entities', {}).get('job', {}).get('collection', {})
                                for jid, job_obj in jobs_col.items():
                                    a = job_obj.get('attributes', {})
                                    if a.get('slug', '') in job_url or a.get('uri', '') in job_url:
                                        job_attr = a
                                        break
                                if not job_attr and jobs_col:
                                    main_id = list(state_data.get('jobPage', {}).get('similarJobs', {}).keys())
                                    if main_id and main_id[0] in jobs_col:
                                        job_attr = jobs_col[main_id[0]].get('attributes', {})
                            except Exception:
                                pass

                # Clean Title
                title = job_attr.get('title') or (job_posting.get('title') if job_posting else "")
                if not title:
                    h1 = page.locator("h1").first
                    title = h1.inner_text() if h1.count() > 0 else "Unknown Title"

                company = (job_posting.get("hiringOrganization", {}).get("name", "").strip() if job_posting else "")
                location = (job_posting.get("jobLocation", {}).get("address", {}).get("addressRegion", "") if job_posting else "")
                date_posted = job_posting.get("datePosted", "") if job_posting else job_attr.get('postedAt', '')

                # Description text
                description_text = ""
                if job_posting:
                    description_text = clean_html(job_posting.get("description", ""))
                elif "description" in job_attr:
                    description_text = clean_html(job_attr.get("description", "") + "\n" + job_attr.get("requirements", ""))

                # Workplace
                wp_data = job_attr.get('workplaceArrangement') or {}
                workplace = wp_data.get('displayedName')
                if not workplace:
                    wp_match = re.search(r'/a/(On-Site|Hybrid|Remote)-Jobs', html_content)
                    workplace = wp_match.group(1).replace('-', ' ') if wp_match else "On-site"

                # Application Links: True if on-platform, False + external company URL if external
                app_type = job_attr.get('applicationType', 'internal')
                redirect_url = job_attr.get('redirectUrl')
                if app_type == 'internal' or not redirect_url:
                    apply_on_platform = True
                    company_apply_url = None
                else:
                    apply_on_platform = False
                    company_apply_url = redirect_url

                # Skills
                skills = [k.get('name') for k in job_attr.get('keywords', []) if isinstance(k, dict) and k.get('name')]
                skills = extract_skills(description_text, skills)

                # Experience & Education
                exp_data = job_attr.get('workExperienceYears') or {}
                exp_years = {
                    "min": exp_data.get('min'),
                    "max": exp_data.get('max')
                }
                if exp_years["min"] is None:
                    exp_years = extract_experience(description_text)

                edu_data = (job_attr.get('candidatePreferences') or {}).get('educationLevel', {}).get('name')
                education = edu_data if edu_data else extract_education(description_text)

                # Seniority
                c_level = (job_attr.get('careerLevel') or {}).get('name', '')
                seniority = extract_seniority(title, c_level)

                # Salary
                sal_data = job_attr.get('salary') or {}
                curr = sal_data.get('currency')
                currency_code = curr.get('code') if isinstance(curr, dict) else curr
                period_obj = sal_data.get('period')
                period_str = period_obj.get('name') if isinstance(period_obj, dict) else period_obj

                salary_info = {
                    "hide_salary": job_attr.get("hideSalary", True),
                    "min": sal_data.get("min"),
                    "max": sal_data.get("max"),
                    "currency": currency_code,
                    "period": period_str
                }

                # Common 16-Field Unified Schema
                job_record = {
                    "job_id": job_id,
                    "platform": "wuzzuf",
                    "url": job_url,
                    "title": title,
                    "company": company,
                    "location": location or LOCATION,
                    "country": COUNTRY_CODE,
                    "workplace": workplace,
                    "seniority_level": seniority,
                    "skills_and_tools": skills,
                    "years_of_experience": exp_years,
                    "education_level": education,
                    "salary": salary_info,
                    "apply_on_platform": apply_on_platform,
                    "company_apply_url": company_apply_url,
                    "date_posted": str(date_posted),
                    "details": description_text
                }

                collected_jobs.append(job_record)
                existing_jobs[job_id] = job_record
                time.sleep(1)

            except Exception as e:
                print(f"  [!] Failed Wuzzuf {job_url}: {e}")

        browser.close()

    print(f"✓ Wuzzuf Finished: {len(collected_jobs)} new jobs added.")
    return collected_jobs

def load_scraper_state() -> dict:
    """Loads the persistent offset state so Indeed pagination continues where it left off."""
    if SCRAPER_STATE_FILE.exists():
        try:
            with SCRAPER_STATE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_scraper_state(state: dict):
    """Saves the current offset state to disk."""
    with SCRAPER_STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def _build_job_record(row, existing_jobs: dict) -> dict | None:
    """Shared row→record converter for both Indeed and LinkedIn rows."""
    job_id = str(row.get("id") or "")
    if not job_id or job_id in existing_jobs:
        return None

    title = str(row.get("title") or "Unknown Title")
    description = str(row.get("description") or "")
    platform = str(row.get("site") or "unknown")

    direct_apply = clean_val(row.get("job_url_direct"))
    if direct_apply:
        apply_on_platform = False
        company_apply_url = str(direct_apply)
    else:
        apply_on_platform = True
        company_apply_url = None

    is_remote = bool(row.get("is_remote"))
    if is_remote:
        workplace = "Remote"
    elif "hybrid" in (title + " " + description[:300]).lower():
        workplace = "Hybrid"
    else:
        workplace = "On-site"

    skills = extract_skills(description, row.get("skills"))
    exp_years = extract_experience(description)
    education = extract_education(description)
    seniority = extract_seniority(title, row.get("job_level"))

    sal_min = clean_val(row.get("min_amount"))
    sal_max = clean_val(row.get("max_amount"))
    currency = clean_val(row.get("currency"))
    period = clean_val(row.get("interval"))
    hide_sal = (sal_min is None and sal_max is None)

    return {
        "job_id": job_id,
        "platform": platform,
        "url": str(row.get("job_url") or ""),
        "title": title,
        "company": str(row.get("company") or "Unknown Company"),
        "location": str(row.get("location") or LOCATION),
        "country": COUNTRY_CODE,
        "workplace": workplace,
        "seniority_level": seniority,
        "skills_and_tools": skills,
        "years_of_experience": exp_years,
        "education_level": education,
        "salary": {
            "hide_salary": hide_sal,
            "min": sal_min,
            "max": sal_max,
            "currency": currency,
            "period": period
        },
        "apply_on_platform": apply_on_platform,
        "company_apply_url": company_apply_url,
        "date_posted": str(row.get("date_posted") or ""),
        "details": description
    }

def scrape_indeed(existing_jobs: dict, state: dict) -> list:
    """
    Scrapes Indeed using 45 specific tech queries.
    Uses offset pagination: each run picks up where the last left off per keyword.
    State is saved after every keyword so progress is never lost.
    """
    print("\n" + "="*50)
    print("▶ Starting Indeed Scraper (offset pagination)...")
    print("="*50)

    collected_jobs = []
    indeed_offsets = state.get("indeed_offsets", {})

    for q_idx, query in enumerate(INDEED_SEARCH_QUERIES, start=1):
        offset = indeed_offsets.get(query, 0)
        print(f"\n--- [{q_idx}/{len(INDEED_SEARCH_QUERIES)}] Indeed: '{query}' | offset={offset} ---")
        try:
            df = scrape_jobs(
                site_name=["indeed"],
                search_term=query,
                location=LOCATION,
                results_wanted=INDEED_RESULTS_PER_QUERY,
                country_indeed="egypt",
                offset=offset,
            )
            print(f"  → Retrieved {len(df)} listings.")
        except Exception as e:
            print(f"  → Skipped '{query}': {e}")
            time.sleep(3)
            continue

        new_this_query = 0
        for _, row in df.iterrows():
            record = _build_job_record(row, existing_jobs)
            if record:
                collected_jobs.append(record)
                existing_jobs[record["job_id"]] = record
                new_this_query += 1

        # Advance offset for next run regardless of how many were new
        indeed_offsets[query] = offset + INDEED_OFFSET_STEP
        state["indeed_offsets"] = indeed_offsets
        save_scraper_state(state)  # Save after every keyword — never lose progress

        print(f"  → {new_this_query} new jobs added for '{query}'.")
        time.sleep(3)  # Polite delay between Indeed queries

    print(f"\n✓ Indeed Finished: {len(collected_jobs)} new jobs added this run.")
    return collected_jobs

def scrape_linkedin(existing_jobs: dict) -> list:
    """
    Scrapes LinkedIn using a small set of broad queries.
    Kept intentionally conservative (no offset, low result count) to avoid bans.
    """
    print("\n" + "="*50)
    print("▶ Starting LinkedIn Scraper (conservative mode)...")
    print("="*50)

    collected_jobs = []

    for q_idx, query in enumerate(LINKEDIN_SEARCH_QUERIES, start=1):
        print(f"\n--- [{q_idx}/{len(LINKEDIN_SEARCH_QUERIES)}] LinkedIn: '{query}' ---")
        try:
            df = scrape_jobs(
                site_name=["linkedin"],
                search_term=query,
                location=LOCATION,
                results_wanted=LINKEDIN_RESULTS_PER_QUERY,
            )
            print(f"  → Retrieved {len(df)} listings.")
        except Exception as e:
            print(f"  → Skipped '{query}': {e}")
            time.sleep(5)
            continue

        new_this_query = 0
        for _, row in df.iterrows():
            record = _build_job_record(row, existing_jobs)
            if record:
                collected_jobs.append(record)
                existing_jobs[record["job_id"]] = record
                new_this_query += 1

        print(f"  → {new_this_query} new jobs added for '{query}'.")
        time.sleep(5)  # Conservative delay for LinkedIn

    print(f"\n✓ LinkedIn Finished: {len(collected_jobs)} new jobs added this run.")
    return collected_jobs


def main():
    print("="*60)
    print(" UNIFIED MULTI-PLATFORM JOB SCRAPER (Wuzzuf, Indeed, LinkedIn)")
    print("="*60)

    # 1. Load History to Prevent Overwriting Existing Jobs
    existing_jobs = {}
    url_registry = {}

    if OUTPUT_JSON_FILE.exists():
        try:
            with OUTPUT_JSON_FILE.open("r", encoding="utf-8") as f:
                for job in json.load(f):
                    if isinstance(job, dict) and "job_id" in job:
                        if "platform" not in job:
                            job["platform"] = next((p for d, p in (("wuzzuf.net", "wuzzuf"), ("indeed.com", "indeed"), ("linkedin.com", "linkedin")) if d in job.get("url", "")), "unknown")
                        existing_jobs[job["job_id"]] = job
                        if "url" in job:
                            url_registry[job["url"]] = job["job_id"]
            print(f"Loaded {len(existing_jobs)} existing jobs from {OUTPUT_JSON_FILE.name}.")
        except Exception as e:
            print(f"Notice: Starting fresh database ({e}).")

    initial_count = len(existing_jobs)

    # 2. Load persistent scraper state (Indeed offsets, etc.)
    scraper_state = load_scraper_state()

    # 3. Run Wuzzuf Scraper
    if ENABLE_WUZZUF:
        scrape_wuzzuf(existing_jobs, url_registry)

    # 4. Run Indeed Scraper (offset pagination — goes deeper every run)
    if ENABLE_INDEED:
        scrape_indeed(existing_jobs, scraper_state)

    # 5. Run LinkedIn Scraper (conservative — no offset, low volume, avoid bans)
    if ENABLE_LINKEDIN:
        scrape_linkedin(existing_jobs)

    # 4. Verify active links & purge expired ones from job_links.json
    #    All historical data remains in jobs_data.json with is_active=True/False
    all_links = [
        {"job_id": j["job_id"], "platform": j["platform"], "url": j["url"]}
        for j in existing_jobs.values()
        if j.get("url")
    ]

    if VERIFY_ACTIVE_LINKS and all_links:
        active_links = verify_and_clean_links(existing_jobs, all_links)
    else:
        # If verification is off, all links are considered active
        active_links = all_links
        for j in existing_jobs.values():
            j.setdefault("is_active", True)

    final_jobs_list = list(existing_jobs.values())
    new_jobs_added = len(final_jobs_list) - initial_count

    # 5. Save Unified Cumulative JSON Dataset (all jobs, active + historical)
    with OUTPUT_JSON_FILE.open("w", encoding="utf-8") as f:
        json.dump(final_jobs_list, f, ensure_ascii=False, indent=2)
    print(f"\n[Saved] Updated JSON database: {OUTPUT_JSON_FILE.name}")

    # 6. Save Active Links File ONLY (expired/closed links are removed)
    with OUTPUT_LINKS_FILE.open("w", encoding="utf-8") as f:
        json.dump(active_links, f, ensure_ascii=False, indent=2)
    print(f"[Saved] Active links registry ({len(active_links)} live links): {OUTPUT_LINKS_FILE.name}")

    # 6. Save Flat CSV Spreadsheet for Excel/Calc Analysis
    try:
        import pandas as pd
        flat_records = []
        for j in final_jobs_list:
            exp = j.get("years_of_experience") or {}
            sal = j.get("salary") or {}
            flat_records.append({
                "Job ID": j.get("job_id", ""),
                "Platform": j.get("platform", ""),
                "Title": j.get("title", ""),
                "Company": j.get("company", ""),
                "Location": j.get("location", ""),
                "Country": j.get("country", ""),
                "Workplace": j.get("workplace", ""),
                "Seniority": j.get("seniority_level", ""),
                "Min Exp (Years)": exp.get("min"),
                "Max Exp (Years)": exp.get("max"),
                "Education": j.get("education_level", ""),
                "Skills": ", ".join(j.get("skills_and_tools") or []),
                "Salary Min": sal.get("min"),
                "Salary Max": sal.get("max"),
                "Salary Currency": sal.get("currency"),
                "Apply On Platform": j.get("apply_on_platform"),
                "Company Apply URL": j.get("company_apply_url"),
                "Date Posted": j.get("date_posted", ""),
                "Is Active": j.get("is_active", True),
                "URL": j.get("url", "")
            })
        pd.DataFrame(flat_records).to_csv(OUTPUT_CSV_FILE, index=False)
        print(f"[Saved] Exported CSV spreadsheet: {OUTPUT_CSV_FILE.name}")
    except Exception as e:
        print(f"Notice: CSV export skipped ({e})")

    active_count = sum(1 for j in final_jobs_list if j.get("is_active", True))
    inactive_count = len(final_jobs_list) - active_count

    print("\n" + "="*60)
    print(f" DONE! Added {new_jobs_added} new jobs.")
    print(f" Total unified database size: {len(final_jobs_list)} jobs.")
    print(f" Active (live) links: {active_count}  |  Expired/inactive: {inactive_count}")
    print("="*60)

if __name__ == "__main__":
    main()