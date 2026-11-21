#!/usr/bin/env python3
"""
Reads roadmap.sh content files (markdown) + the roadmap structure (nodes/edges),
orders the skills using Option C: Hybrid Topological Edge Order guided by
pedagogical fundamental-to-advanced learning phases, attaches dedicated frameworks
to every primary track, and writes structured JSON output files.

Usage:
    python skills_builder.py --roadmap-slug frontend,backend
    python skills_builder.py --roadmap-slug __all__ --roadmaps-dir ./roadmaps
    python skills_builder.py --roadmap-slug frontend --json-dir ./roadmap_json   # offline
"""

import argparse
import copy
import json
import math
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict, deque
from pathlib import Path

# ---- CHOOSE WHAT TO BUILD ----
ROADMAP_SLUG = "__all__"

# True  -> one JSON file per track (frontend.json, backend.json, ...) in the output folder
# False -> everything in one file (roadmaps_ordered.json)
ONE_FILE_PER_TRACK = True

API_URL = "https://roadmap.sh/api/v1-official-roadmap/{}"
FILE_RE = re.compile(r"^(.+)@([^.]+)\.md$")
LINK_RE = re.compile(r"^\s*[-*]\s*\[@([a-z.]+)@(.*?)\]\((.*?)\)\s*$")
VISIT_RE = re.compile(r"^\s*Visit the following resources", re.IGNORECASE)

# In-memory track cache so shared framework roadmaps (e.g. Python, Docker)
# are parsed only once across tracks.
TRACK_CACHE = {}


# ---------- COMPREHENSIVE TRACK FRAMEWORKS & SPECIALIZATIONS ----------

