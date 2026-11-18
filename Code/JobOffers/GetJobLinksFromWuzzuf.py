import sys
import json
import time
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

output_file = Path(__file__).with_name("job_links.json")
if output_file.exists():
    with output_file.open("r", encoding="utf-8") as file:
        job_links = json.load(file)
else: job_links = []

i = 0
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    while True:
        url = (f"https://wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt?start={i}&filters%5Broles%5D%5B0%5D=IT%2FSoftware%20Development&ref=browse-jobs")
        
        page.goto(url, wait_until="domcontentloaded")
        first_try_links = page.locator("a.css-o171kl").evaluate_all(
            """elements => elements
                .map(element => element.href)
                .filter(href => href.includes("/jobs/p/"))"""
        )

        time.sleep(2) # to try again after 2 seconds

        page.goto(url, wait_until="domcontentloaded")
        second_try_links = page.locator("a.css-o171kl").evaluate_all(
            """elements => elements
                .map(element => element.href)
                .filter(href => href.includes("/jobs/p/"))"""
        )

        links = first_try_links + second_try_links

        job_links.extend(links)
        i += 1
        if not links: break

    browser.close()

job_links = list(dict.fromkeys(job_links)) #delete any duplicated links

with output_file.open("w", encoding="utf-8") as file:
    json.dump(job_links, file, ensure_ascii=False, indent=2)

print(f"Saved {len(job_links)} job links to {output_file}")

# subprocess.run(
#     [sys.executable, str(Path(__file__).with_name("CheckJobLinks.py"))],
#     check=True,
# )