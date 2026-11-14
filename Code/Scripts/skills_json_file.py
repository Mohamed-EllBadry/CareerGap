import os
import re
import sys
import json
import time
import secrets

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')

module_directory = os.path.dirname(os.path.abspath(__file__))
code_directory = os.path.dirname(module_directory)
project_root = os.path.dirname(code_directory)

def parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description='Generate a SQL-friendly skills JSON file from roadmap Markdown files.'
    )
    parser.add_argument(
        '--roadmaps-dir',
        help='Path to the extracted roadmaps directory (the folder containing track folders).',
    )
    parser.add_argument(
        '--output-dir',
        default=os.path.join(code_directory, 'json'),
        help='Directory for generated JSON and validation reports (default: ../json).',
    )
    parser.add_argument(
        '--ids-dir',
        default=os.path.join(code_directory, 'IDs'),
        help='Directory holding skills.json and tracks.json with the constant IDs (default: ../IDs).',
    )
    return parser.parse_args()


args = parse_args()


def resolve_roadmaps_directory(value):
    if value:
        candidate = os.path.abspath(os.path.expanduser(value))
        if not os.path.isdir(candidate):
            raise FileNotFoundError(f'Roadmaps directory does not exist: {candidate}')
        return candidate

    candidates = [
        os.path.join(project_root, 'DB', 'roadmap.sh', 'src', 'data', 'roadmaps'),
    ]

    # CAUTION: The following commented-out candidates are not used because they may lead to incorrect paths in some environments. Uncomment and adjust as needed.
    # candidates = [
    #     os.path.join(module_directory, 'roadmaps'),
    #     os.path.join(module_directory, 'src', 'data', 'roadmaps'),
    #     os.path.join(module_directory, 'data', 'roadmaps'),
    # ]

    for candidate in candidates:
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)

    raise FileNotFoundError(
        'Could not find the roadmaps directory automatically. '
        'Pass its path with --roadmaps-dir.'
    )


roadmap_directory = resolve_roadmaps_directory(args.roadmaps_dir)
output_directory = os.path.abspath(os.path.expanduser(args.output_dir))
output_file = os.path.join(output_directory, 'skills.json')

ids_directory = os.path.abspath(os.path.expanduser(args.ids_dir))
skills_ids_file = os.path.join(ids_directory, 'skills_ids.json')
tracks_ids_file = os.path.join(ids_directory, 'tracks_ids.json')

road_maps_nodes_count = {}
skills_map = {}

start = time.time()

def id_generator():
    return secrets.token_hex(32)

def load_id_file(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f'{path} must contain a JSON array.')
    return data


skills_ids_list = load_id_file(skills_ids_file)
tracks_ids_list = load_id_file(tracks_ids_file)

skill_id_by_key = {}
track_id_by_name = {}


def get_skill_id(skill_name, key):
    if key not in skill_id_by_key:
        new_id = id_generator()
        skill_id_by_key[key] = new_id
        skills_ids_list.append({'skill_id': new_id, 'skill_name': skill_name})
        print(f'New skill ID created: {skill_name}')
    return skill_id_by_key[key]


def get_track_id(track_name):
    if track_name not in track_id_by_name:
        new_id = id_generator()
        track_id_by_name[track_name] = new_id
        tracks_ids_list.append({'track_id': new_id, 'track_name': track_name})
        print(f'New track ID created: {track_name}')
    return track_id_by_name[track_name]

def name_key(name):
    return re.sub(r'[\s\-/?:_.,()]', '', name)


for _item in skills_ids_list:
    skill_id_by_key.setdefault(name_key(_item['skill_name']), _item['skill_id'])
for _item in tracks_ids_list:
    track_id_by_name.setdefault(_item['track_name'], _item['track_id'])

def get_files(directory):
    result = []
    for entry in sorted(os.scandir(directory), key=lambda e: e.name):
        entry_path = os.path.join(directory, entry.name)

        if entry.is_dir():
            result.extend(get_files(entry_path))
        elif entry.is_file() and entry.name.endswith('.md'):
            result.append(entry_path)

    return result

