#!/usr/bin/env python3
"""Deadline radar: list upcoming deadlines and flag ones with stale GitHub repos."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

LINE_RE = re.compile(r"^\s*[-*]\s+(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}:\d{2}))?\s*\|(.*)$")
REPO_RE = re.compile(r"^repo:\s*(\S+)$", re.IGNORECASE)


@dataclass
class Deadline:
    due: datetime
    title: str
    repo: str | None
    notes: str


def parse_deadlines(text: str, tz: str = "America/Los_Angeles") -> list[Deadline]:
    zone = ZoneInfo(tz)
    out: list[Deadline] = []
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        date_s, time_s, rest = m.groups()
        try:
            day = datetime.strptime(date_s, "%Y-%m-%d").date()
            if time_s:
                hh, mm = time_s.split(":")
                clock = time(int(hh), int(mm))
            else:
                clock = time(23, 59)
        except ValueError:
            continue
        fields = [f.strip() for f in rest.split("|")]
        title = fields[0] if fields else ""
        if not title:
            continue
        repo: str | None = None
        notes: list[str] = []
        for f in fields[1:]:
            rm = REPO_RE.match(f)
            if rm and repo is None:
                repo = rm.group(1)
            elif f:
                notes.append(f)
        out.append(
            Deadline(
                due=datetime.combine(day, clock, tzinfo=zone),
                title=title,
                repo=repo,
                notes=" | ".join(notes),
            )
        )
    out.sort(key=lambda d: d.due)
    return out


def load_deadlines(path: str | os.PathLike, tz: str = "America/Los_Angeles") -> list[Deadline]:
    with open(path, encoding="utf-8") as fh:
        return parse_deadlines(fh.read(), tz)


def repo_activity(
    repo: str,
    token: str | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict:
    token = token or os.environ.get("GITHUB_TOKEN")
    result: dict = {
        "repo": repo,
        "last_commit_at": None,
        "last_commit_msg_first_line": None,
        "pushed_at": None,
        "error": None,
    }

    def get(path: str) -> Any:
        req = urllib.request.Request(
            f"https://api.github.com{path}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "deadline-radar"},
        )
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with opener(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        commits = get(f"/repos/{repo}/commits?per_page=1")
        if commits:
            commit = commits[0].get("commit", {})
            result["last_commit_at"] = (commit.get("committer") or {}).get("date") or (
                commit.get("author") or {}
            ).get("date")
            result["last_commit_msg_first_line"] = (commit.get("message") or "").split("\n")[0]
        info = get(f"/repos/{repo}")
        result["pushed_at"] = info.get("pushed_at")
    except urllib.error.HTTPError as exc:
        result["error"] = f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        result["error"] = type(exc).__name__
    return result


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def radar(
    deadlines: list[Deadline],
    now: datetime,
    days: int = 7,
    stale_hours: int = 48,
    activity_fn: Callable[[str], dict] = repo_activity,
) -> list[dict]:
    items: list[dict] = []
    for d in sorted(deadlines, key=lambda x: x.due):
        delta = d.due - now
        hours_left = delta.total_seconds() / 3600
        if delta > timedelta(days=days) or delta < -timedelta(days=1):
            continue
        days_left = hours_left / 24
        if hours_left < 0:
            status = "overdue"
        elif d.due.astimezone(now.tzinfo).date() == now.date():
            status = "due_today"
        elif days_left <= 3:
            status = "due_soon"
        else:
            status = "upcoming"

        activity: dict | None = None
        stale = False
        if d.repo:
            activity = activity_fn(d.repo)
            last = activity.get("last_commit_at")
            if not last:
                stale = True
            else:
                age = (now - _parse_iso(last)).total_seconds() / 3600
                stale = age > stale_hours
        alert = (days_left <= 3 and stale) or status in ("overdue", "due_today")
        items.append(
            {
                "due": d.due.isoformat(),
                "title": d.title,
                "repo": d.repo,
                "notes": d.notes,
                "hours_left": round(hours_left, 1),
                "days_left": round(days_left, 2),
                "status": status,
                "activity": activity,
                "stale": stale,
                "alert": alert,
            }
        )
    return items


def _fmt_left(hours_left: float) -> str:
    if hours_left < 0:
        return f"{_fmt_left(-hours_left)} overdue"
    total = int(hours_left)
    d, h = divmod(total, 24)
    return f"{d}d {h}h left"


def _fmt_age(last: str | None, now: datetime) -> str:
    if not last:
        return "no commits"
    hours = (now - _parse_iso(last)).total_seconds() / 3600
    if hours < 48:
        return f"{max(int(hours), 0)}h ago"
    return f"{int(hours // 24)}d ago"


def format_line(item: dict, now: datetime) -> str:
    due = datetime.fromisoformat(item["due"])
    line = f"{due.strftime('%a %b %d %H:%M')}  {item['title']}  ({_fmt_left(item['hours_left'])})"
    act = item.get("activity")
    if item["repo"] and act is not None:
        if act.get("error"):
            line += f"  repo {item['repo']}: {act['error']}"
        else:
            line += f"  repo {item['repo']}: last commit {_fmt_age(act.get('last_commit_at'), now)}"
    elif item["repo"]:
        line += f"  repo {item['repo']}"
    if item["alert"]:
        reason = "stale repo" if item["stale"] and item["status"] not in ("overdue", "due_today") else item["status"].replace("_", " ")
        line += f"  ALERT: {reason}"
    return line


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    p = argparse.ArgumentParser(description="Show upcoming deadlines and repo activity.")
    p.add_argument("--deadlines", required=True, help="Path to the deadlines markdown file")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--stale-hours", type=int, default=48)
    p.add_argument("--tz", default="America/Los_Angeles")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.add_argument("--no-github", action="store_true")
    args = p.parse_args(argv)

    zone = ZoneInfo(args.tz)
    current = now or datetime.now(timezone.utc).astimezone(zone)
    deadlines = load_deadlines(args.deadlines, args.tz)
    if args.no_github:
        def activity_fn(repo: str) -> dict:
            return {
                "repo": repo,
                "last_commit_at": None,
                "last_commit_msg_first_line": None,
                "pushed_at": None,
                "error": "github lookup skipped",
            }
    else:
        activity_fn = repo_activity
    items = radar(deadlines, current, args.days, args.stale_hours, activity_fn)
    if args.no_github:
        for it in items:
            it["stale"] = False
            it["alert"] = it["status"] in ("overdue", "due_today")
    if args.as_json:
        print(json.dumps(items, indent=2))
    else:
        for it in items:
            print(format_line(it, current))
    return 0


if __name__ == "__main__":
    sys.exit(main())
