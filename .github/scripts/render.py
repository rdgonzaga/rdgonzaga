"""Render every SVG pane in assets/ for the profile README.

Static panes (hero, projects, stack) come from the data below. The stats pane
pulls numbers from the GitHub GraphQL API and is skipped when no token is set.
Run: STATS_TOKEN=$(gh auth token) python .github/scripts/render.py

Animations are CSS so they switch off under prefers-reduced-motion; everything
plays once on load except the cursor blink.
"""
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

USER = "rdgonzaga"
ASSETS = Path(__file__).resolve().parents[2] / "assets"

BG, LINE, TEXT, BODY, MUTED, GREEN, SHADOW = (
    "#0a0c0f", "#2a3038", "#eceef1", "#c3c8ce", "#6b737d", "#4ade80", "#1d4d33")
HEAT = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace"
CHAR = 8.0  # mono advance at 14px; typed lines are pinned to it with textLength so any font lines up
STYLE = f"""<style>
text{{font-family:{MONO};white-space:pre}}
.in{{opacity:0;animation:in .3s ease-out forwards}}
.grow{{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow .7s cubic-bezier(.2,.7,.2,1) forwards}}
.cover{{transform-box:fill-box;transform-origin:right;animation-fill-mode:forwards;animation-name:type}}
.blink{{animation:blink 1.06s steps(1) infinite}}
@keyframes in{{to{{opacity:1}}}}
@keyframes grow{{to{{transform:scaleX(1)}}}}
@keyframes type{{to{{transform:scaleX(0)}}}}
@keyframes blink{{50%{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}.in{{opacity:1}}.grow{{transform:none}}.cover{{display:none}}}}
</style>"""
PROMPT = f'<tspan fill="{GREEN}">rai@raigon</tspan><tspan fill="{MUTED}">:~$ </tspan>'

PROJECTS = [
    ("promptpatrol", "security", ["finds security holes in", "AI-generated web apps"], "python · sast · dast"),
    ("archerbytes", "backend", ["knowledge-sharing platform", "for 20,000+ DLSU students"], "next.js · postgresql · drizzle"),
    ("f1-prediction", "ml", ["predicts F1 race results", "right after qualifying"], "python · xgboost"),
    ("f1-telemetry", "tooling", ["live telemetry dashboard for", "F1 25: 2026 Season Pack"], "python · fastapi · react"),
]
STACK = [
    ("security", "kali · nmap · burp suite · metasploit · wireshark"),
    ("backend", "python · node · java · fastapi · postgresql"),
    ("frontend", "typescript · react · next.js · tailwind"),
]
CONTACT = [
    ("web", "open raigon.dev"),
    ("mail", "mail rainerdgonzaga@gmail.com"),
    ("linkedin", "open in/rdgonzaga"),
]
EXCLUDE_LANGS = {"Jupyter Notebook"}

# ANSI Shadow letters, block rows only; each █ becomes a rect so the art
# doesn't depend on the viewer's font
ART = {
    "R": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║"],
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║"],
    "I": ["██╗", "██║", "██║", "██║", "██║"],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║"],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗"],
    "G": [" ██████╗ ", "██╔════╝ ", "██║  ███╗", "██║   ██║", "╚██████╔╝"],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝"],
    "Z": ["███████╗", "╚══███╔╝", "  ███╔╝ ", " ███╔╝  ", "███████╗"],
    " ": ["  "] * 5,
}


def at(delay):
    return f'style="animation-delay:{delay:.2f}s"'


def typed(x, y, text, delay, per=0.06, size=14, fill=TEXT, prefix="", prefix_len=0):
    """Line whose `text` part is revealed char by char as a background-colored
    cover shrinks toward its right edge. `prefix` (already-escaped SVG) shows at once."""
    c = CHAR * size / 14
    w = len(text) * c + 4
    cx = x + prefix_len * c
    return (f'<text x="{x:.1f}" y="{y}" textLength="{(prefix_len + len(text)) * c:.1f}" lengthAdjust="spacing" '
            f'font-size="{size}">{prefix}<tspan fill="{fill}">{escape(text)}</tspan></text>'
            f'<rect class="cover" x="{cx - 1:.1f}" y="{y - size}" width="{w:.1f}" height="{size + 6}" fill="{BG}" '
            f'style="animation-duration:{len(text) * per:.2f}s;'
            f'animation-timing-function:steps({len(text)});animation-delay:{delay:.2f}s"/>')


