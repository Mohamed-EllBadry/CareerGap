skills_json_file.py
===================

So what is this script?

It takes the roadmap.sh roadmaps (a big folder of Markdown files, one file per
topic) and turns them into a single skills.json file that's ready to be loaded
into a database. Every topic in a roadmap becomes a "skill", every roadmap
becomes a "track", and the learning links inside each topic become that
skill's resources.

Think of it like taking a pile of handwritten notes from many different
courses and typing them up into one tidy catalog, where each subject appears
once, even if several courses teach it.

Before you run it

You need the roadmap.sh repository on your machine. The script looks for it at
DB/roadmap.sh/src/data/roadmaps, one level above your Code folder. If yours is
somewhere else, just tell the script where with --roadmaps-dir.

It also works with the two ID files that ID_saver.py creates (skills_ids.json
and tracks_ids.json in the IDs folder). They're not required, but if they
exist the script reuses them, which is what keeps every skill and track on the
same ID from one run to the next. More on that below.

How to run it

  python skills_json_file.py

or, if your roadmaps live somewhere else:

  python skills_json_file.py --roadmaps-dir "path/to/roadmaps"

There are two more optional settings. --output-dir changes where the results
are saved (default is the json folder inside Code), and --ids-dir changes
where the ID files are read from and saved to (default is the IDs folder
inside Code).

What you end up with

The main result is skills.json, saved in the json folder. Next to it you get
two reports: validation_report.json, which gives you the numbers (how many
skills, tracks, resources, and so on), and description_review.json, which
lists every skill whose description needed a bit of special handling so you
can double-check it. The script also updates skills_ids.json and
tracks_ids.json in the IDs folder.

Each skill in skills.json has an ID, a name, a description, and a list of the
tracks it appears in. Each of those tracks has its own ID, its name, the
skill's position in that track, and a list of resources (a title, a URL, and
some content).

How it works, step by step

First it goes through every roadmap folder and reads each Markdown file inside
its content folder. If a roadmap has no content folder, it prints a warning
and moves on instead of crashing.

For each file, the skill name is the first heading, in lowercase. Files named
"readme" are skipped because they're notes about the roadmap, not skills.
Files whose heading is just "questions to ask" get their name from the file
name instead, since lots of files share that heading.

The description is the first real piece of text under the heading. It skips
filler like "Visit the following resources to learn more" and bare list
introductions that end in a colon. If the opening line is only a lead-in, it
uses the list that follows it instead. If the file truly has nothing useful,
the description is left empty rather than made up, and the skill shows up in
description_review.json so you know to look at it.

The resources come from the links in the bullet lists. Titles are cleaned of
Markdown clutter, broken URLs missing a closing bracket get fixed, links that
just jump to a spot in the same page are ignored, and links like /golang turn
into full roadmap.sh addresses. Duplicate links in the same file are dropped.
If a file has no links at all, its own text is used as the resource instead.
But if a track has at least one real link, those text-only entries are
removed so you only keep the real links.

If the same skill appears in several roadmaps (say, "git" shows up in a few of
them), it's merged into one skill with several tracks instead of being
repeated. Any new description text or new resources are added to the first
version, and nothing already there is duplicated.

About the IDs

Each skill and track gets a long random ID the first time it's seen. After
that, the ID stays the same forever, because the script looks names up in the
ID files first and only creates a new ID when it finds nothing. Skill names
are matched ignoring spaces and punctuation, so small formatting differences
won't create a second ID for the same skill. At the end, the ID files are
saved again with any new additions, and the old ones are left untouched.

Checks before saving

Before writing anything, the script checks its own work. It makes sure every
skill and track has the same structure, that IDs are unique, that every track
ID points to just one track name, that the position numbers in each track run
1, 2, 3 without gaps, and that the final JSON can be read back. Any empty text
value is replaced with the word NAN, so a database import never runs into a
blank. If a check fails, the script stops with an error and nothing is saved.

Good to know

  - It's safe to run again whenever the roadmaps change. Existing IDs stay
    put, and only new skills and tracks get new ones.
  - Run ID_saver.py first if you want to rebuild the ID files from an
    existing skills.json.
  - It's worth opening description_review.json after a run and checking the
    entries marked for manual review.