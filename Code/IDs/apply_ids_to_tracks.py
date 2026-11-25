#!/usr/bin/env python3
"""
Applies Canonical IDs to Track Roadmap Files
============================================
This script:
1. Loads Code/IDs/tracks_ids.json and Code/IDs/skills_ids.json
2. Reads each of the 33 track JSON files in Code/json/
3. Replaces old/canvas IDs with canonical IDs:
   - track_id -> from tracks_ids.json
   - skill_id -> from skills_ids.json (for main skills, sub-skills, frameworks, related topics)
4. Leaves all ordering, resources, descriptions, and dependency structures 100% untouched.
"""

import os
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
CODE_DIR = CURRENT_DIR.parent
JSON_DIR = CODE_DIR / "json"
IDS_DIR = CURRENT_DIR

IGNORED_FILES = {
    "skills.json",
    "skills_from_roadmaps_with_progress.json",
    "description_review.json",
    "validation_report.json",
}

def clean_key(name):
    if not name:
        return ""
    return " ".join(name.strip().split()).lower()

def main():
    print("=" * 60)
    print("Applying Canonical IDs to Track Files...")
    print("=" * 60)

    # 1. Load ID maps
    with open(IDS_DIR / "skills_ids.json", "r", encoding="utf-8") as f:
        skills_data = json.load(f)
    with open(IDS_DIR / "tracks_ids.json", "r", encoding="utf-8") as f:
        tracks_data = json.load(f)

    skill_map = {clean_key(s["skill_name"]): s["skill_id"] for s in skills_data}
    track_map = {clean_key(t["track_name"]): t["track_id"] for t in tracks_data}

    track_files = [
        f for f in os.listdir(JSON_DIR)
        if f.endswith(".json") and f not in IGNORED_FILES
    ]
    track_files.sort()

    updated_skills_count = 0

    def update_skill_tree(s):
        nonlocal updated_skills_count
        name = s.get("skill_name")
        key = clean_key(name)
        if key in skill_map:
            s["skill_id"] = skill_map[key]
            updated_skills_count += 1
        for sub in s.get("sub_skills", []):
            update_skill_tree(sub)

    # 2. Process each track file
    for filename in track_files:
        file_path = JSON_DIR / filename
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Update track_id
        track_name = data.get("track_name", filename.replace(".json", ""))
        track_key = clean_key(track_name)
        if track_key in track_map:
            data["track_id"] = track_map[track_key]

        # Update main skills and sub-skills
        for skill in data.get("skills", []):
            update_skill_tree(skill)

        # Update frameworks
        for framework in data.get("frameworks", []):
            for fw_skill in framework.get("skills", []):
                update_skill_tree(fw_skill)

        # Update related topics
        for topic in data.get("related_topics", []):
            for topic_skill in topic.get("skills", []):
                update_skill_tree(topic_skill)

        # Save back to file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Successfully updated {len(track_files)} files!")
    print(f"Total skills updated with canonical IDs: {updated_skills_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()