def pane(W, H, title, right=None, x0=0, inset=14):
    """TUI box (btop/lazygit style) with the title cut into the top border."""
    x, tw = x0 + inset, len(title) * 7.8 + 16
    parts = [
        f'<rect x="{x}" y="{inset}" width="{W - 2 * inset}" height="{H - 2 * inset}" rx="6" fill="none" stroke="{LINE}"/>',
        f'<rect x="{x + 14}" y="{inset - 8}" width="{tw:.0f}" height="16" fill="{BG}"/>',
        f'<text x="{x + 22}" y="{inset + 4.5}" fill="{GREEN}" font-size="13" font-weight="600">{escape(title)}</text>',
    ]
    if right:
        rw, rx = len(right) * 7.8 + 16, x0 + W - inset
        parts += [
            f'<rect x="{rx - 14 - rw:.0f}" y="{inset - 8}" width="{rw:.0f}" height="16" fill="{BG}"/>',
            f'<text x="{rx - 22}" y="{inset + 4.5}" text-anchor="end" fill="{MUTED}" font-size="13">{escape(right)}</text>',
        ]
    return "".join(parts)


def write_svg(name, W, H, label, body):
    path = ASSETS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{escape(label)}">{STYLE}\n<rect width="{W}" height="{H}" fill="{BG}"/>\n'
        f'{body}\n</svg>\n', encoding="utf-8")


def cursor(x, y, delay):
    return (f'<g class="in" {at(delay)}><rect class="blink" x="{x:.1f}" y="{y - 12}" width="8" height="15" '
            f'fill="{GREEN}"/></g>')


def render_hero():
    W, H, X = 840, 326, 40
    px = X + len("rai@raigon:~$ ") * CHAR

    # 1. type the command
    t = 0.4
    body = pane(W, H, " rai@raigon ", "zsh")
    body += typed(X, 70, "whoami", t, per=0.09, prefix=PROMPT, prefix_len=len("rai@raigon:~$ "))
    t += 6 * 0.09 + 0.25

    # 2. print the name one letter at a time
    cw, ch, ay = 6.4, 12, 108
    col = 0
    for i, c in enumerate("RAINER GONZAGA"):
        letter = ART[c]
        rects = [(X + (col + cx) * cw, ay + ry * ch)
                 for ry, row in enumerate(letter) for cx, v in enumerate(row) if v == "█"]
        col += len(letter[0])
        if not rects:
            continue
        d = t + i * 0.045
        shadow = "".join(f'<rect x="{x + 3:.1f}" y="{y + 3}" width="{cw + .5:.1f}" height="{ch + .5}"/>' for x, y in rects)
        front = "".join(f'<rect x="{x:.1f}" y="{y}" width="{cw + .5:.1f}" height="{ch + .5}"/>' for x, y in rects)
        body += (f'<g class="in" {at(d)} shape-rendering="crispEdges"><g fill="{SHADOW}">{shadow}</g>'
                 f'<g fill="{GREEN}">{front}</g></g>')
    t += 14 * 0.045 + 0.3

    # 3. info lines stream in, then a fresh prompt
    lines = [
        f'cs student <tspan fill="{MUTED}">·</tspan> network &amp; information security <tspan fill="{MUTED}">@</tspan> dlsu',
        f'ex ai &amp; brand design engineer <tspan fill="{MUTED}">@</tspan> decktradr',
        f'backend <tspan fill="{MUTED}">·</tspan> cybersecurity <tspan fill="{MUTED}">·</tspan> machine learning',
    ]
    for i, ln in enumerate(lines):
        body += f'<text class="in" {at(t + i * 0.18)} x="{X}" y="{206 + i * 26}" fill="{BODY}" font-size="15">{ln}</text>'
    t += len(lines) * 0.18 + 0.2
    body += f'<text class="in" {at(t)} x="{X}" y="290" textLength="{len("rai@raigon:~$ ") * CHAR}" lengthAdjust="spacing" font-size="14">{PROMPT}</text>'
    body += f'<text class="in" {at(t)} x="{W - X}" y="290" text-anchor="end" fill="{MUTED}" font-size="13">raigon.dev ↗</text>'
    body += cursor(px, 290, t)
    write_svg("hero.svg", W, H,
              "Terminal: whoami, Rainer Gonzaga. CS student, Network and Information Security at DLSU. "
              "Ex AI and Brand Design Engineer at DeckTradr. Backend, cybersecurity, machine learning.", body)


