---
name: deadline-radar
description: Track upcoming assignment deadlines from a markdown file and flag ones whose GitHub repo has gone quiet. Answers "what's due this week" and powers "due in 3 days, no commits since Tuesday" alerts.
version: 1.0.0
author: megradhikan
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [productivity, deadlines, students, github, alerts]
    requires_toolsets: [terminal]
---

# Deadline Radar

Reads a small deadlines file, works out what is due soon, and checks each linked GitHub repo's last
commit so it can warn when a deadline is close but the repo has gone stale. Standard library only, no
API key needed (set `GITHUB_TOKEN` in the environment only if you hit GitHub's anonymous rate limit).

## When to Use

- The user asks what is due this week, what's coming up, or how much time is left on an assignment.
- The user asks whether they are behind on a project that has a repo.
- A scheduled check wants deadline alerts (due today, overdue, or due within 3 days with a stale repo).

If a tool named `deadline_radar` is available, call it instead of running the script; it does the same thing.

## Deadlines File Format

One deadline per line, everything else is ignored:

```
- 2026-11-14 23:59 | CSCI 599 Assignment 3 | repo: owner/name | notes: demo video required
- 2026-11-16 | MATH 410 Problem Set 8 | notes: submit on the course site
```

Time is optional (defaults to 23:59). `repo:` is optional. Times are read in the `--tz` timezone
(default America/Los_Angeles).

Where to find it, in order: a path the user gives; `$HERMES_HOME/a3-workspace/deadlines.md` if it
exists; otherwise `references/deadlines.example.md` inside this skill (sample data, say so in the answer).

## Quick Reference

| Goal | Command |
|---|---|
| Next 7 days, readable | `python3 <skill_dir>/scripts/radar.py --deadlines <file>` |
| Next 14 days as JSON | `python3 <skill_dir>/scripts/radar.py --deadlines <file> --days 14 --json` |
| Skip GitHub lookups | add `--no-github` |
| Different stale threshold | add `--stale-hours 72` |

`<skill_dir>` is the `skill_dir` value returned by `skill_view("deadline-radar")`.

## Procedure

1. Call `skill_view("deadline-radar")` and note `skill_dir`.
2. Pick the deadlines file as described above.
3. Run the readable command with the terminal tool. Use `--json` if you need to reason over fields.
4. Answer in a few lines: soonest first, with time left. Lead with anything marked `ALERT`
   (overdue, due today, or due within 3 days with a stale repo) and say why (for example
   "no commits in 3 days").
5. Never invent deadlines. If the file has none in range, say so.

## Pitfalls

- A repo that doesn't exist or is private shows an `error` and is not treated as stale; mention it.
- GitHub's anonymous API allows 60 requests per hour. With many repos, use `--no-github` or set `GITHUB_TOKEN`.
- Past deadlines more than a day old are dropped on purpose; don't present them as new.

## Verification

The command exits 0 and prints one line per deadline in range (or `[]` with `--json`). Each line shows
the due time, time left, and an `ALERT:` reason when one applies.
