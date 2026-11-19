CareerGap - Scripts Readme
==========================


ID_saver.py
-----------
What it does:
  Takes the big skills.json file and pulls out just the IDs and names, so you
  end up with two small, easy-to-use lookup files: one for skills and one for
  tracks.

What it needs:
  A file at <Code>/json/skills.json. It should be a list of skills, and each
  skill needs a skill_id, a skill_name, and a "tracks" list where every track
  has a track_id and a track_name.

What you get:
  Two files in <Code>/IDs (the folder gets created if it isn't there yet):
    - skills_ids.json: every skill with its ID and name
    - tracks_ids.json: every track with its ID and name

How it works:
  It looks one folder up from where the script lives to find the Code folder,
  then reads skills.json from there. It copies each skill's ID and name into
  the first list. For tracks, it goes through every skill's track list and
  keeps each track only once, even if lots of skills share it. Then it saves
  both lists as readable JSON, and non-English characters stay as they are.

How to run it:
  python ID_saver.py

Good to know:
  - It overwrites the two output files every time you run it.
  - Run it again whenever skills.json changes so the lookups stay up to date.