def render_projects():
    W, H = 420, 176
    for idx, (slug, kind, desc, stack) in enumerate(PROJECTS):
        t = 0.5 + idx * 0.35  # cascade across the grid
        cmd = f"./{slug} --about"
        body = pane(W, H, f" {slug} ", kind)
        body += typed(34, 58, cmd, t, per=0.035, size=13, fill=MUTED,
                      prefix=f'<tspan fill="{GREEN}">$ </tspan>', prefix_len=2)
        t += len(cmd) * 0.035 + 0.2
        for i, d in enumerate(desc):
            body += f'<text class="in" {at(t + i * 0.12)} x="34" y="{88 + i * 24}" fill="{TEXT}" font-size="16">{escape(d)}</text>'
        t += len(desc) * 0.12 + 0.1
        body += f'<text class="in" {at(t)} x="34" y="144" fill="{MUTED}" font-size="12.5"># {escape(stack)}</text>'
        body += f'<text class="in" {at(t + 0.1)} x="{W - 34}" y="144" text-anchor="end" fill="{GREEN}" font-size="14">→</text>'
        write_svg(f"projects/{slug}.svg", W, H, f"{slug}: {' '.join(desc)}. Built with {stack}.", body)


def render_stack():
    W, X = 840, 34
    H = 40 + len(STACK) * 30 + 34
    body = pane(W, H, " stack ", "cat stack.txt")
    for i, (k, v) in enumerate(STACK):
        y, t = 64 + i * 30, 0.4 + i * 0.25
        body += f'<text class="in" {at(t)} x="{X}" y="{y}" fill="{MUTED}" font-size="14">{k}</text>'
        body += typed(X + 110, y, v, t + 0.1, per=0.015, fill=BODY)
    write_svg("stack.svg", W, H, "Stack. " + ". ".join(f"{k}: {v}" for k, v in STACK), body)


def render_contact():
    W, H = 280, 96
    for idx, (slug, cmd) in enumerate(CONTACT):
        body = pane(W, H, f" {slug} ", "↗")
        body += typed(30, 60, cmd, 0.4 + idx * 0.3, per=0.03, size=12.5, fill=BODY,
                      prefix=f'<tspan fill="{GREEN}">$ </tspan>', prefix_len=2)
        write_svg(f"contact/{slug}.svg", W, H, f"{slug}: {cmd.split(' ', 1)[1]}", body)


# ---------- stats from the GitHub API ----------

