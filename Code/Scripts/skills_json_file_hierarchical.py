"""Generate hierarchy-aware CareerGap JSON from roadmap Markdown alone.

The combined roadmap Markdown controls track/skill/sub-skill names, hierarchy,
and order. Extracted roadmap files supply descriptions and resources only; their
folder/file ordering is never used as the learning order. This script does not
read or modify skills.json or skills_json_file.py.

Output records contain the existing-style IDs, skill content, tracks, skill
count, and resources, plus sub_skill_name. A track is a TRACK slug or, for a
standalone SKILL roadmap, that roadmap's slug. skill_count is the 1-based
preorder position of each node in that track. Deeper descendants are recorded
as a breadcrumb in sub_skill_name, e.g. "Module Bundlers > Vite". Each record
has is_learnt: leaf values default to false and are preserved from the previous
output on reruns; parent values are recalculated from all child values. This is
one JSON progress file, not separate progress for multiple platform users.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

NAN = "NAN"
DEFAULT_ROADMAPS = Path("/home/mo2/Projects/CareerGap/DB/roadmap.sh/src/data/roadmaps")
DEFAULT_ORDER_FILE = Path.home() / "Downloads" / "all_tracks_and_skills_combined.md"
DEFAULT_OUTPUT = Path("/home/mo2/Projects/CareerGap/Code/json/skills_from_roadmaps_with_progress.json")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate ordered track/skill/sub-skill JSON from roadmap Markdown."
    )
    parser.add_argument("--roadmaps-dir", type=Path, default=DEFAULT_ROADMAPS)
    parser.add_argument("--order-file", type=Path, default=DEFAULT_ORDER_FILE)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def word_key(text: str) -> str:
    """Order-insensitive key for headings whose folder slug reorders words."""
    words = re.findall(r"[a-z0-9]+", text.casefold())
    words = [word for word in words if not word.isdigit()]
    return " ".join(sorted(words))


def clean_markdown(text: str) -> str:
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]*)\)", r"\1", text)
    text = re.sub(r"<\s*/?\s*[A-Za-z][^>]*>", "", text)
    text = text.replace("**", "").replace("__", "").replace("~~", "").replace("`", "")
    text = re.sub(r"(?<!\w)(?<!\\)\*(?=\S)|(?<=\S)(?<!\\)\*(?!\w)", "", text)
    text = re.sub(r"(?<!\w)(?<!\\)_(?=\S)|(?<=\S)(?<!\\)_(?!\w)", "", text)
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_label(text: str) -> str:
    text = re.sub(r"\s+\[(?:shared|milestone)\]\s*$", "", text, flags=re.I)
    return text.strip().rstrip(" .")


def parse_order_file(path: Path) -> list[dict]:
    """Read the ordered hierarchy from numbered bullets and their indentation."""
    section_re = re.compile(r"^##\s+(TRACK|SKILL):\s+([^\s(]+)")
    bullet_re = re.compile(r"^(\s*)-\s+\d+(?:\.\d+)*\.\s+(.+?)\s*$")
    sections, current, stack = [], None, []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        section = section_re.match(line)
        if section:
            current = {"kind": section.group(1), "name": section.group(2), "nodes": [], "line": line_no}
            sections.append(current)
            stack = []
            continue
        if current is None:
            continue
        bullet = bullet_re.match(line)
        if not bullet:
            continue
        indent = len(bullet.group(1).replace("\t", "    "))
        node = {"name": clean_label(bullet.group(2)), "children": [], "line": line_no}
        while stack and stack[-1][0] >= indent:
            stack.pop()
        (stack[-1][1]["children"] if stack else current["nodes"]).append(node)
        stack.append((indent, node))
    if not sections:
        raise ValueError(f"No TRACK or SKILL sections found in {path}")
    return sections


def walk_nodes(nodes, ancestors=()):
    for node in nodes:
        node_path = ancestors + (node["name"],)
        yield node, node_path
        yield from walk_nodes(node["children"], node_path)


def get_heading(text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            return clean_markdown(match.group(1))
    return ""


def get_description(text: str) -> str:
    """Return the first prose paragraph after the first Markdown heading."""
    lines = text.splitlines()
    heading_seen = False
    in_code = False
    paragraph = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("```"):
            if paragraph:
                break
            in_code = not in_code
            continue
        if in_code:
            continue
        if re.match(r"^#{1,6}\s+", line):
            if heading_seen:
                break
            heading_seen = True
            continue
        if not heading_seen:
            continue
        if not line:
            if paragraph:
                break
            continue
        if re.match(r"^[-*+]\s+", line) or line.startswith((">", "|")):
            if paragraph:
                break
            continue
        paragraph.append(line)
    return clean_markdown(" ".join(paragraph))


def get_resources(text: str, fallback_title: str) -> list[dict]:
    """Extract Markdown links; retain source text if no links exist."""
    resources, seen = [], set()
    for match in re.finditer(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", text):
        title = clean_markdown(match.group(1)).rstrip(":").strip()
        url = match.group(2).strip()
        if not title or not url or url.startswith("#"):
            continue
        if url.startswith("/"):
            url = "https://roadmap.sh" + url
        key = (title, url)
        if key not in seen:
            seen.add(key)
            resources.append({"title": title, "url": url, "content": NAN})
    if resources:
        return resources
    if text.strip():
        return [{"title": fallback_title or NAN, "url": NAN, "content": text.strip()}]
    return []


def load_source_index(roadmaps_dir: Path) -> dict[str, list[dict]]:
    """Index source Markdown by title/stem; sorting is only a tie-breaker."""
    index: dict[str, list[dict]] = {}
    for track_dir in sorted(p for p in roadmaps_dir.iterdir() if p.is_dir()):
        content_dir = track_dir / "content"
        if not content_dir.is_dir():
            continue
        entries = []
        for source in sorted(content_dir.rglob("*.md")):
            try:
                text = source.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                text = source.read_text(encoding="utf-8", errors="replace")
            title = get_heading(text)
            stem = re.sub(r"^\d+-", "", source.stem).replace("-", " ")
            folder_names = [
                re.sub(r"^\d+-", "", part).replace("-", " ")
                for part in source.relative_to(content_dir).parts[:-1]
            ]
            entries.append({
                "path": source,
                "relative": source.relative_to(content_dir),
                "title": title,
                "text": text,
                "description": get_description(text),
                "rsc": get_resources(text, title),
                "title_key": normalize(title),
                "stem_key": normalize(stem),
                "title_words": word_key(title),
                "stem_words": word_key(stem),
                "folder_names": folder_names,
                "folder_words": [word_key(name) for name in folder_names],
            })
        index[track_dir.name] = entries
    return index


def source_for_node(entries: list[dict], node_path: tuple[str, ...]) -> dict | None:
    """Match a Markdown hierarchy label to source details without using source order."""
    if not entries:
        return None
    leaf_key = normalize(node_path[-1])
    leaf_words = word_key(node_path[-1])
    candidates = [
        entry for entry in entries
        if entry["title_key"] == leaf_key
        or entry["stem_key"] == leaf_key
        or (leaf_words and entry["title_words"] == leaf_words)
        or (leaf_words and entry["stem_words"] == leaf_words)
        or (leaf_words and entry["path"].name.casefold() == "index.md"
            and entry["folder_words"] and entry["folder_words"][-1] == leaf_words)
    ]
    if not candidates:
        return None

    def score(entry):
        path_parts = entry["folder_words"]
        value = 100 if entry["title_key"] == leaf_key else 70
        if entry["path"].name.casefold() == "index.md" and entry["folder_words"] \
                and entry["folder_words"][-1] == leaf_words:
            value += 150
        for ancestor in node_path[:-1]:
            ancestor_key = word_key(ancestor)
            if ancestor_key and ancestor_key in path_parts:
                value += 20
        is_index = entry["path"].name.casefold() == "index.md"
        if len(node_path) == 1:
            value += 15 if is_index else 0
        else:
            value += 15 if not is_index else 0
        return value

    return max(candidates, key=lambda entry: (score(entry), str(entry["path"])))


def stable_id(kind: str, value: str) -> str:
    return hashlib.sha256(f"careergap:{kind}:{value}".encode("utf-8")).hexdigest()


def node_key(item: dict) -> tuple[str, tuple[str, ...]]:
    track_name = item["tracks"][0]["track_name"]
    path = [normalize(item["skill_name"])]
    sub_skill = item.get("sub_skill_name", NAN)
    if sub_skill and sub_skill != NAN:
        path.extend(normalize(part.strip()) for part in sub_skill.split(" > "))
    return track_name, tuple(path)


def load_previous_progress(output_file: Path) -> dict[tuple[str, tuple[str, ...]], bool]:
    """Preserve completion values from the previous generated JSON, if present."""
    if not output_file.is_file():
        return {}
    try:
        previous = json.loads(output_file.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    statuses = {}
    if isinstance(previous, list):
        for item in previous:
            if isinstance(item, dict) and isinstance(item.get("is_learnt"), bool) \
                    and isinstance(item.get("tracks"), list) and item["tracks"]:
                statuses[node_key(item)] = item["is_learnt"]
    return statuses


def apply_learning_status(output: list[dict], saved_statuses: dict[tuple[str, tuple[str, ...]], bool]) -> None:
    """Preserve leaf statuses and derive every parent from all its children."""
    by_key = {node_key(item): item for item in output}
    children_by_parent: dict[tuple[str, tuple[str, ...]], list[tuple[str, tuple[str, ...]]]] = {}
    for key in by_key:
        track_name, path = key
        if len(path) > 1:
            parent_key = (track_name, path[:-1])
            children_by_parent.setdefault(parent_key, []).append(key)

    # Work from deepest nodes upward so parent values use already calculated children.
    for key in sorted(by_key, key=lambda value: len(value[1]), reverse=True):
        children = children_by_parent.get(key, [])
        if children:
            by_key[key]["is_learnt"] = all(by_key[child]["is_learnt"] for child in children)
        else:
            by_key[key]["is_learnt"] = saved_statuses.get(key, False)


def build_output(
    sections: list[dict],
    source_index: dict[str, list[dict]],
    saved_statuses: dict[tuple[str, tuple[str, ...]], bool],
) -> tuple[list[dict], list[dict]]:
    output, unmatched, empty_details, structural_without_source = [], [], [], []
    count_by_track: dict[str, int] = {}
    for section in sections:
        track_name = section["name"]
        entries = source_index.get(track_name, [])
        for node, node_path in walk_nodes(section["nodes"]):
            count_by_track[track_name] = count_by_track.get(track_name, 0) + 1
            source = source_for_node(entries, node_path)
            leaf = node_path[-1]
            root_skill = node_path[0]
            sub_skill = " > ".join(node_path[1:]) if len(node_path) > 1 else NAN
            resource_list = source["rsc"] if source else []
            item = {
                "skill_id": stable_id("skill", "/".join(normalize(part) for part in node_path)),
                "skill_name": root_skill,
                "skill_content": source["description"] if source and source["description"] else NAN,
                "tracks": [{
                    "track_id": stable_id("track", track_name),
                    "track_name": track_name,
                    "skill_count": count_by_track[track_name],
                    "rsc": resource_list,
                }],
                "sub_skill_name": sub_skill,
                "is_learnt": False,
            }
            output.append(item)
            if source is None:
                missing = {
                    "track_name": track_name,
                    "skill_name": root_skill,
                    "sub_skill_name": sub_skill,
                    "node_path": node_path,
                }
                if node["children"]:
                    structural_without_source.append(missing)
                else:
                    unmatched.append(missing)
            elif not source["description"] and not source["rsc"]:
                empty_details.append({
                    "track_name": track_name,
                    "skill_name": root_skill,
                    "sub_skill_name": sub_skill,
                    "source_file": str(source["path"]),
                })
    apply_learning_status(output, saved_statuses)
    return output, unmatched, empty_details, structural_without_source


def main() -> int:
    args = parse_args()
    roadmaps_dir = args.roadmaps_dir.expanduser().resolve()
    order_file = args.order_file.expanduser().resolve()
    output_file = args.output_file.expanduser().resolve()
    if not roadmaps_dir.is_dir():
        raise FileNotFoundError(f"Roadmaps directory not found: {roadmaps_dir}")
    if not order_file.is_file():
        raise FileNotFoundError(f"Combined Markdown order file not found: {order_file}")

    sections = parse_order_file(order_file)
    source_index = load_source_index(roadmaps_dir)
    saved_statuses = load_previous_progress(output_file)
    output, unmatched, empty_details, structural_without_source = build_output(
        sections, source_index, saved_statuses
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_file.with_suffix(output_file.suffix + ".tmp")
    temporary.write_text(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(output_file)

    print(f"Wrote {len(output)} ordered records to {output_file}")
    print(f"Used names/order from {order_file}; source detail folder: {roadmaps_dir}")
    if unmatched:
        print(f"WARNING: no source file matched {len(unmatched)} leaf records:", file=sys.stderr)
        for row in unmatched[:25]:
            sub = "" if row["sub_skill_name"] == NAN else row["sub_skill_name"]
            label = f"{row['skill_name']} > {sub}" if sub else row["skill_name"]
            print(f"  {row['track_name']}: {label}", file=sys.stderr)
        if len(unmatched) > 25:
            print(f"  ... and {len(unmatched) - 25} more", file=sys.stderr)
    if empty_details:
        print(f"WARNING: {len(empty_details)} matched source files have no description or resource links:", file=sys.stderr)
        for row in empty_details[:25]:
            sub = "" if row["sub_skill_name"] == NAN else row["sub_skill_name"]
            label = f"{row['skill_name']} > {sub}" if sub else row["skill_name"]
            print(f"  {row['track_name']}: {label} ({row['source_file']})", file=sys.stderr)
        if len(empty_details) > 25:
            print(f"  ... and {len(empty_details) - 25} more", file=sys.stderr)
    if structural_without_source:
        print(f"INFO: {len(structural_without_source)} parent/group nodes have no dedicated source file; their sub-skills are listed separately.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
