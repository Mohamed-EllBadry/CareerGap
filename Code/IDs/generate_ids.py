#!/usr/bin/env python3
"""
Simple ID Generator for CareerGap
=================================
What this script does:
1. Reads all 33 track roadmap files in Code/json/
2. Ignores cache and non-track files (skills.json, validation_report.json, etc.)
3. Collects every unique Track name and Skill name (including sub-skills, frameworks, and related topics)
4. Generates a clean, unique 10-character alphanumeric ID for each one
5. Saves them into two clean lookup files:
   - Code/IDs/tracks_ids.json
   - Code/IDs/skills_ids.json
"""

import os
import json
import secrets
import string
from pathlib import Path

# ----------------------------------------------------------------------
# 1. SETUP PATHS AND SETTINGS
# ----------------------------------------------------------------------

CURRENT_DIR = Path(__file__).resolve().parent
CODE_DIR = CURRENT_DIR.parent
JSON_DIR = CODE_DIR / "json"
IDS_DIR = CURRENT_DIR

# Files inside Code/json/ that we MUST IGNORE (not track roadmaps)
IGNORED_FILES = {
    "skills.json",
    "skills_from_roadmaps_with_progress.json",
    "description_review.json",
    "validation_report.json",
}

# ----------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ----------------------------------------------------------------------

def generate_unique_id(existing_ids, length=10):
    """
    Generates a random 10-character alphanumeric ID (letters and numbers).
    Example: 'k9Xm2P8qL1'
    Ensures that the generated ID is never a duplicate.
    """
    characters = string.ascii_letters + string.digits
    while True:
        new_id = "".join(secrets.choice(characters) for _ in range(length))
        if new_id not in existing_ids:
            existing_ids.add(new_id)
            return new_id


def clean_name(name):
    """
    Cleans up extra spaces from a name.
    Example: '  Git   ' becomes 'Git'
    """
    if not name:
        return ""
    return " ".join(name.strip().split())


# ----------------------------------------------------------------------
# 3. MAIN SCRIPT
# ----------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Starting ID Generation from scratch...")
    print("=" * 60)

    # Find all track JSON files (excluding ignored files)
    track_files = [
        f for f in os.listdir(JSON_DIR)
        if f.endswith(".json") and f not in IGNORED_FILES
    ]
    track_files.sort()

    print(f"Found {len(track_files)} track roadmap files to process.\n")

    unique_tracks = {}
    unique_skills = {}
    used_ids = set()

    def record_skill(name):
        cleaned = clean_name(name)
        if cleaned:
            skill_key = cleaned.lower()
            if skill_key not in unique_skills:
                unique_skills[skill_key] = cleaned

    def record_skill_tree(s):
        """Recursively records a skill and all its sub-skills."""
        record_skill(s.get("skill_name"))
        for sub in s.get("sub_skills", []):
            record_skill_tree(sub)

    # Step 1: Scan all 33 track files and gather unique names
    for filename in track_files:
        file_path = JSON_DIR / filename
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Track Name
        track_name = clean_name(data.get("track_name", filename.replace(".json", "")))
        if track_name:
            track_key = track_name.lower()
            if track_key not in unique_tracks:
                unique_tracks[track_key] = track_name

        # 2. Main Skills (and their sub-skills)
        for skill in data.get("skills", []):
            record_skill_tree(skill)

        # 3. Frameworks (and their skills/sub-skills)
        for framework in data.get("frameworks", []):
            record_skill(framework.get("framework_name"))
            for fw_skill in framework.get("skills", []):
                record_skill_tree(fw_skill)

        # 4. Related Topics (and their skills/sub-skills)
        for topic in data.get("related_topics", []):
            record_skill(topic.get("related_name"))
            for topic_skill in topic.get("skills", []):
                record_skill_tree(topic_skill)

    print(f"Collected {len(unique_tracks)} unique tracks.")
    print(f"Collected {len(unique_skills)} unique skills (including all sub-skills, frameworks, and topics).")
    print("\nGenerating fresh alphanumeric IDs...")

    # Step 2: Build the Tracks ID list
    tracks_result = []
    for track_key in sorted(unique_tracks.keys()):
        display_name = unique_tracks[track_key]
        tracks_result.append({
            "track_id": generate_unique_id(used_ids),
            "track_name": display_name
        })

    # Step 3: Build the Skills ID list
    skills_result = []
    for skill_key in sorted(unique_skills.keys()):
        display_name = unique_skills[skill_key]
        skills_result.append({
            "skill_id": generate_unique_id(used_ids),
            "skill_name": display_name
        })

    # Step 4: Save the files into Code/IDs/
    tracks_output_file = IDS_DIR / "tracks_ids.json"
    skills_output_file = IDS_DIR / "skills_ids.json"

    with open(tracks_output_file, "w", encoding="utf-8") as f:
        json.dump(tracks_result, f, indent=2, ensure_ascii=False)

    with open(skills_output_file, "w", encoding="utf-8") as f:
        json.dump(skills_result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("SUCCESS! Files saved:")
    print(f"  1. {tracks_output_file} ({len(tracks_result)} tracks)")
    print(f"  2. {skills_output_file} ({len(skills_result)} skills)")
    print("=" * 60)


if __name__ == "__main__":
    main()
