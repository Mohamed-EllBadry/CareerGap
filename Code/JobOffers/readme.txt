AllOutScrapper.py
=====================

What it does:
  Collects tech job offers in Egypt from three sites (Wuzzuf, Indeed and
  LinkedIn) and puts them all into one clean, unified dataset. Every run adds
  the new jobs on top of what you already have, so nothing gets overwritten.
  It also checks whether old offers are still open, so you never end up
  handing people expired links.

What you need installed:
  - playwright (and a Chromium browser for it), used for Wuzzuf
  - python-jobspy, used for Indeed and LinkedIn
  - pandas (optional, only for the CSV export)

What you get (all saved next to the script):
  - jobs_data.json: the full history of every job ever scraped, active or not
  - job_links.json: only the links that are still live
  - jobs_data.csv: a flat spreadsheet version you can open in Excel
  - scraper_state.json: remembers where Indeed stopped, so the next run
    carries on deeper instead of starting over

How a run goes:
  1. Loads jobs_data.json so it knows what it already has. Old jobs that
     were saved without a "platform" are labeled automatically from their
     URL (wuzzuf.net, indeed.com or linkedin.com).
  2. Wuzzuf: opens a visible browser, walks through every page of the IT &
     Software Development listings in Egypt, then visits each new job and
     pulls out its details. Jobs it already has are skipped.
  3. Indeed: searches 45 tech-related keywords. Each keyword remembers its
     own offset, so every run grabs the next batch of results instead of the
     same ones again.
  4. LinkedIn: searches only 8 broad keywords with a small number of results
     and longer pauses between them, to stay under the radar and avoid bans.
  5. Link check: visits every saved link and sees if the offer has closed or
     expired. Dead ones are removed from job_links.json, but the job stays in
     jobs_data.json with is_active set to False, so you can still analyze it.
  6. Saves the JSON, the links file and the CSV, then prints a short summary
     (new jobs added, total size, active vs expired).

What each job record contains:
  job_id, platform, url, title, company, location, country, workplace
  (on-site / hybrid / remote), seniority level, skills and tools, years of
  experience (min and max), education level, salary (min, max, currency,
  period, or hidden), whether you apply on the platform or on the company's
  own site, the date posted, and the full description.

  Skills, experience, education and seniority are taken from the platform's
  own data when it has it. Otherwise the script reads them out of the job
  description text.

Settings you can change at the top of the file:
  - ENABLE_WUZZUF / ENABLE_INDEED / ENABLE_LINKEDIN: turn a site on or off
  - WUZZUF_MAX_PAGES: limit how many Wuzzuf pages to crawl (None = all)
  - INDEED_RESULTS_PER_QUERY and LINKEDIN_RESULTS_PER_QUERY: how many results
    to ask for per keyword
  - INDEED_SEARCH_QUERIES and LINKEDIN_SEARCH_QUERIES: the keywords searched
  - VERIFY_ACTIVE_LINKS: turn the expired-link check on or off
  - TECH_KEYWORDS: the list of skills the script looks for in descriptions

How to run it:
  python scrapping_all_test.py

Good to know:
  - The Wuzzuf part opens a real browser window, so don't close it mid-run.
  - Running LinkedIn too often can get you blocked (you'll see a 429 error in
    the output). If that happens, wait a while or turn LinkedIn off.
  - The link check goes through every saved job, so it gets slower as your
    database grows.