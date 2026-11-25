"""Generate self-hosted GitHub stat cards (no third-party widget servers).

Writes dist/stats.svg and dist/langs.svg using the GitHub GraphQL API.
Runs in GitHub Actions with GITHUB_TOKEN; public data only.
"""
import json
import os
import urllib.request
from html import escape

USER = os.environ.get("GH_USER", "sidharthabhi")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = os.environ.get("OUT_DIR", "dist")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, privacy: PUBLIC) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""

SKIP_LANGS = {"Jupyter Notebook", "HTML", "CSS"}

BG, BORDER, TITLE, TEXT, MUTED, ACCENT = (
    "#0D1117", "#1F2937", "#60A5FA", "#C9D1D9", "#8B949E", "#22C55E")
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', sans-serif"


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def card(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    .t {{ font: 600 17px {FONT}; fill: {TITLE}; }}
    .l {{ font: 400 13px {FONT}; fill: {MUTED}; }}
    .v {{ font: 700 22px {FONT}; fill: {TEXT}; }}
    .s {{ font: 400 12px {FONT}; fill: {TEXT}; }}
    .fade {{ animation: in .6s ease-out backwards; }}
    @keyframes in {{ from {{ opacity: 0; }} }}
  </style>
  <rect x="0.5" y="0.5" rx="10" width="{width - 1}" height="{height - 1}" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="36" class="t">{escape(title)}</text>
  {body}
</svg>"""


def stats_svg(u):
    repos = u["repositories"]["nodes"]
    cc = u["contributionsCollection"]
    items = [
        ("Contributions (1y)", cc["contributionCalendar"]["totalContributions"]),
        ("Commits (1y)", cc["totalCommitContributions"]),
        ("Public repositories", u["repositories"]["totalCount"]),
        ("Stars earned", sum(r["stargazerCount"] for r in repos)),
        ("Pull requests (1y)", cc["totalPullRequestContributions"]),
        ("Followers", u["followers"]["totalCount"]),
    ]
    cells = []
    for i, (label, value) in enumerate(items):
        col, row = i % 3, i // 3
        x, y = 24 + col * 160, 82 + row * 62
        cells.append(
            f'<g class="fade" style="animation-delay:{i * 0.1:.1f}s">'
            f'<text x="{x}" y="{y}" class="v">{value:,}</text>'
            f'<text x="{x}" y="{y + 20}" class="l">{escape(label)}</text></g>')
    return card(500, 200, "GitHub at a glance", "\n  ".join(cells))


def langs_svg(u):
    totals = {}
    colors = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name in SKIP_LANGS:
                continue
            totals[name] = totals.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or MUTED
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    total = sum(v for _, v in top) or 1
    width, bar_w = 360, 312
    parts, x = [], 24.0
    for name, size in top:
        w = bar_w * size / total
        parts.append(f'<rect x="{x:.2f}" y="56" width="{w:.2f}" height="10" fill="{colors[name]}"/>')
        x += w
    bar = (f'<clipPath id="c"><rect x="24" y="56" width="{bar_w}" height="10" rx="5"/></clipPath>'
           f'<g clip-path="url(#c)">{"".join(parts)}</g>')
    legend = []
    for i, (name, size) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = 24 + col * 160, 96 + row * 26
        legend.append(
            f'<g class="fade" style="animation-delay:{i * 0.1:.1f}s">'
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{colors[name]}"/>'
            f'<text x="{lx + 16}" y="{ly}" class="s">{escape(name)} '
            f'<tspan fill="{MUTED}">{100 * size / total:.1f}%</tspan></text></g>')
    return card(width, 200, "Most used languages", bar + "\n  " + "\n  ".join(legend))


def main():
    u = fetch()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "stats.svg"), "w") as f:
        f.write(stats_svg(u))
    with open(os.path.join(OUT, "langs.svg"), "w") as f:
        f.write(langs_svg(u))
    print("Wrote stats.svg and langs.svg")


if __name__ == "__main__":
    main()
