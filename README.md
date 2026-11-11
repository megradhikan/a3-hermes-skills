# a3-hermes-skills

A Hermes Agent skill tap with one skill, `deadline-radar`, built for CSCI 599 Assignment 3.

`deadline-radar` reads a small markdown file of deadlines, shows what's due soon, and checks each linked
GitHub repo's last commit so it can warn when something is due in a few days but the repo has gone quiet.
Standard library only, no credentials.

## Install with the tap workflow

```bash
hermes skills tap add megradhikan/a3-hermes-skills
hermes skills search deadline
hermes skills inspect megradhikan/a3-hermes-skills/skills/deadline-radar
hermes skills install megradhikan/a3-hermes-skills/skills/deadline-radar
```

Then ask the agent "what's due this week?" or run the script directly:

```bash
python3 <skill_dir>/scripts/radar.py --deadlines path/to/deadlines.md
```

See `skills/deadline-radar/SKILL.md` for the file format and options.

## Layout

```
skills/
  deadline-radar/
    SKILL.md
    scripts/radar.py
    references/deadlines.example.md
```

All sample data is fictional.