TRACK_FRAMEWORKS = {
    "frontend": [
        {"framework_id": "react",         "framework_name": "React",                   "source_roadmap": "react"},
        {"framework_id": "vue",           "framework_name": "Vue.js",                  "source_roadmap": "vue"},
        {"framework_id": "angular",       "framework_name": "Angular",                 "source_roadmap": "angular"},
        {"framework_id": "nextjs",        "framework_name": "Next.js",                 "source_roadmap": "nextjs"},
        {"framework_id": "typescript",    "framework_name": "TypeScript",              "source_roadmap": "typescript"},
        {"framework_id": "javascript",    "framework_name": "JavaScript",              "source_roadmap": "javascript"},
        {"framework_id": "html",          "framework_name": "HTML",                    "source_roadmap": "html"},
        {"framework_id": "css",           "framework_name": "CSS",                     "source_roadmap": "css"},
        {"framework_id": "design-system", "framework_name": "Design System",            "source_roadmap": "design-system"},
        {"framework_id": "seo",           "framework_name": "SEO & Web Performance",    "source_roadmap": "seo"},
        {"framework_id": "wordpress",     "framework_name": "WordPress CMS",           "source_roadmap": "wordpress"},
        {"framework_id": "svelte",        "framework_name": "Svelte",                  "source_roadmap": None},
        {"framework_id": "solidjs",       "framework_name": "Solid JS",                "source_roadmap": None},
    ],
    "frontend-beginner": [
        {"framework_id": "html",                "framework_name": "HTML",                    "source_roadmap": "html"},
        {"framework_id": "css",                 "framework_name": "CSS",                     "source_roadmap": "css"},
        {"framework_id": "javascript",          "framework_name": "JavaScript",              "source_roadmap": "javascript"},
        {"framework_id": "git-github-beginner", "framework_name": "Git & GitHub Beginner",   "source_roadmap": "git-github-beginner"},
    ],
    "backend": [
        {"framework_id": "nodejs",        "framework_name": "Node.js",                 "source_roadmap": "nodejs"},
        {"framework_id": "python",        "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "django",        "framework_name": "Django",                  "source_roadmap": "django"},
        {"framework_id": "java",          "framework_name": "Java",                    "source_roadmap": "java"},
        {"framework_id": "spring-boot",   "framework_name": "Spring Boot",             "source_roadmap": "spring-boot"},
        {"framework_id": "golang",        "framework_name": "Go",                      "source_roadmap": "golang"},
        {"framework_id": "rust",          "framework_name": "Rust",                    "source_roadmap": "rust"},
        {"framework_id": "cpp",           "framework_name": "C++",                     "source_roadmap": "cpp"},
        {"framework_id": "c",             "framework_name": "C",                       "source_roadmap": "c"},
        {"framework_id": "aspnet-core",   "framework_name": "ASP.NET Core",            "source_roadmap": "aspnet-core"},
        {"framework_id": "php",           "framework_name": "PHP",                     "source_roadmap": "php"},
        {"framework_id": "laravel",       "framework_name": "Laravel",                 "source_roadmap": "laravel"},
        {"framework_id": "ruby",          "framework_name": "Ruby",                    "source_roadmap": "ruby"},
        {"framework_id": "ruby-on-rails", "framework_name": "Ruby on Rails",           "source_roadmap": "ruby-on-rails"},
        {"framework_id": "scala",         "framework_name": "Scala",                   "source_roadmap": "scala"},
        {"framework_id": "graphql",       "framework_name": "GraphQL",                 "source_roadmap": "graphql"},
        {"framework_id": "api-design",    "framework_name": "API Design",              "source_roadmap": "api-design"},
    ],
    "backend-beginner": [
        {"framework_id": "python",              "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "nodejs",              "framework_name": "Node.js",                 "source_roadmap": "nodejs"},
        {"framework_id": "sql",                 "framework_name": "SQL",                     "source_roadmap": "sql"},
        {"framework_id": "git-github-beginner", "framework_name": "Git & GitHub Beginner",   "source_roadmap": "git-github-beginner"},
    ],
    "full-stack": [
        {"framework_id": "react",         "framework_name": "React",                   "source_roadmap": "react"},
        {"framework_id": "nextjs",        "framework_name": "Next.js",                 "source_roadmap": "nextjs"},
        {"framework_id": "vue",           "framework_name": "Vue.js",                  "source_roadmap": "vue"},
        {"framework_id": "nodejs",        "framework_name": "Node.js",                 "source_roadmap": "nodejs"},
        {"framework_id": "python",        "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "django",        "framework_name": "Django",                  "source_roadmap": "django"},
        {"framework_id": "java",          "framework_name": "Java",                    "source_roadmap": "java"},
        {"framework_id": "spring-boot",   "framework_name": "Spring Boot",             "source_roadmap": "spring-boot"},
        {"framework_id": "aspnet-core",   "framework_name": "ASP.NET Core",            "source_roadmap": "aspnet-core"},
        {"framework_id": "laravel",       "framework_name": "Laravel",                 "source_roadmap": "laravel"},
        {"framework_id": "ruby-on-rails", "framework_name": "Ruby on Rails",           "source_roadmap": "ruby-on-rails"},
        {"framework_id": "graphql",       "framework_name": "GraphQL",                 "source_roadmap": "graphql"},
        {"framework_id": "wordpress",     "framework_name": "WordPress CMS",           "source_roadmap": "wordpress"},
    ],
    "android": [
        {"framework_id": "kotlin",       "framework_name": "Kotlin",                  "source_roadmap": "kotlin"},
        {"framework_id": "java",         "framework_name": "Java",                    "source_roadmap": "java"},
        {"framework_id": "flutter",      "framework_name": "Flutter",                 "source_roadmap": "flutter"},
        {"framework_id": "react-native", "framework_name": "React Native",             "source_roadmap": "react-native"},
    ],
    "ios": [
        {"framework_id": "swift-ui",     "framework_name": "SwiftUI",                 "source_roadmap": "swift-ui"},
        {"framework_id": "flutter",      "framework_name": "Flutter",                 "source_roadmap": "flutter"},
        {"framework_id": "react-native", "framework_name": "React Native",             "source_roadmap": "react-native"},
    ],
    "devops": [
        {"framework_id": "docker",          "framework_name": "Docker",                  "source_roadmap": "docker"},
        {"framework_id": "kubernetes",      "framework_name": "Kubernetes",              "source_roadmap": "kubernetes"},
        {"framework_id": "terraform",       "framework_name": "Terraform",               "source_roadmap": "terraform"},
        {"framework_id": "aws",             "framework_name": "AWS",                     "source_roadmap": "aws"},
        {"framework_id": "cloud-computing", "framework_name": "Cloud Computing",         "source_roadmap": "cloud-computing"},
        {"framework_id": "cloudflare",      "framework_name": "Cloudflare",              "source_roadmap": "cloudflare"},
        {"framework_id": "linux",           "framework_name": "Linux",                   "source_roadmap": "linux"},
        {"framework_id": "shell-bash",      "framework_name": "Shell / Bash",            "source_roadmap": "shell-bash"},
        {"framework_id": "git-github",      "framework_name": "Git & GitHub",            "source_roadmap": "git-github"},
    ],
    "devops-beginner": [
        {"framework_id": "linux",               "framework_name": "Linux",                   "source_roadmap": "linux"},
        {"framework_id": "shell-bash",          "framework_name": "Shell / Bash",            "source_roadmap": "shell-bash"},
        {"framework_id": "git-github-beginner", "framework_name": "Git & GitHub Beginner",   "source_roadmap": "git-github-beginner"},
        {"framework_id": "docker",              "framework_name": "Docker",                  "source_roadmap": "docker"},
    ],
    "devsecops": [
        {"framework_id": "docker",         "framework_name": "Docker",                  "source_roadmap": "docker"},
        {"framework_id": "kubernetes",     "framework_name": "Kubernetes",              "source_roadmap": "kubernetes"},
        {"framework_id": "cyber-security", "framework_name": "Cyber Security",          "source_roadmap": "cyber-security"},
        {"framework_id": "terraform",      "framework_name": "Terraform",               "source_roadmap": "terraform"},
        {"framework_id": "linux",          "framework_name": "Linux",                   "source_roadmap": "linux"},
    ],
    "data-engineer": [
        {"framework_id": "python",         "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "sql",            "framework_name": "SQL",                     "source_roadmap": "sql"},
        {"framework_id": "postgresql-dba", "framework_name": "PostgreSQL DBA",          "source_roadmap": "postgresql-dba"},
        {"framework_id": "mongodb",        "framework_name": "MongoDB",                 "source_roadmap": "mongodb"},
        {"framework_id": "redis",          "framework_name": "Redis",                   "source_roadmap": "redis"},
        {"framework_id": "elasticsearch",  "framework_name": "Elasticsearch",           "source_roadmap": "elasticsearch"},
        {"framework_id": "scala",          "framework_name": "Scala",                   "source_roadmap": "scala"},
        {"framework_id": "docker",         "framework_name": "Docker",                  "source_roadmap": "docker"},
    ],
    "data-analyst": [
        {"framework_id": "sql",                  "framework_name": "SQL",                     "source_roadmap": "sql"},
        {"framework_id": "python-data-analysis", "framework_name": "Python Data Analysis",   "source_roadmap": "python-data-analysis"},
        {"framework_id": "python",               "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "power-bi",             "framework_name": "Power BI",                "source_roadmap": "power-bi"},
        {"framework_id": "r-programming",        "framework_name": "R Programming",           "source_roadmap": "r-programming"},
    ],
    "bi-analyst": [
        {"framework_id": "power-bi",             "framework_name": "Power BI",                "source_roadmap": "power-bi"},
        {"framework_id": "sql",                  "framework_name": "SQL",                     "source_roadmap": "sql"},
        {"framework_id": "python-data-analysis", "framework_name": "Python Data Analysis",   "source_roadmap": "python-data-analysis"},
        {"framework_id": "r-programming",        "framework_name": "R Programming",           "source_roadmap": "r-programming"},
    ],
    "ai-data-scientist": [
        {"framework_id": "python",               "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "python-data-analysis", "framework_name": "Python Data Analysis",   "source_roadmap": "python-data-analysis"},
        {"framework_id": "sql",                  "framework_name": "SQL",                     "source_roadmap": "sql"},
        {"framework_id": "r-programming",        "framework_name": "R Programming",           "source_roadmap": "r-programming"},
        {"framework_id": "mlops",                "framework_name": "MLOps",                   "source_roadmap": "mlops"},
    ],
    "machine-learning": [
        {"framework_id": "python",               "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "python-data-analysis", "framework_name": "Python Data Analysis",   "source_roadmap": "python-data-analysis"},
        {"framework_id": "sql",                  "framework_name": "SQL",                     "source_roadmap": "sql"},
        {"framework_id": "mlops",                "framework_name": "MLOps",                   "source_roadmap": "mlops"},
    ],
    "ai-engineer": [
        {"framework_id": "ai-agents",            "framework_name": "AI Agents",               "source_roadmap": "ai-agents"},
        {"framework_id": "prompt-engineering",   "framework_name": "Prompt Engineering",      "source_roadmap": "prompt-engineering"},
        {"framework_id": "inference-engineering","framework_name": "Inference Engineering",   "source_roadmap": "inference-engineering"},
        {"framework_id": "mlops",                "framework_name": "MLOps",                   "source_roadmap": "mlops"},
        {"framework_id": "ai-red-teaming",       "framework_name": "AI Red Teaming",          "source_roadmap": "ai-red-teaming"},
        {"framework_id": "python",               "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "openclaw",             "framework_name": "OpenClaw Agent Platform", "source_roadmap": "openclaw"},
    ],
    "ai-product-builder": [
        {"framework_id": "prompt-engineering", "framework_name": "Prompt Engineering",      "source_roadmap": "prompt-engineering"},
        {"framework_id": "ai-agents",          "framework_name": "AI Agents",               "source_roadmap": "ai-agents"},
        {"framework_id": "cursor",             "framework_name": "Cursor AI",               "source_roadmap": "cursor"},
        {"framework_id": "claude-code",        "framework_name": "Claude Code",             "source_roadmap": "claude-code"},
        {"framework_id": "codex",              "framework_name": "Codex AI",                "source_roadmap": "codex"},
        {"framework_id": "vibe-coding",        "framework_name": "Vibe Coding",             "source_roadmap": "vibe-coding"},
    ],
    "qa": [
        {"framework_id": "python",     "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "javascript", "framework_name": "JavaScript",              "source_roadmap": "javascript"},
        {"framework_id": "typescript", "framework_name": "TypeScript",              "source_roadmap": "typescript"},
        {"framework_id": "api-design", "framework_name": "API Design",              "source_roadmap": "api-design"},
        {"framework_id": "git-github", "framework_name": "Git & GitHub",            "source_roadmap": "git-github"},
    ],
    "cyber-security": [
        {"framework_id": "linux",            "framework_name": "Linux",                   "source_roadmap": "linux"},
        {"framework_id": "network-engineer", "framework_name": "Network Engineer",         "source_roadmap": "network-engineer"},
        {"framework_id": "python",           "framework_name": "Python",                  "source_roadmap": "python"},
        {"framework_id": "shell-bash",        "framework_name": "Shell / Bash",            "source_roadmap": "shell-bash"},
        {"framework_id": "devsecops",        "framework_name": "DevSecOps",               "source_roadmap": "devsecops"},
    ],
    "game-developer": [
        {"framework_id": "cpp",                        "framework_name": "C++",                        "source_roadmap": "cpp"},
        {"framework_id": "c",                          "framework_name": "C",                          "source_roadmap": "c"},
        {"framework_id": "rust",                       "framework_name": "Rust",                       "source_roadmap": "rust"},
        {"framework_id": "server-side-game-developer", "framework_name": "Server-Side Game Developer", "source_roadmap": "server-side-game-developer"},
    ],
    "server-side-game-developer": [
        {"framework_id": "cpp",    "framework_name": "C++",     "source_roadmap": "cpp"},
        {"framework_id": "rust",   "framework_name": "Rust",    "source_roadmap": "rust"},
        {"framework_id": "golang", "framework_name": "Go",      "source_roadmap": "golang"},
        {"framework_id": "nodejs", "framework_name": "Node.js", "source_roadmap": "nodejs"},
    ],
    "blockchain": [
        {"framework_id": "rust",       "framework_name": "Rust",       "source_roadmap": "rust"},
        {"framework_id": "golang",     "framework_name": "Go",         "source_roadmap": "golang"},
        {"framework_id": "typescript", "framework_name": "TypeScript", "source_roadmap": "typescript"},
        {"framework_id": "javascript", "framework_name": "JavaScript", "source_roadmap": "javascript"},
    ],
    "software-architect": [
        {"framework_id": "system-design", "framework_name": "System Design", "source_roadmap": "system-design"},
        {"framework_id": "api-design",    "framework_name": "API Design",    "source_roadmap": "api-design"},
        {"framework_id": "design-system", "framework_name": "Design System", "source_roadmap": "design-system"},
        {"framework_id": "code-review",   "framework_name": "Code Review",   "source_roadmap": "code-review"},
    ],
    "software-design-architecture": [
        {"framework_id": "system-design", "framework_name": "System Design", "source_roadmap": "system-design"},
        {"framework_id": "api-design",    "framework_name": "API Design",    "source_roadmap": "api-design"},
        {"framework_id": "code-review",   "framework_name": "Code Review",   "source_roadmap": "code-review"},
    ],
    "network-engineer": [
        {"framework_id": "linux",          "framework_name": "Linux",          "source_roadmap": "linux"},
        {"framework_id": "shell-bash",      "framework_name": "Shell / Bash",   "source_roadmap": "shell-bash"},
        {"framework_id": "python",         "framework_name": "Python",         "source_roadmap": "python"},
        {"framework_id": "cyber-security", "framework_name": "Cyber Security", "source_roadmap": "cyber-security"},
    ],
    "product-manager": [
        {"framework_id": "design-system",   "framework_name": "Design System",   "source_roadmap": "design-system"},
        {"framework_id": "technical-writer", "framework_name": "Technical Writer", "source_roadmap": "technical-writer"},
        {"framework_id": "seo",              "framework_name": "SEO & Growth",    "source_roadmap": "seo"},
    ],
    "product-design": [
        {"framework_id": "ux-design",     "framework_name": "UX Design",     "source_roadmap": "ux-design"},
        {"framework_id": "design-system", "framework_name": "Design System", "source_roadmap": "design-system"},
    ],
    "ux-design": [
        {"framework_id": "design-system", "framework_name": "Design System", "source_roadmap": "design-system"},
        {"framework_id": "product-design", "framework_name": "Product Design", "source_roadmap": "product-design"},
    ],
    "engineering-manager": [
        {"framework_id": "code-review",     "framework_name": "Code Review",     "source_roadmap": "code-review"},
        {"framework_id": "technical-writer", "framework_name": "Technical Writer", "source_roadmap": "technical-writer"},
    ],
    "devrel": [
        {"framework_id": "technical-writer", "framework_name": "Technical Writer", "source_roadmap": "technical-writer"},
        {"framework_id": "git-github",       "framework_name": "Git & GitHub",       "source_roadmap": "git-github"},
    ],
    "forward-deployed-engineer": [
        {"framework_id": "python",     "framework_name": "Python",     "source_roadmap": "python"},
        {"framework_id": "docker",     "framework_name": "Docker",     "source_roadmap": "docker"},
        {"framework_id": "ai-agents",  "framework_name": "AI Agents",  "source_roadmap": "ai-agents"},
        {"framework_id": "api-design", "framework_name": "API Design", "source_roadmap": "api-design"},
    ],
    "computer-science": [
        {"framework_id": "datastructures-and-algorithms", "framework_name": "Data Structures & Algorithms", "source_roadmap": "datastructures-and-algorithms"},
        {"framework_id": "leetcode",                      "framework_name": "LeetCode",                      "source_roadmap": "leetcode"},
        {"framework_id": "c",                             "framework_name": "C",                             "source_roadmap": "c"},
        {"framework_id": "cpp",                           "framework_name": "C++",                           "source_roadmap": "cpp"},
        {"framework_id": "python",                        "framework_name": "Python",                        "source_roadmap": "python"},
    ],
    "datastructures-and-algorithms": [
        {"framework_id": "leetcode", "framework_name": "LeetCode", "source_roadmap": "leetcode"},
        {"framework_id": "python",   "framework_name": "Python",   "source_roadmap": "python"},
        {"framework_id": "cpp",      "framework_name": "C++",      "source_roadmap": "cpp"},
        {"framework_id": "java",     "framework_name": "Java",     "source_roadmap": "java"},
    ],
}

PRIMARY_TRACKS = list(TRACK_FRAMEWORKS.keys())
CACHE_DIR = Path(__file__).resolve().parent.parent / "json" / ".cache_roadmaps"


# ---------- FETCHING ROADMAP STRUCTURE WITH CACHING ----------

def fetch_roadmap(slug, json_dir=None):
    if json_dir:
        local = Path(json_dir) / f"{slug}.json"
        if local.exists():
            return json.loads(local.read_text(encoding="utf-8"))

    cache_file = CACHE_DIR / f"{slug}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data and data.get("nodes"):
                return data
        except Exception:
            pass

    req = urllib.request.Request(
        API_URL.format(slug),
        headers={"User-Agent": "Mozilla/5.0 (compatible; roadmap-sync/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)

    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"API error for {slug}: {data['error']}")

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    return data


# ---------- READING MARKDOWN CONTENT FILES ----------

def index_content_files(content_dir):
    files = {}
    if not content_dir.is_dir():
        return files
    for f in content_dir.iterdir():
        m = FILE_RE.match(f.name)
        if m:
            files[m.group(2)] = f
    return files


def parse_content(text):
    desc_lines, links = [], []
    for line in text.splitlines():
        if line.startswith("# ") and not desc_lines and not links:
            continue
        m = LINK_RE.match(line)
        if m:
            title = re.sub(r"\\(.)", r"\1", m.group(2)).strip()
            links.append((title, m.group(3).strip()))
            continue
        if VISIT_RE.match(line):
            continue
        desc_lines.append(line)

    description = re.sub(r"\n{3,}", "\n\n", "\n".join(desc_lines)).strip()
    return (description or None), links


# ---------- LAYOUT & GEOMETRY HELPERS ----------

LABEL_MAX_SCORE = 120
STACK_MAX_SCORE = 45
TOPIC_BELOW_MAX_GAP = 45

STATS = {}


def node_pos(node):
    p = node.get("position") or node.get("positionAbsolute") or {}
    return float(p.get("x", 0)), float(p.get("y", 0))


def node_label(node):
    return ((node.get("data") or {}).get("label") or "").strip()


def box(node):
    w = node.get("width") or (node.get("measured") or {}).get("width") or 0
    h = node.get("height") or (node.get("measured") or {}).get("height") or 0
    x, y = node_pos(node)
    return x, y, float(w), float(h)


def inside(node, section, pad=2):
    x, y, w, h = box(node)
    sx, sy, sw, sh = box(section)
    cx, cy = x + w / 2, y + h / 2
    return sx - pad <= cx <= sx + sw + pad and sy - pad <= cy <= sy + sh + pad


def distance(a, b):
    ax, ay = node_pos(a)
    bx, by = node_pos(b)
    return math.hypot(ax - bx, ay - by)


def above_score(item, cand):
    ix, iy, iw, ih = box(item)
    cx, cy, cw, ch = box(cand)
    vgap = iy - (cy + ch)
    if vgap < -10:
        return None
    hgap = max(0.0, max(ix, cx) - min(ix + iw, cx + cw))
    return max(vgap, 0.0) + 3 * hgap


def make_items(nodes):
    items = {}
    for n in nodes:
        kind = n.get("type")
        if kind in ("subtopic", "todo") and node_label(n):
            items[n["id"]] = {**n, "_adj": n["id"]}
        elif kind == "checklist":
            x, y = node_pos(n)
            for i, entry in enumerate((n.get("data") or {}).get("checklists") or []):
                label = (entry.get("label") or "").strip()
                if not label:
                    continue
                item_id = f"{n['id']}-{entry.get('id', i)}"
                items[item_id] = {
                    "id": item_id,
                    "type": "checklist-item",
                    "data": {"label": label},
                    "position": {"x": x, "y": y + i * 0.01},
                    "width": n.get("width"),
                    "height": n.get("height"),
                    "_adj": n["id"],
                }
    return items


def edge_parents(start, adj, item_nodes, topics):
    seen, frontier = {start}, [start]
    while frontier:
        found, nxt = [], []
        for cur in frontier:
            for nb in adj[cur]:
                if nb in topics:
                    found.append(nb)
                elif nb in item_nodes and nb not in seen:
                    seen.add(nb)
                    nxt.append(nb)
        if found:
            return found
        frontier = nxt
    return []


def pick_label(item, labels):
    if len(labels) == 1:
        return labels[0]
    scored = [(above_score(item, lab), lab) for lab in labels]
    scored = [(sc, lab) for sc, lab in scored if sc is not None]
    if scored:
        return min(scored, key=lambda t: t[0])[1]
    return min(labels, key=lambda lab: distance(lab, item))


# ---------- SEMANTIC AFFINITY RULES ----------

SEMANTIC_AFFINITY_RULES = [
    (r"\b(npm|yarn|pnpm|bun|pip|composer|cargo|nuget)\b", r"package manager"),
    (r"\b(react|vue|angular|svelte|solid|next|nuxt|remix|astro)\b", r"^(?!.*css).*framework"),
    (r"\b(git|gitlab|github|bitbucket|svn|mercurial)\b", r"(version control|vcs|repo hosting)"),
    (r"\b(tailwind|bootstrap|bulma|sass|less|postcss|chakra|material ui)\b", r"css framework|styling"),
    (r"\b(webpack|vite|rollup|esbuild|parcel|turbopack|snowpack)\b", r"bundler|build tool"),
    (r"\b(eslint|prettier|biome|stylelint)\b", r"linter|formatter"),
    (r"\b(jest|cypress|playwright|vitest|mocha|selenium)\b", r"test|testing"),
    (r"\b(jwt|oauth|session|sso|cookie|openid|token)\b", r"auth|security"),
    (r"\b(sql|postgresql|mysql|sqlite|oracle|mariadb)\b", r"relational database|database"),
    (r"\b(mongodb|cassandra|couchdb|dynamodb)\b", r"nosql|database"),
    (r"\b(redis|memcached)\b", r"caching|cache"),
    (r"\b(kafka|rabbitmq|activemq|sqs)\b", r"broker|messaging"),
    (r"\b(docker|podman|containerd)\b", r"container|docker"),
    (r"\b(kubernetes|k8s|helm)\b", r"kubernetes|orchestration"),
    (r"\b(terraform|pulumi|ansible)\b", r"infrastructure|iac"),
    (r"\b(rest|graphql|grpc|soap|openapi)\b", r"api|apis"),
]


def find_semantic_parent(item_label, topics):
    il = item_label.lower().strip()
    for item_pat, topic_pat in SEMANTIC_AFFINITY_RULES:
        if re.search(item_pat, il):
            cands = [tid for tid, top in topics.items() if re.search(topic_pat, node_label(top).lower())]
            if cands:
                return cands
    return []


def attach_items(topics, items, labels, sections, edges, stats):
    adj = defaultdict(set)
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s and t:
            adj[s].add(t)
            adj[t].add(s)
    item_nodes = {it["_adj"] for it in items.values()}

    heading_boxes = []
    for sec in sections:
        labs = [lab for lab in labels.values() if inside(lab, sec)]
        if labs and not any(inside(t, sec) for t in topics.values()):
            x, y, w, h = box(sec)
            heading_boxes.append((w * h, sec, labs))
    heading_boxes.sort(key=lambda t: t[0])

    topic_members, heading_members = defaultdict(list), defaultdict(list)
    placed = {}

    for item in sorted(items.values(), key=lambda n: (node_pos(n)[1], node_pos(n)[0])):
        ilabel = node_label(item)

        # 1) Graph edges (direct / multi-hop)
        found = edge_parents(item["_adj"], adj, item_nodes, topics)
        if found:
            parent = min(found, key=lambda t: distance(topics[t], item))
            topic_members[parent].append(item)
            placed[item["id"]] = ("topic", parent)
            stats["edge"] += 1
            continue

        # 2) Inside a heading box
        box_hit = next((labs for _, sec, labs in heading_boxes if inside(item, sec)), None)
        if box_hit:
            heading_members[pick_label(item, box_hit)["id"]].append(item)
            stats["heading box"] += 1
            continue

        # 3) Semantic affinity check (domain knowledge)
        sem_cands = find_semantic_parent(ilabel, topics)
        if sem_cands:
            parent = min(sem_cands, key=lambda t: distance(topics[t], item))
            topic_members[parent].append(item)
            placed[item["id"]] = ("topic", parent)
            stats["semantic affinity"] += 1
            continue

        # 4) Geometric proximity
        options = []
        for other_id, (kind, pid) in placed.items():
            sc = above_score(item, items[other_id])
            if sc is not None and sc <= STACK_MAX_SCORE:
                options.append((sc, kind, pid, "stacked under another"))
        for lid, lab in labels.items():
            sc = above_score(item, lab)
            if sc is not None and sc <= LABEL_MAX_SCORE:
                options.append((sc, "heading", lid, "label above"))
        for tid, top in topics.items():
            sc = above_score(top, item)
            if sc is not None and sc <= TOPIC_BELOW_MAX_GAP:
                options.append((sc, "topic", tid, "topic below"))
            sc = above_score(item, top)
            if sc is not None:
                options.append((sc + 1000, "topic", tid, "topic above"))

        if options:
            _, kind, pid, rule = min(options, key=lambda o: o[0])
            (heading_members if kind == "heading" else topic_members)[pid].append(item)
            placed[item["id"]] = (kind, pid)
            stats[rule] += 1
        elif topics:
            parent = min(topics, key=lambda t: distance(topics[t], item))
            topic_members[parent].append(item)
            placed[item["id"]] = ("topic", parent)
            stats["closest topic (guess)"] += 1
        else:
            stats["orphan (dropped)"] += 1

    return topic_members, heading_members


def attach_resources(resource_nodes, items, topics):
    owners = {}
    for r in resource_nodes:
        cands = [
            (above_score(r, c), cid)
            for cid, c in {**items, **topics}.items()
            if above_score(r, c) is not None
        ]
        if cands:
            owners.setdefault(min(cands, key=lambda t: t[0])[1], []).append(r)
    return owners


# ---------- OPTION C: HYBRID TOPOLOGICAL & PEDAGOGICAL ORDERING ----------

PEDAGOGICAL_TIER_PATTERNS = [
    (0, r"\b(internet|how does the internet work|cs basics|computer science|prerequisite|introduction|basics|getting started|frontend basics|pick a backend language)\b"),
    (1, r"\b(html|css|javascript|typescript|python|java|c\+\+|golang|go|rust|c#|ruby|php|kotlin|swift|syntax|core language|markup)\b"),
    (2, r"\b(version control|git|github|gitlab|vcs|repo hosting|package manager|npm|yarn|pnpm|linters|formatters)\b"),
    (3, r"\b(framework|react|vue|angular|svelte|nextjs|css framework|tailwind|bootstrap|web apis|dom|learn about apis|apis|rest|graphql)\b"),
    (4, r"\b(database|relational|nosql|state management|redux|caching|storage|async|message brokers|search engines)\b"),
    (5, r"\b(test|testing|unit|integration|e2e|cypress|playwright|jest)\b"),
    (6, r"\b(security|auth|authentication|authorization|owasp|cors|https|web security)\b"),
    (7, r"\b(module bundler|bundler|build|vite|webpack|ci / cd|ci/cd|deploy|deployment|hosting|web servers)\b"),
    (8, r"\b(ssr|ssg|performance|pwa|web components|accessibility|design system|architecture|architectural patterns|system design|scaling|real-time data)\b"),
    (9, r"\b(ai|prompt|agents|mcp|coding|ai assisted coding|desktop apps|mobile apps|emerging)\b"),
]


def get_pedagogical_tier(label):
    l = label.lower()
    for tier, pat in PEDAGOGICAL_TIER_PATTERNS:
        if re.search(pat, l):
            return float(tier)
    return 4.0


def compute_hybrid_order(top_level, edges, all_nodes):
    id_to_entry = {node["id"]: (pos, node, members) for pos, node, members in top_level}
    topic_ids = set(id_to_entry.keys())

    dag = defaultdict(set)
    in_degree = defaultdict(int)
    for tid in topic_ids:
        in_degree[tid] = 0

    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in topic_ids and t in topic_ids and s != t:
            sy = node_pos(all_nodes.get(s, {}))[1]
            ty = node_pos(all_nodes.get(t, {}))[1]
            if ty >= sy - 150:
                if t not in dag[s]:
                    dag[s].add(t)
                    in_degree[t] += 1

    ranks = {tid: get_pedagogical_tier(node_label(id_to_entry[tid][1])) for tid in topic_ids}

    q = deque([tid for tid in topic_ids if in_degree[tid] == 0])
    current_in = dict(in_degree)
    while q:
        curr = q.popleft()
        for nxt in dag[curr]:
            ranks[nxt] = max(ranks[nxt], ranks[curr] + 0.1)
            current_in[nxt] -= 1
            if current_in[nxt] == 0:
                q.append(nxt)

    def sort_key(entry):
        _, node, _ = entry
        nid = node["id"]
        x, y = node_pos(node)
        return (ranks[nid], y, x)

    return sorted(top_level, key=sort_key)


SUB_PRIORITY_PATTERNS = [
    (0, r"\b(basic|syntax|intro|overview|core|fundamental|how|what is|getting started)\b"),
    (1, r"\b(intermediate|features|workflow|lifecycle|state|routing)\b"),
    (2, r"\b(advanced|internals|optimization|performance|best practice)\b"),
    (3, r"\b(tool|alternative|ecosystem|extra)\b"),
]


def sub_skill_priority(label):
    l = label.lower()
    for p, pat in SUB_PRIORITY_PATTERNS:
        if re.search(pat, l):
            return p
    return 1


def sort_sub_skills(members):
    seen_labels = set()
    unique_members = []
    for m in members:
        lbl = node_label(m).lower()
        if lbl and lbl not in seen_labels:
            seen_labels.add(lbl)
            unique_members.append(m)

    return sorted(
        unique_members,
        key=lambda n: (sub_skill_priority(node_label(n)), node_pos(n)[1], node_pos(n)[0]),
    )


# ---------- BUILDING THE OUTPUT ----------

def build_skill(node, files, extra_links=()):
    node_id = node["id"]
    name = node_label(node)

    description, links = (None, [])
    if node_id in files:
        description, links = parse_content(files[node_id].read_text(encoding="utf-8"))

    if links:
        rsc = [{"title": t, "url": u, "content": None} for t, u in links]
    elif description:
        rsc = [{"title": name, "url": None, "content": description}]
    else:
        rsc = []

    for r in extra_links:
        data = r.get("data") or {}
        if data.get("href"):
            rsc.append({"title": node_label(r) or data["href"], "url": data["href"], "content": None})

    return {
        "skill_id": node_id,
        "skill_name": name,
        "skill_content": description,
        "rsc": rsc,
    }


def build_track(slug, roadmaps_dir, json_dir, embed_frameworks=True, visited=None):
    """Builds an ordered track with skills, sub-skills, and embedded frameworks."""
    if visited is None:
        visited = set()
    if slug in visited:
        return {"track_id": slug, "track_name": slug, "skills": []}

    cache_key = (slug, embed_frameworks)
    if cache_key in TRACK_CACHE:
        return copy.deepcopy(TRACK_CACHE[cache_key])

    roadmap = fetch_roadmap(slug, json_dir)
    nodes = roadmap.get("nodes", [])
    edges = roadmap.get("edges", [])
    files = index_content_files(roadmaps_dir / slug / "content")
    all_nodes = {n["id"]: n for n in nodes}

    topics = {n["id"]: n for n in nodes if n.get("type") == "topic" and node_label(n)}
    labels = {
        n["id"]: n
        for n in nodes
        if n.get("type") == "label" and re.search(r"[A-Za-z\u0600-\u06FF]", node_label(n))
    }
    sections = [n for n in nodes if n.get("type") == "section"]
    resource_nodes = [n for n in nodes if n.get("type") == "resourceButton"]
    items = make_items(nodes)

    stats = Counter()
    topic_members, heading_members = attach_items(topics, items, labels, sections, edges, stats)
    owners = attach_resources(resource_nodes, items, topics)
    STATS[slug] = stats

    top_level = []
    for tid, topic in topics.items():
        top_level.append(((node_pos(topic)[1], node_pos(topic)[0]), topic, topic_members.get(tid, [])))
    for lid, members in heading_members.items():
        label = labels[lid]
        top_y = min([box(label)[1]] + [box(m)[1] for m in members])
        top_level.append(((top_y, node_pos(label)[0]), label, members))

    ordered_top_level = compute_hybrid_order(top_level, edges, all_nodes)

    skills = []
    for order, (_, node, members) in enumerate(ordered_top_level, start=1):
        skill = build_skill(node, files, owners.get(node["id"], ()))
        skill["skill_order_in_track"] = order
        skill["sub_skills"] = []

        for sub_order, sub in enumerate(sort_sub_skills(members), start=1):
            sub_skill = build_skill(sub, files, owners.get(sub["id"], ()))
            sub_skill["skill_order_in_parent"] = sub_order
            skill["sub_skills"].append(sub_skill)

        skills.append(skill)

    title = roadmap.get("title") or {}
    track_name = (
        (title.get("page") or title.get("card")) if isinstance(title, dict) else title
    ) or slug.replace("-", " ").title()

    track = {"track_id": slug, "track_name": track_name, "skills": skills}

    frameworks = []
    if embed_frameworks:
        next_visited = visited | {slug}
        for fw in TRACK_FRAMEWORKS.get(slug, []):
            fw_skills = []
            if fw["source_roadmap"]:
                try:
                    fw_track = build_track(
                        fw["source_roadmap"], roadmaps_dir, json_dir,
                        embed_frameworks=False, visited=next_visited
                    )
                    fw_skills = fw_track["skills"]
                except Exception as err:
                    print(f"WARN {slug}/{fw['framework_id']}: {err}")
            frameworks.append({**fw, "skills": fw_skills})

    if frameworks:
        track["frameworks"] = frameworks

    TRACK_CACHE[cache_key] = track
    return copy.deepcopy(track)


def all_slugs(roadmaps_dir):
    return PRIMARY_TRACKS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--roadmap-slug",
        default=ROADMAP_SLUG,
        help="comma separated slugs, or __all__ (default: ROADMAP_SLUG at the top of the file)",
    )
    parser.add_argument(
        "--roadmaps-dir",
        default=str(Path(__file__).resolve().parent.parent.parent / "DB" / "roadmaps"),
        help="path to the repo's roadmaps folder",
    )
    parser.add_argument(
        "--json-dir",
        default=None,
        help="optional folder with <slug>.json files (offline mode)",
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "json" / "roadmaps_ordered.json"),
        help="path to write output JSON files",
    )
    args = parser.parse_args()

    roadmaps_dir = Path(args.roadmaps_dir)
    if not roadmaps_dir.is_dir():
        sys.exit(f"roadmaps folder not found: {roadmaps_dir}")

    if args.roadmap_slug == "__all__":
        slugs = all_slugs(roadmaps_dir)
    else:
        slugs = [s.strip() for s in args.roadmap_slug.split(",") if s.strip()]

    print(f"Building {len(slugs)} track(s)...")

    tracks = []
    for slug in slugs:
        try:
            track = build_track(slug, roadmaps_dir, args.json_dir)
            tracks.append(track)
            subs = sum(len(t["sub_skills"]) for t in track["skills"])
            fws = len(track.get("frameworks", []))
            how = ", ".join(f"{k} {v}" for k, v in STATS.get(slug, {}).items())
            print(f"OK   {slug:25}: {len(track['skills']):2d} skills, {subs:2d} sub-skills, {fws:2d} frameworks [{how}]")
        except Exception as err:
            print(f"FAIL {slug:25}: {err}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if ONE_FILE_PER_TRACK:
        for track in tracks:
            file_path = out_path.parent / f"{track['track_id']}.json"
            file_path.write_text(
                json.dumps(track, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(f"\nWrote {len(tracks)} file(s) to {out_path.parent}")
    else:
        out_path.write_text(
            json.dumps(tracks, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nWrote {len(tracks)} track(s) to {out_path}")


if __name__ == "__main__":
    main()
