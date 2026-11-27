Roadmaps Validation
===================

This folder checks the quality of the roadmaps skills data before we use it in the database.
The script reads skills_from_roadmaps_with_progress.json (3816 skill records across all tracks)
and writes two reports that show what is wrong and where.


What is inside
--------------
validate_roadmaps.py
    The validation script. It runs all the checks and writes the reports.

validation_issues.csv
    Every problem the script found, one row per problem.
    Columns: issue_type, skill_id, skill_name, track_name, skill_count, details

duplicate_skills_same_track.csv
    The skills that appear twice in the same track with two different IDs.
    One record has no sub-skill (NAN) and the other record has the skill name as its sub-skill.

track-explorer.html
    Opens one track JSON and shows it as a tree, with filters, so the data is easy to review.


Prerequisites
-------------
- Python 3
- pandas  (pip install pandas)
- skills_from_roadmaps_with_progress.json in the same folder as validate_roadmaps.py


How to run
----------
1. Put validate_roadmaps.py next to the JSON file.
2. Close any CSV file that is open in Excel, or Windows will not let the script overwrite it.
3. Run:  python validate_roadmaps.py
4. Open validation_issues.csv and duplicate_skills_same_track.csv.


What it checks
--------------
1. Missing fields and empty values in each skill record.
2. NAN values in skill_id, skill_name, or skill_content.
3. Invalid skill IDs (a valid ID is 64 hex characters).
4. Duplicate IDs: the same ID used by more than one record.
5. The same ID twice in the same track.
6. The same ID with different content, name, or sub-skill.
7. Skill count order inside each track (should be 1, 2, 3, ... with no gaps).
8. Resource links that are missing or are not real http/https URLs.
9. The same skill twice in the same track with different IDs.


Results of the last run
-----------------------
Records checked: 3816
Issues found: 349
    NAN Value                                     171
    Duplicate ID                                   95
    ID Content Mismatch                            70
    Same Skill In Same Track With Different ID      8
    Same ID in Same Track                           5

The 8 rows in the same-track check are 7 different skills
(Internet, JavaScript, Blockchain, Processes and Threads, C#, Developer Tools, Hooks).
Internet shows twice because it is in both the frontend and backend tracks with the same IDs.


Notes
-----
- The same skill appearing in different tracks with the same ID is normal and is not an error.
- The 7 skills above are real errors and need to be fixed in the data.
