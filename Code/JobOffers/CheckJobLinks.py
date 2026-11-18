import json
from pathlib import Path
from playwright.sync_api import sync_playwright

folder = Path(__file__).parent
input_file = folder / "job_links.json"
output_file = folder / "accessible_job_links.json"

with input_file.open("r", encoding="utf-8") as file:
    job_links = json.load(file)

available_links = []
removed_links = []
total = len(job_links)

with sync_playwright() as p:
    request = p.request.new_context()

    for index, link in enumerate(job_links, start=1):
        statuses = []

        for attempt in range(2):
            try:
                response = request.get(link, timeout=15000)
                statuses.append(response.status)
            except Exception:
                statuses.append(None)

        if len(statuses) == 2 and all(status in (404, 410) for status in statuses):
            removed_links.append(link)
        else:
            available_links.append(link)

        print(f"Checked {index}/{total} links")

    request.dispose()

for path in (input_file, output_file):
    with path.open("w", encoding="utf-8") as file:
        json.dump(available_links, file, ensure_ascii=False, indent=2)

print(f"Available: {len(available_links)} | Removed: {len(removed_links)}")