def graphql(token, query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        out = json.load(resp)
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


def fetch_stats(token):
    user = graphql(token, """
    query($login: String!) {
      user(login: $login) {
        createdAt
        pullRequests { totalCount }
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
          contributionCalendar { totalContributions }
        }
        repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
          totalCount
          nodes {
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } }
            }
          }
        }
      }
    }""", {"login": USER})["user"]

    # Streaks need every day since the account was created, one year per query
    days = {}
    start = datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    while start < now:
        end = min(start + timedelta(days=365), now)
        cal = graphql(token, """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar { weeks { contributionDays { date contributionCount } } }
            }
          }
        }""", {"login": USER, "from": start.isoformat(), "to": end.isoformat()})
        for week in cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        start = end

    ordered = sorted(days.items())
    longest = run = 0
    for _, n in ordered:
        run = run + 1 if n else 0
        longest = max(longest, run)
    current, cursor_day = 0, date.fromisoformat(ordered[-1][0])
    if not days.get(cursor_day.isoformat()):
        cursor_day -= timedelta(days=1)  # today not counted yet doesn't break the streak
    while days.get(cursor_day.isoformat()):
        current += 1
        cursor_day -= timedelta(days=1)

    langs = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            if name not in EXCLUDE_LANGS:
                size, _ = langs.get(name, (0, None))
                langs[name] = (size + e["size"], e["node"]["color"] or BODY)
    total = sum(s for s, _ in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: kv[1][0], reverse=True)[:6]

    cc = user["contributionsCollection"]
    return {
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": user["pullRequests"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in user["repositories"]["nodes"]),
        "current": current,
        "longest": longest,
        "recent": [n for _, n in ordered[-7 * 22:]],
        "langs": [(name, 100 * size / total, color) for name, (size, color) in top],
        "synced": now.strftime("%Y-%m-%d"),
    }


def render_stats(s):
    W, H, half = 840, 354, 420
    body = pane(half, 206, " stats ", "last 12 months") + pane(half, 206, " streak ", x0=half)

    rows = [("contributions", s["contributions"]), ("commits", s["commits"]),
            ("pull requests", s["prs"]), ("public repos", s["repos"]), ("stars", s["stars"])]
    for i, (k, v) in enumerate(rows):
        y, t = 60 + i * 28, 0.4 + i * 0.12
        body += (f'<g class="in" {at(t)}><text x="34" y="{y}" fill="{MUTED}" font-size="14">{k}</text>'
                 f'<text x="{half - 34}" y="{y}" text-anchor="end" fill="{TEXT}" font-size="14" font-weight="600">{v:,}</text></g>')

    sx = half + 34
    body += (f'<g class="in" {at(0.4)}><text x="{sx}" y="60" fill="{MUTED}" font-size="14">current</text>'
             f'<text x="{sx + 90}" y="60" fill="{GREEN}" font-size="14" font-weight="600">{s["current"]} days</text></g>'
             f'<g class="in" {at(0.52)}><text x="{sx}" y="88" fill="{MUTED}" font-size="14">longest</text>'
             f'<text x="{sx + 90}" y="88" fill="{TEXT}" font-size="14" font-weight="600">{s["longest"]} days</text></g>')
    # last ~22 weeks as a heatmap, columns are weeks; quartile shading like
    # GitHub's; cells sweep in left to right
    active = sorted(n for n in s["recent"] if n)
    cuts = [active[len(active) * q // 4] for q in (1, 2, 3)] if active else [1, 1, 1]
    for i, n in enumerate(s["recent"]):
        level = 0 if n == 0 else 1 + sum(n >= c for c in cuts)
        wk, dy = divmod(i, 7)
        body += (f'<rect class="in" {at(0.7 + wk * 0.04 + dy * 0.01)} x="{sx + wk * 15.5:.1f}" y="{106 + dy * 10}" '
                 f'width="13" height="8" rx="1.5" fill="{HEAT[level]}"/>')

    # languages pane: bar segments grow in sequence, legend follows
    top, lx, bw = 214, 34, W - 68
    body += f'<g transform="translate(0,{top - 14})">{pane(W, 154, " languages ", "synced " + s["synced"])}</g>'
    shown = sum(p for _, p, _ in s["langs"]) or 1
    x, t = lx, 1.2
    for name, pct, color in s["langs"]:
        w = bw * pct / shown
        dur = 0.15 + 0.5 * pct / shown
        body += (f'<rect class="grow" style="animation-delay:{t:.2f}s;animation-duration:{dur:.2f}s" '
                 f'x="{x:.1f}" y="{top + 30}" width="{max(w - 2, 1):.1f}" height="8" rx="1" fill="{color}"/>')
        x, t = x + w, t + dur
    for i, (name, pct, color) in enumerate(s["langs"]):
        cx, cy = lx + (i % 3) * (bw / 3), top + 74 + (i // 3) * 30
        body += (f'<g class="in" {at(1.3 + i * 0.1)}><rect x="{cx:.0f}" y="{cy - 9}" width="9" height="9" rx="1" fill="{color}"/>'
                 f'<text x="{cx + 18:.0f}" y="{cy}" fill="{BODY}" font-size="14">{escape(name.lower())}'
                 f'<tspan dx="10" fill="{MUTED}">{pct:.1f}%</tspan></text></g>')
    label = (f"GitHub stats, last 12 months: {s['contributions']} contributions, {s['commits']} commits, "
             f"{s['prs']} pull requests, {s['repos']} public repos, {s['stars']} stars. "
             f"Current streak {s['current']} days, longest {s['longest']} days. Languages: "
             + ", ".join(f"{n} {p:.0f}%" for n, p, _ in s["langs"]) + f". Synced {s['synced']}.")
    write_svg("stats.svg", W, H, label, body)


if __name__ == "__main__":
    render_hero()
    render_projects()
    render_stack()
    render_contact()
    token = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        render_stats(fetch_stats(token))
    else:
        print("no STATS_TOKEN/GITHUB_TOKEN set, skipped stats.svg")
