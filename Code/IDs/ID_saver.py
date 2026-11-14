import json
import os

code_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

input_folder = os.path.join(code_directory, "json")
output_folder = os.path.join(code_directory, "IDs")
os.makedirs(output_folder, exist_ok=True)

with open(os.path.join(input_folder, "skills.json"), encoding="utf-8") as f:
    data = json.load(f)

skills = [{"skill_id": s["skill_id"], "skill_name": s["skill_name"]} for s in data]

tracks = {}
for s in data:
    for t in s["tracks"]:
        tracks[t["track_id"]] = {"track_id": t["track_id"], "track_name": t["track_name"]}

with open(os.path.join(output_folder, "skills_ids.json"), "w", encoding="utf-8") as f:
    json.dump(skills, f, indent=2, ensure_ascii=False)

with open(os.path.join(output_folder, "tracks_ids.json"), "w", encoding="utf-8") as f:
    json.dump(list(tracks.values()), f, indent=2, ensure_ascii=False)