# Roadmaps Validation

This folder has the script we use to check the roadmaps skills file
(skills_from_roadmaps_with_progress.json).

## Files

- main.py : the validation script
- validation_issues.csv : all issues found by the script
- duplicate_skills_same_track.csv : skills repeated inside the same track with a different ID
- Track Explorer (HTML) : shows one track as a tree with filters

## How to run

1. Put main.py next to skills_from_roadmaps_with_progress.json
2. Install pandas: pip install pandas
3. Run: python main.py
4. Close the CSV files before running, or Windows will block writing them

## What the script checks

- Missing fields and empty values
- NAN values
- Invalid skill IDs
- Duplicate IDs, and the same ID twice in one track
- Same ID with different content
- Skill count order inside each track
- Missing or invalid resource links
- Same skill repeated in the same track with a different ID
  (one record has no sub-skill and the other has the skill name as its sub-skill)

## Result of the last run

- Records: 3816
- Issues: 349
- Duplicate skills in the same track with different IDs: 8 rows, 7 skills
  (Internet appears in frontend and backend with the same IDs)