def read_balanced(text, start, opening, closing):
    if start >= len(text) or text[start] != opening:
        return None, start

    depth = 0
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    return None, start


def iter_bullet_links(content):
    """Yield every inline link on Markdown bullet-list lines."""
    for line in content.splitlines():
        bullet = re.match(r'^\s*[-*+]\s+', line)
        if not bullet:
            continue

        index = bullet.end()
        while index < len(line):
            opening = line.find('[', index)
            if opening == -1:
                break
            title, after_title = read_balanced(line, opening, '[', ']')
            if title is None or after_title >= len(line) or line[after_title] != '(':
                index = opening + 1
                continue

            url, after_url = read_balanced(line, after_title, '(', ')')
            if url is None:
                index = after_title + 1
                continue

            yield title, url
            index = after_url


def clean_markdown_text(value):
    """Remove presentation syntax while retaining the source wording."""
    text = value.strip()

    # Images and inline links: retain their human-readable labels, not URLs.
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)

    # Remove HTML tags, Markdown emphasis/code/strike markers and escapes.
    text = re.sub(r'<\s*/?\s*[A-Za-z][^>]*>', '', text)
    text = re.sub(r'(?<!\w)(\*\*|__)(?=\S)|(?<=\S)(\*\*|__)(?!\w)', '', text)
    text = text.replace('**', '').replace('__', '')
    text = text.replace('~~', '').replace('`', '')
    # Remove emphasis delimiters, but preserve escaped literal symbols such as A\\* Search.
    text = re.sub(r'(?<!\w)(?<!\\)\*(?=\S)|(?<=\S)(?<!\\)\*(?!\w)', '', text)
    text = re.sub(r'(?<!\w)(?<!\\)_(?=\S)|(?<=\S)(?<!\\)_(?!\w)', '', text)
    text = re.sub(r'\\([\\`*_{}\[\]()#+\-.!])', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# Extract resources from markdown content (sanitizes malformed URLs).
# If the file has no links, the file's own content is used as the resource.
def get_resources(content, skill_name):
    resources = []
    seen = set()

    for raw_title, raw_url in iter_bullet_links(content):
        title = clean_markdown_text(raw_title).rstrip(':').strip()
        clean_url = raw_url.strip() if raw_url else ''

        # Fix unclosed parentheses in URLs (e.g., Wikipedia links missing trailing ')')
        if '(' in clean_url and not clean_url.endswith(')'):
            open_count = clean_url.count('(')
            close_count = clean_url.count(')')
            if open_count > close_count:
                clean_url += ')'

        # Strip wrapping angle brackets if present
        clean_url = re.sub(r'^<|>\Z', '', clean_url)

        # Skip in-page jump links (#section), they are not resources.
        if clean_url.startswith('#'):
            continue

        # Site-relative links (/golang) become full roadmap.sh links.
        if clean_url.startswith('/'):
            clean_url = 'https://roadmap.sh' + clean_url

        resource = {'title': title, 'url': clean_url, 'content': 'NAN'}

        # Skip a link already added from this file.
        key = (resource['title'], resource['url'])
        if key in seen:
            continue
        seen.add(key)
        resources.append(resource)

    # No URLs found: write the Markdown content itself into rsc.
    if not resources:
        has_text = any(
            line.strip() and not re.match(r'^#{1,6}(\s|$)', line.strip())
            for line in content.split('\n')
        )
        if has_text:
            resources.append({
                'title': skill_name,
                'url': 'NAN',
                'content': content.strip(),
            })

    return resources

# Extract skill name from markdown heading
def get_skill_name(content):
    lines = content.split('\n')

    first_heading = next(
        (line for line in lines if re.match(r'^#\s+', line)),
        None,
    )

    # Fix 2: no "# " heading, use the first heading of any level (## to ######)
    if not first_heading:
        first_heading = next(
            (line for line in lines if re.match(r'^#{2,6}\s+', line)),
            None,
        )

    if not first_heading:
        return None

    name = re.sub(r'^#{1,6}\s+', '', first_heading).strip()

    # Fix 3: clean markdown leftovers from the name
    name = re.sub(r'\s+#+\s*$', '', name)  # closing hashes: "C++11 ###"
    name = re.sub(r'\\+([\\`*_{}\[\]()#+\-.!])', r'\1', name)  # escapes: "A\* Algorithm"
    name = name.replace('`', '')  # backticks

    return name.strip().lower()


# Extract a useful description from text already present in the Markdown file.
# Weak lead-ins are skipped in favor of the following source text. If no better
# text exists, leave the description empty for review rather than inventing one.
description_review = []
missing_track_directories = []


def get_skill_content(content, skill_name, source_file=''):
    try:
        lines = content.split('\n')

        heading_index = next(
            (i for i, line in enumerate(lines) if re.match(r'^#\s+', line)),
            None,
        )
        if heading_index is None:
            heading_index = next(
                (i for i, line in enumerate(lines) if re.match(r'^#{2,6}\s+', line)),
                None,
            )
        if heading_index is None:
            return ''

        in_code = False
        weak_reasons = []
        index = heading_index + 1

        while index < len(lines):
            raw = lines[index].strip()
            line_number = index + 1

            if raw.startswith('```'):
                in_code = not in_code
                index += 1
                continue
            if in_code or not raw:
                index += 1
                continue
            if re.match(r'^#{1,6}(\s|$)', raw):
                # Do not borrow a description from an unrelated subsection
                # after discovering that the opening text was only a lead-in.
                if weak_reasons:
                    break
                index += 1
                continue
            if re.match(r'^visit the following', raw, re.I):
                index += 1
                continue
            if re.match(r'^[-*+]\s+\[[^]]+\]\([^)]*\)', raw):
                index += 1
                continue

            if raw.endswith(':'):
                # Keep any complete explanatory sentence before a list intro,
                # e.g. "Arithmetic operators ... numbers. Here is a summary:"
                prefix = re.match(
                    r'^(.*?[.!?])\s+(?:Here\b|The following\b|Below\b|Following\b|A list\b).*:$',
                    raw,
                    re.I,
                )
                if prefix and len(prefix.group(1).strip()) >= 30:
                    cleaned = clean_markdown_text(prefix.group(1))
                    if cleaned:
                        description_review.append({
                            'skill_name': skill_name,
                            'source_file': source_file,
                            'line': line_number,
                            'reason': 'removed a list-introduction phrase after a complete description',
                            'source_text': raw,
                            'action': 'kept the complete explanatory sentence from the same line',
                        })
                        return cleaned

                weak_reasons.append('description is only a list/introduction lead-in')
                index += 1
                continue

            if re.fullmatch(r'\*\*[^*]+\*\*', raw):
                weak_reasons.append('description is only a bold heading/label')
                index += 1
                continue

            # If a weak lead-in is followed by a Markdown list, use the list's
            # actual source items rather than only its first item.
            if weak_reasons and re.match(r'^[-*+]\s+', raw):
                items = []
                j = index
                while j < len(lines):
                    candidate = lines[j].rstrip()
                    stripped = candidate.strip()
                    if not stripped:
                        break
                    if re.match(r'^#{1,6}(\s|$)', stripped):
                        break
                    bullet = re.match(r'^\s*[-*+]\s+(.*)$', candidate)
                    if bullet:
                        item = bullet.group(1).strip()
                        if re.match(r'^\[[^]]+\]\([^)]*\)', item):
                            j += 1
                            continue
                        cleaned_item = clean_markdown_text(item)
                        if cleaned_item:
                            items.append(cleaned_item)
                    elif candidate.startswith(('  ', '\t')) and items:
                        continuation = clean_markdown_text(stripped)
                        if continuation:
                            items[-1] += ' ' + continuation
                    else:
                        break
                    j += 1

                if items:
                    description_review.append({
                        'skill_name': skill_name,
                        'source_file': source_file,
                        'line': line_number,
                        'reason': '; '.join(weak_reasons),
                        'source_text': raw,
                        'action': 'used the following source list items as the description',
                    })
                    return '\n'.join(items)

            cleaned = clean_markdown_text(raw)
            if cleaned:
                cleaned = re.sub(r'^[-*+]\s+', '', cleaned).strip()
                if weak_reasons:
                    description_review.append({
                        'skill_name': skill_name,
                        'source_file': source_file,
                        'line': line_number,
                        'reason': '; '.join(weak_reasons),
                        'source_text': raw,
                        'action': 'used following source text as description',
                    })
                return cleaned

            index += 1

        if weak_reasons:
            description_review.append({
                'skill_name': skill_name,
                'source_file': source_file,
                'reason': '; '.join(weak_reasons),
                'source_text': '',
                'action': 'no better description exists in this Markdown file; left empty for review',
            })
        return ''
    except Exception as error:
        description_review.append({
            'skill_name': skill_name,
            'source_file': source_file,
            'reason': f'description extraction error: {error}',
            'source_text': '',
            'action': 'left empty for manual review',
        })
        return ''

# Merge differences into the first occurrence of a skill
def merge_skill(existing_skill, skill_content, track):
    # Add new skill content only if it doesn't already exist
    if skill_content and skill_content not in existing_skill['skill_content']:
        existing_skill['skill_content'] = '\n'.join(
            part for part in [existing_skill['skill_content'], skill_content] if part
        )
        existing_skill['skill_content'] = '\n'.join(
            clean_markdown_text(part) for part in existing_skill['skill_content'].splitlines() if part.strip()
        )

    # Check if the track already exists
    existing_track = next(
        (t for t in existing_skill['tracks'] if t['track_name'] == track['track_name']),
        None,
    )

    if existing_track:
        # Merge only new resources into the existing track (checking title and url)
        old_rsc = existing_track['rsc']
        existing_track['rsc'] = old_rsc + [
            resource for resource in track['rsc']
            if not any(
                existing['title'] == resource['title'] and existing['url'] == resource['url']
                for existing in old_rsc
            )
        ]
    else:
        # Add the new track
        existing_skill['tracks'].append(track)


# Generate skills and merge duplicates
def generate_json_from_dir_files(slug):
    roadmap_files = os.path.abspath(os.path.join(roadmap_directory, slug))

    if not os.path.exists(roadmap_files):
        missing_track_directories.append(slug.split('/')[0])
        print(f'WARNING: Track content directory is missing and was skipped: {roadmap_files}', file=sys.stderr)
        return

    files = get_files(roadmap_files)

    for file in files:
        with open(file, 'r', encoding='utf8') as f:
            content = f.read()

        skill_name = get_skill_name(content)

        if not skill_name:
            continue

        # Fix 9: "readme" is a note about the roadmap, not a skill
        if skill_name == 'readme':
            continue

        # Fix 10: many files share this heading, so name the skill from the file name
        if skill_name == 'questions to ask':
            stem = os.path.splitext(os.path.basename(file))[0]
            stem = re.sub(r'^\d+-', '', stem).replace('-', ' ')
            skill_name = stem.strip().lower() or skill_name

        print(f'Extracting: {file}  ->  {skill_name}')

        # Track name is extracted from the directory structure
        relative_path = os.path.relpath(file, roadmap_files)
        track_name = slug.split('/')[0]

        review_start = len(description_review)
        skill_content = get_skill_content(content, skill_name, file)
        if not skill_content and not any(
            item.get('source_file') == file
            for item in description_review[review_start:]
        ):
            description_review.append({
                'skill_name': skill_name,
                'source_file': file,
                'reason': 'no usable description text found in the source Markdown file',
                'source_text': '',
                'action': 'left empty for manual review; no description was invented',
            })

        road_maps_nodes_count[track_name] = road_maps_nodes_count.get(track_name, 0) + 1

        track = {
            'track_id': get_track_id(track_name),
            'track_name': track_name,
            'skill_count': road_maps_nodes_count[track_name],
            'rsc': get_resources(content, skill_name),
        }


        # Fix 8: look the skill up by its cleaned key
        key = name_key(skill_name)

        # Check if the skill already exists
        if key in skills_map:
            existing_skill = skills_map[key]

            # Merge only the differences into the first skill occurrence
            merge_skill(existing_skill, skill_content, track)

            continue

        # Create a new skill
        skill = {
            'skill_id': get_skill_id(skill_name, key),
            'skill_name': skill_name,
            'skill_content': skill_content,
            'tracks': [track],
        }

        skills_map[key] = skill


def replace_empty_text_values(value):
    """Recursively replace empty textual values with the literal SQL-safe marker."""
    if isinstance(value, dict):
        return {key: replace_empty_text_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_empty_text_values(item) for item in value]
    if value is None:
        return 'NAN'
    if isinstance(value, str) and not value.strip():
        return 'NAN'
    return value


def validate_output(items):
    if not isinstance(items, list):
        raise ValueError('Top-level JSON value must be an array.')

    skill_ids = set()
    track_ids = {}
    resource_count = 0
    track_count = 0
    counts_by_track = {}
    for skill_index, skill in enumerate(items):
        required_skill = {'skill_id', 'skill_name', 'skill_content', 'tracks'}
        if set(skill) != required_skill:
            raise ValueError(f'Skill at index {skill_index} has an inconsistent schema.')
        if not isinstance(skill['skill_id'], str) or not skill['skill_id']:
            raise ValueError('skill_id must be a non-empty string.')
        if skill['skill_id'] in skill_ids:
            raise ValueError(f'Duplicate skill_id detected: {skill["skill_id"]}')
        skill_ids.add(skill['skill_id'])
        if not isinstance(skill['tracks'], list):
            raise ValueError(f'Skill at index {skill_index} has a non-array tracks value.')

        for track in skill['tracks']:
            required_track = {'track_id', 'track_name', 'skill_count', 'rsc'}
            if set(track) != required_track:
                raise ValueError(f'Inconsistent track schema under skill {skill["skill_id"]}.')
            if not isinstance(track['track_id'], str) or not track['track_id']:
                raise ValueError('track_id must be a non-empty string.')
            if track_ids.setdefault(track['track_id'], track['track_name']) != track['track_name']:
                raise ValueError(f'track_id {track["track_id"]} is used by more than one track name.')
            if not isinstance(track['track_name'], str) or not track['track_name']:
                raise ValueError('track_name must be a non-empty string.')
            if not isinstance(track['skill_count'], int) or isinstance(track['skill_count'], bool):
                raise ValueError('skill_count must remain an integer.')
            if not isinstance(track['rsc'], list):
                raise ValueError('Track rsc must remain an array.')
            counts_by_track.setdefault(track['track_name'], []).append(track['skill_count'])
            track_count += 1

            for resource in track['rsc']:
                if set(resource) != {'title', 'url', 'content'}:
                    raise ValueError('Every resource must contain exactly title, url, and content.')
                if not all(isinstance(resource[field], str) for field in ('title', 'url', 'content')):
                    raise ValueError('Resource title, url, and content must all be strings.')
                if any(not resource[field].strip() for field in ('title', 'url', 'content')):
                    raise ValueError('Empty resource text value found after NAN normalization.')
                resource_count += 1

    for track_name, counts in counts_by_track.items():
        if sorted(counts) != list(range(1, len(counts) + 1)):
            raise ValueError(f'skill_count values are not consecutive for track {track_name}.')

    return {
        'skills': len(items),
        'tracks': track_count,
        'unique_skill_ids': len(skill_ids),
        'unique_track_ids': len(track_ids),
        'resources': resource_count,
    }


# Main execution
try:
    if not os.path.exists(roadmap_directory):
        raise Exception(f'Roadmap directory not found: {roadmap_directory}')

    directories = [
        entry for entry in sorted(os.scandir(roadmap_directory), key=lambda e: e.name)
        if entry.is_dir()
    ]

    for d in directories:
        road_maps_nodes_count[d.name] = 0

        generate_json_from_dir_files(f'{d.name}/content')

    # Fix 7: if a track has real links, drop its text (content) entry
    for skill in skills_map.values():
        for track in skill['tracks']:
            if any(r.get('url') != 'NAN' for r in track['rsc']):
                track['rsc'] = [r for r in track['rsc'] if r.get('url') != 'NAN']

    # Recalculate skill_count after removing duplicates
    track_skills = {}

    for skill in skills_map.values():
        for track in skill['tracks']:
            track_skills.setdefault(track['track_name'], []).append(track)

    # Sort skills by their original position and assign consecutive positions
    for tracks in track_skills.values():
        tracks.sort(key=lambda t: t['skill_count'])

        for index, track in enumerate(tracks):
            track['skill_count'] = index + 1

    # Convert Map values into an array
    json_array = list(skills_map.values())

    # Create output directory
    os.makedirs(output_directory, exist_ok=True)

    # Normalize all empty textual values while preserving numeric fields and arrays.
    json_array = replace_empty_text_values(json_array)

    # Validate the complete SQL-friendly schema before writing anything.
    validation_summary = validate_output(json_array)
    json_string = json.dumps(json_array, indent=2, ensure_ascii=False, allow_nan=False)
    # Parse it back to ensure the serialized file is valid JSON.
    json.loads(json_string)

    with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json_string)
        f.write('\n')

    # Save the ID files (existing IDs untouched, new ones appended)
    os.makedirs(ids_directory, exist_ok=True)
    for path, items in ((skills_ids_file, skills_ids_list), (tracks_ids_file, tracks_ids_list)):
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
            f.write('\n')

    review_file = os.path.join(output_directory, 'description_review.json')
    with open(review_file, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(description_review, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')

    summary_file = os.path.join(output_directory, 'validation_report.json')
    all_resources = [
        resource for skill in json_array for track in skill['tracks']
        for resource in track['rsc']
    ]
    def count_nan_values(value):
        if isinstance(value, dict):
            return sum(count_nan_values(item) for item in value.values())
        if isinstance(value, list):
            return sum(count_nan_values(item) for item in value)
        return 1 if value == 'NAN' else 0

    validation_summary.update({
        'source_markdown_files': sum(
            1 for root, _, filenames in os.walk(roadmap_directory)
            for filename in filenames if filename.lower().endswith('.md')
        ),
        'track_names': sorted({track['track_name'] for skill in json_array for track in skill['tracks']}),
        'missing_track_directories': sorted(set(missing_track_directories)),
        'empty_skill_descriptions': sum(1 for skill in json_array if skill['skill_content'] == 'NAN'),
        'resources_with_url': sum(1 for resource in all_resources if resource['url'] != 'NAN'),
        'content_only_resources': sum(
            1 for resource in all_resources
            if resource['url'] == 'NAN' and resource['content'] != 'NAN'
        ),
        'description_review_items': len(description_review),
        'unresolved_description_review_items': sum(
            1 for item in description_review
            if 'no better description exists' in item.get('action', '')
            or 'manual review' in item.get('action', '')
        ),
        'nan_text_values': count_nan_values(json_array),
        'output_file': output_file,
    })
    with open(summary_file, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(validation_summary, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')

    print('\nGeneration completed successfully.')
    print(json.dumps(validation_summary, indent=2, ensure_ascii=False))

    if len(json_array) == 0:
        print(
            'WARNING: No skills were extracted. Check the directory paths and Markdown heading structure.',
            file=sys.stderr,
        )
except Exception as error:
    print(f'Error while generating skills: {error}', file=sys.stderr)
    sys.exit(1)