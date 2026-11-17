from pathlib import Path
import json
from playwright.sync_api import sync_playwright

output_file = Path(__file__).with_name("job_links.json")

url = (
    "https://wuzzuf.net/a/IT-Software-Development-Jobs-in-Egypt"
    "?start=0"
    "&filters[city][0]=Cairo"
    "&filters[roles][0]=IT%2FSoftware%20Development"
    "&ref=browse-jobs"
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.goto(url, wait_until="domcontentloaded")
    page.locator("a.css-o171kl").first.wait_for()

    links = page.locator("a.css-o171kl").evaluate_all(
        """elements => elements
            .map(element => element.href)
            .filter(href => href.includes("/jobs/p/"))"""
    )

    job_links = list(dict.fromkeys(links))
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(job_links, file, ensure_ascii=False, indent=2)
    browser.close()
    print(f"Job links saved to {output_file}")