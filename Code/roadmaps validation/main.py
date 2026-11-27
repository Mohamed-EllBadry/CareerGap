import json
import re
from collections import defaultdict
from urllib.parse import urlparse
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
FILE_PATH = BASE_DIR / "skills_from_roadmaps_with_progress.json"

with open(FILE_PATH, "r", encoding="utf-8") as file:
    data = json.load(file)

required_fields = [
    "skill_id",
    "skill_name",
    "skill_content",
    "tracks",
    "sub_skill_name",
    "is_learnt"
]

issues = []


def get_tracks(record):
    tracks = record.get("tracks", [])
    if isinstance(tracks, list):
        return tracks
    elif isinstance(tracks, dict):
        return [tracks]
    return []


def normalize(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def add_issue(issue_type, record, details):
    tracks = get_tracks(record)
    track_names = [t.get("track_name") for t in tracks if isinstance(t, dict)]
    skill_counts = [t.get("skill_count") for t in tracks if isinstance(t, dict)]
    issues.append({
        "issue_type": issue_type,
        "skill_id": record.get("skill_id"),
        "skill_name": record.get("skill_name"),
        "track_name": ", ".join(map(str, track_names)),
        "skill_count": ", ".join(map(str, skill_counts)),
        "details": details
    })


for record in data:
    for field in required_fields:
        if field not in record:
            add_issue("Missing Field", record, field)

    for field in ["skill_id", "skill_name", "skill_content"]:
        value = record.get(field)
        if value is None or str(value).strip() == "":
            add_issue("Empty Value", record, field)
        elif str(value).strip().upper() == "NAN":
            add_issue("NAN Value", record, f"NAN found in field: {field}")


for record in data:
    skill_id = record.get("skill_id")
    if not isinstance(skill_id, str) or not re.fullmatch(r"[a-f0-9]{64}", skill_id):
        add_issue("Invalid Skill ID", record, str(skill_id))


ids = defaultdict(list)

for record in data:
    ids[record.get("skill_id")].append(record)

for skill_id, records in ids.items():
    if len(records) > 1:
        tracks = []
        for record in records:
            for track in get_tracks(record):
                if isinstance(track, dict):
                    tracks.append(track.get("track_name"))
        add_issue(
            "Duplicate ID",
            records[0],
            f"ID: {skill_id}, Occurrences: {len(records)}, Tracks: {tracks}"
        )


track_skill_pairs = defaultdict(list)

for record in data:
    skill_id = record.get("skill_id")
    for track in get_tracks(record):
        if isinstance(track, dict):
            track_skill_pairs[(track.get("track_name"), skill_id)].append(record)

for (track_name, skill_id), records in track_skill_pairs.items():
    if len(records) > 1:
        add_issue(
            "Same ID in Same Track",
            records[0],
            f"Track: {track_name}, ID: {skill_id}, Occurrences: {len(records)}"
        )


for skill_id, records in ids.items():
    if len(records) > 1:
        contents = set(str(r.get("skill_content")) for r in records)
        names = set(str(r.get("skill_name")) for r in records)
        subskills = set(str(r.get("sub_skill_name")) for r in records)
        if len(contents) > 1 or len(names) > 1 or len(subskills) > 1:
            add_issue(
                "ID Content Mismatch",
                records[0],
                f"Names: {names}, Subskills: {subskills}, Different Contents: {len(contents)}"
            )


def is_empty_sub(value):
    return normalize(value) in ("", "nan", "none")


skills_in_track = defaultdict(list)

for record in data:
    for track in get_tracks(record):
        if isinstance(track, dict):
            key = (track.get("track_name"), normalize(record.get("skill_name")))
            skills_in_track[key].append(record)

duplicate_rows = []

for (track_name, skill_name), records in skills_in_track.items():
    if len({r.get("skill_id") for r in records}) < 2:
        continue

    empty_sub = [r for r in records if is_empty_sub(r.get("sub_skill_name"))]
    same_sub = [r for r in records if normalize(r.get("sub_skill_name")) == skill_name]

    if empty_sub and same_sub:
        first = empty_sub[0]
        second = same_sub[0]

        def count_in_track(record):
            for track in get_tracks(record):
                if isinstance(track, dict) and track.get("track_name") == track_name:
                    return track.get("skill_count")

        duplicate_rows.append({
            "Track": track_name,
            "Skill Name": second.get("skill_name"),
            "Sub Skill Record 1": first.get("sub_skill_name"),
            "Skill Count Record 1": count_in_track(first),
            "ID Record 1": first.get("skill_id"),
            "Sub Skill Record 2": second.get("sub_skill_name"),
            "Skill Count Record 2": count_in_track(second),
            "ID Record 2": second.get("skill_id")
        })
        add_issue(
            "Same Skill In Same Track With Different ID",
            second,
            f"Track: {track_name}, IDs: {[first.get('skill_id'), second.get('skill_id')]}"
        )


track_counts = defaultdict(list)

for record in data:
    for track in get_tracks(record):
        if isinstance(track, dict):
            track_counts[track.get("track_name")].append(track.get("skill_count"))

for track_name, counts in track_counts.items():
    valid_counts = sorted(c for c in counts if isinstance(c, int))
    expected = list(range(1, len(valid_counts) + 1))
    if valid_counts != expected:
        issues.append({
            "issue_type": "Invalid Skill Count Sequence",
            "skill_id": None,
            "skill_name": None,
            "track_name": track_name,
            "skill_count": None,
            "details": f"Expected: {expected}, Actual: {valid_counts}"
        })


for record in data:
    for track in get_tracks(record):
        if not isinstance(track, dict):
            continue

        resources = track.get("resources", [])

        if not isinstance(resources, list):
            add_issue(
                "Invalid Resources Format",
                record,
                f"Resources should be a list, got {type(resources).__name__}"
            )
            continue

        for resource in resources:
            if not isinstance(resource, dict):
                add_issue("Invalid Resource Format", record, str(resource))
                continue

            url = resource.get("url")

            if url is None or str(url).strip() == "" or str(url).strip().upper() == "NAN":
                add_issue("Missing Resource URL", record, resource.get("title"))
                continue

            parsed = urlparse(str(url).strip())

            if parsed.scheme not in ["http", "https"] or not parsed.netloc:
                add_issue("Invalid URL", record, str(url))


df = pd.DataFrame(issues)

OUTPUT_PATH = BASE_DIR / "validation_issues.csv"

df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

DUP_PATH = BASE_DIR / "duplicate_skills_same_track.csv"
pd.DataFrame(duplicate_rows).to_csv(DUP_PATH, index=False, encoding="utf-8-sig")

print("Total Records:", len(data))
print("Total Issues:", len(issues))

if not df.empty:
    print(df["issue_type"].value_counts())
else:
    print("No issues found!")

print("Report saved at:", OUTPUT_PATH)
