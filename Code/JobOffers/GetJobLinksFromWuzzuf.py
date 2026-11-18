import sys
import json
import time
import re
import hashlib
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

output_links_file = Path(__file__).with_name("job_links.json")
output_jobs_file = Path(__file__).with_name("jobs_data.json")

def get_consistent_job_id(url: str, existing_url_map: dict) -> str:
    if url in existing_url_map:
        return existing_url_map[url]
    
    match = re.search(r'/jobs/p/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]

def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"</?(?:li|p|h\d|div|section|ul)[^>]*>", "\n", raw_html)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)

def parse_job_page(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    html_content = page.content()

    job_posting = None
    for script in re.findall(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', html_content, re.DOTALL):
        try:
            d = json.loads(script)
            if d.get('@type') == 'JobPosting':
                job_posting = d
                break
        except Exception:
            pass

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
                        slug = a.get('slug', '')
                        uri = a.get('uri', '')
                        if (slug and slug in url) or (uri and uri in url):
                            job_attr = a
                            break
                    if not job_attr and jobs_col:
                        main_id = list(state_data.get('jobPage', {}).get('similarJobs', {}).keys())
                        if main_id and main_id[0] in jobs_col:
                            job_attr = jobs_col[main_id[0]].get('attributes', {})
                except Exception:
                    pass

    salary_data = job_attr.get('salary') or {}
    curr = salary_data.get('currency')
    currency_str = curr.get('code') if isinstance(curr, dict) else curr
    per = salary_data.get('period')
    period_str = per.get('name') if isinstance(per, dict) else per

    salary_info = {
        "hide_salary": job_attr.get("hideSalary", True),
        "min": salary_data.get("min"),
        "max": salary_data.get("max"),
        "currency": currency_str,
        "period": period_str,
        "additional_details": salary_data.get("additionalDetails")
    }

    skills = [k.get('name') for k in job_attr.get('keywords', []) if isinstance(k, dict) and k.get('name')]
    career_lvl = job_attr.get('careerLevel') or {}
    workplace_data = job_attr.get('workplaceArrangement') or {}
    exp_years = job_attr.get('workExperienceYears') or {}
    insights = job_attr.get('insights') or {}

    workplace = workplace_data.get('displayedName')
    if not workplace:
        wp_match = re.search(r'/a/(On-Site|Hybrid|Remote)-Jobs', html_content)
        workplace = wp_match.group(1).replace('-', ' ') if wp_match else "Unspecified"

    description_text = ""
    if job_posting:
        description_text = clean_html(job_posting.get("description", ""))
    elif "description" in job_attr:
        description_text = clean_html(job_attr.get("description", "") + "\n" + job_attr.get("requirements", ""))

    title = job_attr.get('title') or (job_posting.get('title') if job_posting else "")
    if not title:
        h1 = page.locator("h1").first
        title = h1.inner_text() if h1.count() > 0 else ""

    company = ""
    location = ""
    country = ""
    date_posted = ""

    if job_posting:
        company = job_posting.get("hiringOrganization", {}).get("name", "").strip()
        address = job_posting.get("jobLocation", {}).get("address", {})
        location = address.get("addressRegion", "")
        country = address.get("addressCountry", "")
        date_posted = job_posting.get("datePosted", "")
        employment_type = job_posting.get("employmentType", [])

    return {
        "title": title,
        "company": company,
        "location": location,
        "country": country,
        "workplace": workplace,
        "seniority_level": career_lvl.get('name', 'Unspecified'),
        "seniority_hint": career_lvl.get('hint', ''),
        "skills_and_tools": skills,
        "years_of_experience": {
            "min": exp_years.get('min'),
            "max": exp_years.get('max')
        },
        "vacancies": job_attr.get('vacancies', 1),
        "applicants_count": insights.get('applied', 0),
        "education_level": (job_attr.get('candidatePreferences') or {}).get('educationLevel', {}).get('name', ''),
        "salary": salary_info,
        "application": {
            "type": job_attr.get('applicationType', 'internal'),
            "redirect_url": job_attr.get('redirectUrl')
        },
        "date_posted": date_posted or job_attr.get('postedAt', ''),
        "expire_at": job_attr.get('expireAt') or (job_posting.get('validThrough') if job_posting else ''),
        "details": description_text
    }

all_jobs_dict = {}
url_to_id_registry = {}

if output_jobs_file.exists():
    try:
        with output_jobs_file.open("r", encoding="utf-8") as f:
            for job in json.load(f):
                if isinstance(job, dict) and "job_id" in job and "url" in job:
                    all_jobs_dict[job["job_id"]] = job
                    url_to_id_registry[job["url"]] = job["job_id"]
        print(f"Loaded {len(all_jobs_dict)} existing jobs from {output_jobs_file.name}.")
    except Exception as e:
        print(f"Notice: Could not load existing data ({e}).")

if output_links_file.exists():
    try:
        with output_links_file.open("r", encoding="utf-8") as f:
            for item in json.load(f):
                if isinstance(item, dict) and "job_id" in item and "url" in item:
                    url_to_id_registry.setdefault(item["url"], item["job_id"])
    except Exception:
        pass

raw_links = []
i = 0

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("Collecting job links...")
    while True:
        url = (f"https://wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt?start={i}&filters%5Broles%5D%5B0%5D=IT%2FSoftware%20Development&ref=browse-jobs")
        
        page.goto(url, wait_until="domcontentloaded")
        first_try_links = page.locator("a.css-o171kl").evaluate_all(
            """elements => elements
                .map(element => element.href)
                .filter(href => href.includes("/jobs/p/"))"""
        )

        time.sleep(2)

        page.goto(url, wait_until="domcontentloaded")
        second_try_links = page.locator("a.css-o171kl").evaluate_all(
            """elements => elements
                .map(element => element.href)
                .filter(href => href.includes("/jobs/p/"))"""
        )

        links = first_try_links + second_try_links
        raw_links.extend(links)
        i += 1
        if not links: break

    unique_urls = list(dict.fromkeys(raw_links))
    
    formatted_links = []
    for u in unique_urls:
        job_id = get_consistent_job_id(u, url_to_id_registry)
        url_to_id_registry[u] = job_id
        formatted_links.append({"job_id": job_id, "url": u})

    print(f"Found {len(formatted_links)} links in this run.")

    with output_links_file.open("w", encoding="utf-8") as f:
        json.dump(formatted_links, f, ensure_ascii=False, indent=2)
    print(f"Overwrote latest links to {output_links_file.name}.")

    new_jobs_scraped = 0
    print("\nProcessing job offers...")

    for idx, item in enumerate(formatted_links, start=1):
        job_id = item["job_id"]
        job_url = item["url"]

        if job_id in all_jobs_dict:
            print(f"[{idx}/{len(formatted_links)}] Skipping {job_id} (already saved).")
            continue

        print(f"[{idx}/{len(formatted_links)}] Scraping new job: {job_id}...")
        try:
            parsed_data = parse_job_page(page, job_url)
            parsed_data["job_id"] = job_id
            parsed_data["url"] = job_url

            all_jobs_dict[job_id] = parsed_data
            new_jobs_scraped += 1

            time.sleep(1)

        except Exception as e:
            print(f"  [!] Failed to scrape {job_url}: {e}")

    browser.close()

with output_jobs_file.open("w", encoding="utf-8") as f:
    json.dump(list(all_jobs_dict.values()), f, ensure_ascii=False, indent=2)

print(f"\nDone! Added {new_jobs_scraped} new jobs. Total dataset now has {len(all_jobs_dict)} jobs in {output_jobs_file.name}.")
