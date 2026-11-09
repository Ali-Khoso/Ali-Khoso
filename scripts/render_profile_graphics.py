#!/usr/bin/env python3
"""Render locally hosted profile SVGs from GitHub's own contribution data."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

LOGIN = "Ali-Khoso"
TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
OUT = Path("assets")

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, privacy: PUBLIC) {
      nodes { stargazerCount }
      pageInfo { hasNextPage endCursor }
    }
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(vars):
    if not TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN")
    body = json.dumps({"query": QUERY, "variables": vars}).encode()
    req = Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Ali-Khoso-profile-graphics",
    })
    with urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError("GitHub GraphQL returned errors: " + repr(payload["errors"]))
    user = payload.get("data", {}).get("user")
    if not user:
        raise RuntimeError("No GitHub user returned")
    return user


def stats(user, repos, stars, today):
    collection = user["contributionsCollection"]
    cells = [
        (25, 73, "COMMITS (12 MONTHS)", collection["totalCommitContributions"]),
        (285, 73, "STARS (PUBLIC REPOS)", stars),
        (25, 148, "PRS (12 MONTHS)", collection["totalPullRequestContributions"]),
        (285, 148, "ISSUES (12 MONTHS)", collection["totalIssueContributions"]),
    ]
    tiles = "".join(
        f'<rect x="{x}" y="{y}" rx="11" width="245" height="66" fill="#24283b"/>'
        f'<text x="{x + 15}" y="{y + 23}" fill="#a9b1d6" font-size="11">{label}</text>'
        f'<text x="{x + 15}" y="{y + 52}" fill="#c0caf5" font-size="28" font-weight="bold">{value:,}</text>'
        for x, y, label, value in cells
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 555 248" width="555" height="248">
<title>GitHub statistics for {LOGIN}</title>
<desc>Commits, stars, pull requests and issues. Contribution metrics cover the last 12 months. Updated {today} UTC.</desc>
<rect width="555" height="248" rx="16" fill="#1a1b26"/>
<rect width="5" height="248" fill="#bb9af7"/>
<g font-family="Arial, sans-serif">
<text x="25" y="36" fill="#c0caf5" font-size="21" font-weight="bold">GitHub statistics</text>
<text x="25" y="55" fill="#7aa2f7" font-size="12">@{escape(LOGIN)} · {repos} public repositories</text>
{tiles}
<text x="25" y="235" fill="#a9b1d6" font-size="11">Updated {today} UTC · GitHub Actions</text>
</g></svg>'''


def activity(user, today):
    calendar = user["contributionsCollection"]["contributionCalendar"]
    weeks = [w for w in calendar["weeks"] if w["contributionDays"]][-53:]
    if not weeks:
        raise RuntimeError("GitHub did not provide a contribution calendar")
    counts = [sum(day["contributionCount"] for day in w["contributionDays"]) for w in weeks]
    peak = max(1, max(counts))
    left, right, top, bottom = 67, 997, 95, 255
    pts = [(left + i * (right - left) / max(1, len(counts) - 1),
            bottom - n * (bottom - top) / peak) for i, n in enumerate(counts)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M {left},{bottom} L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area += f" L {pts[-1][0]:.1f},{bottom} Z"
    guides = []
    for i in range(5):
        y = bottom - i * (bottom - top) / 4
        guides.append(f'<line x1="{left}" x2="{right}" y1="{y:.1f}" y2="{y:.1f}" stroke="#414868" stroke-width=".8"/>')
        guides.append(f'<text x="{left - 12}" y="{y + 4:.1f}" fill="#a9b1d6" text-anchor="end" font-size="12">{round(peak * i / 4)}</text>')
    for i in range(0, len(weeks), 8):
        date = datetime.strptime(weeks[i]["contributionDays"][0]["date"], "%Y-%m-%d").strftime("%b %Y")
        guides.append(f'<text x="{pts[i][0]:.1f}" y="281" fill="#a9b1d6" font-size="12" text-anchor="middle">{date}</text>')
    total = calendar["totalContributions"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1060 311" width="1060" height="311">
<title>Recent GitHub contribution activity for {LOGIN}</title>
<desc>{total:,} contributions over the last 12 months. Weekly contributions. Updated {today} UTC.</desc>
<defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
<stop offset="0%" stop-color="#bb9af7" stop-opacity=".72"/>
<stop offset="100%" stop-color="#bb9af7" stop-opacity=".07"/>
</linearGradient></defs>
<rect width="1060" height="311" rx="16" fill="#1a1b26"/><rect width="5" height="311" fill="#7aa2f7"/>
<g font-family="Arial, sans-serif">
<text x="30" y="38" font-size="21" font-weight="bold" fill="#c0caf5">Recent contribution activity</text>
<text x="30" y="61" fill="#7aa2f7" font-size="13">{total:,} contributions (last 12 months) · Week by week</text>
{''.join(guides)}
<path d="{area}" fill="url(#fill)"/>
<polyline points="{line}" fill="none" stroke="#bb9af7" stroke-width="3" stroke-linejoin="round"/>
<text x="1030" y="300" text-anchor="end" fill="#a9b1d6" font-size="11">Updated {today} UTC</text>
</g></svg>'''


def main():
    now = datetime.now(timezone.utc)
    vars = {"login": LOGIN, "from": (now - timedelta(days=364)).isoformat(),
            "to": now.isoformat(), "after": None}
    user = fetch(vars)
    repos = list(user["repositories"]["nodes"])
    page = user["repositories"]["pageInfo"]
    while page["hasNextPage"]:
        vars["after"] = page["endCursor"]
        more = fetch(vars)["repositories"]
        repos.extend(more["nodes"])
        page = more["pageInfo"]
    OUT.mkdir(parents=True, exist_ok=True)
    today = now.strftime("%Y-%m-%d")
    (OUT / "github-stats.svg").write_text(stats(user, len(repos), sum(x["stargazerCount"] for x in repos), today) + "\n", encoding="utf-8")
    (OUT / "github-activity.svg").write_text(activity(user, today) + "\n", encoding="utf-8")
    print("Rendered both GitHub graphics; no secrets saved.")


if __name__ == "__main__":
    main()
