"""Render the live cards for the profile README: stats from the GitHub GraphQL
API (CI, every 6 hours) and the music card from Last.fm (served by api/music.py).
Each is skipped when its key isn't set. Pass `stats` or `music` to render one.
Run: STATS_TOKEN=$(gh auth token) LASTFM_API_KEY=... python cards/render.py

The static images (hero, projects, skills, contact, banner) come from scene.py.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

USER = "rdgonzaga"
LASTFM_USER = "Reniaaar"
LASTFM_PLACEHOLDER = "2a96cbd8b46e442fc41c2b86b821562f"  # Last.fm's grey star "no art" image
ASSETS = Path(__file__).resolve().parents[1] / "assets"
MANILA = timezone(timedelta(hours=8))  # days for the weekly sparkline; fixed offset, no tzdata needed
WEEK_PAGES = 5  # 200 scrobbles a page, so the sparkline counts up to 1,000 plays a week



# ---------- glass cards ----------
# The live cards match the scene images (cards/scene.py): glass over a blurred
# lake, sunset in dark mode and morning in light. Each card's background is its
# own slice of the shared lake sheet, cut and tinted by scene.py.
CARDS = Path(__file__).resolve().parent
GLASS = {
    "sunset": {"ink": "#f1eadc", "muted": "#d8cdb8", "accent": "#e9b660"},
    "morning": {"ink": "#1d1b17", "muted": "#4a443a", "accent": "#b07814"},
}
SANS = "'Familjen Grotesk', system-ui, -apple-system, 'Segoe UI', sans-serif"
STATS_H, MUSIC_H = 236, 160  # must match the rows in scene.py


def inline(path, kind):
    return f"data:{kind};base64,{base64.b64encode(path.read_bytes()).decode()}"


def glass_svg(slug, theme, W, H, label, body):
    """A rounded card inset 6px; camo blocks outside fetches, so the font and
    the lake are inlined."""
    theme = theme if theme in GLASS else "sunset"
    fonts = "".join(
        f"@font-face{{font-family:'Familjen Grotesk';font-weight:{w};"
        f"src:url({inline(CARDS / 'fonts' / f'familjen-latin-{w}.woff2', 'font/woff2')}) format('woff2')}}"
        for w in (500, 700))
    style = (f"<style>{fonts}text{{font-family:{SANS}}}"
             ".eq{transform-box:fill-box;transform-origin:bottom;animation:eq .9s ease-in-out infinite alternate}"
             "@keyframes eq{from{transform:scaleY(.3)}to{transform:scaleY(1)}}"
             "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")
    bg = inline(CARDS / f"bg-{slug}-{theme}.jpg", "image/jpeg")
    w, h = W - 12, H - 12
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'role="img" aria-label="{escape(label)}">{style}'
            f'<clipPath id="card"><rect x="6" y="6" width="{w}" height="{h}" rx="16"/></clipPath>'
            f'<image href="{bg}" x="6" y="6" width="{w}" height="{h}" preserveAspectRatio="none" clip-path="url(#card)"/>'
            f'<rect x="6.5" y="6.5" width="{w - 1}" height="{h - 1}" rx="15.5" fill="none" stroke="#fff" stroke-opacity=".13"/>'
            f'\n{body}\n</svg>\n')


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
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
          contributionCalendar { totalContributions }
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

    cc = user["contributionsCollection"]
    return {
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "current": current,
        "longest": longest,
        "recent": [n for _, n in ordered[-7 * 52:]],
        "synced": now.strftime("%Y-%m-%d"),
    }


def stats_svg(s, theme="sunset"):
    t = GLASS.get(theme, GLASS["sunset"])
    W, X = 840, 30
    figures = [(s["contributions"], "contributions this year"), (s["commits"], "commits"),
               (s["current"], "day streak"), (s["longest"], "longest streak")]
    body = ""
    for i, (n, label) in enumerate(figures):
        x = X + i * 196
        body += (f'<text x="{x}" y="58" fill="{t["ink"]}" font-size="30" font-weight="700" letter-spacing="-0.8">{n:,}</text>'
                 f'<text x="{x}" y="82" fill="{t["muted"]}" font-size="14" font-weight="500">{label}</text>')

    # the last year as a heatmap, one column per week, in the accent at four strengths
    days = s["recent"][-7 * 52:]
    active = sorted(n for n in days if n)
    cuts = [active[len(active) * q // 4] for q in (1, 2, 3)] if active else [1, 1, 1]
    step = (W - 2 * X) / 52
    for i, n in enumerate(days):
        level = 0 if n == 0 else 1 + sum(n >= c for c in cuts)
        wk, dy = divmod(i, 7)
        fill, op = (t["ink"], 0.08) if level == 0 else (t["accent"], (0.35, 0.55, 0.78, 1)[level - 1])
        body += (f'<rect x="{X + wk * step:.1f}" y="{104 + dy * 14.5:.1f}" width="{step - 3:.1f}" height="11.5" rx="2.5" '
                 f'fill="{fill}" fill-opacity="{op}"/>')
    label = (f"GitHub stats: {s['contributions']} contributions this year, {s['commits']} commits. "
             f"Current streak {s['current']} days, longest {s['longest']} days. Synced {s['synced']}.")
    return glass_svg("stats", theme, W, STATS_H, label, body)


def render_stats(s):
    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in GLASS:
        (ASSETS / f"stats-{theme}.svg").write_text(stats_svg(s, theme), encoding="utf-8")


# ---------- last played from Last.fm ----------

def ago(delta):
    m = int(delta.total_seconds() // 60)
    if m < 1:
        return "just now"
    if m < 60:
        return f"{m}m ago"
    if m < 60 * 24:
        return f"{m // 60}h ago"
    return f"{m // (60 * 24)}d ago"


def clip(text, n):
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def parse_music(recent, info, now):
    tracks = recent["recenttracks"]["track"]
    if isinstance(tracks, dict):  # Last.fm collapses a one-item list into an object
        tracks = [tracks]
    if not tracks:
        return None
    # while something is playing it comes first, ahead of the last finished track
    t = tracks[0]
    playing = t.get("@attr", {}).get("nowplaying") == "true"
    art = next((i["#text"] for i in t.get("image", []) if i["size"] == "extralarge"), "")
    return {
        "track": t["name"],
        "artist": t["artist"]["#text"],
        "album": t["album"]["#text"],
        "playing": playing,
        "ago": None if playing else ago(now - datetime.fromtimestamp(int(t["date"]["uts"]), timezone.utc)),
        "scrobbles": int(info["user"]["playcount"]),
        "art": art if art and LASTFM_PLACEHOLDER not in art else None,
    }


def parse_top(data):
    artists = data["topartists"]["artist"]
    if isinstance(artists, dict):
        artists = [artists]
    return [(a["name"], int(a["playcount"])) for a in artists[:3]]


def parse_playcount(data):
    n = int(data["track"].get("userplaycount", 0))
    return n or None


def week_start(now):
    """Midnight in Manila six days back, so the window is the last 7 local days."""
    today = now.astimezone(MANILA).replace(hour=0, minute=0, second=0, microsecond=0)
    return (today - timedelta(days=6)).astimezone(timezone.utc)


def parse_week(pages, now):
    first = week_start(now).astimezone(MANILA).date()
    days = [0] * 7
    for page in pages:
        tracks = page["recenttracks"]["track"]
        for t in [tracks] if isinstance(tracks, dict) else tracks:
            if "date" not in t:  # the now-playing track isn't a scrobble yet
                continue
            day = datetime.fromtimestamp(int(t["date"]["uts"]), MANILA).date()
            i = (day - first).days
            if 0 <= i < 7:
                days[i] += 1
    return {"total": int(pages[0]["recenttracks"]["@attr"]["total"]), "days": days}


def lastfm(key, method, **params):
    q = urllib.parse.urlencode({"method": method, "user": LASTFM_USER, "api_key": key,
                                "format": "json", "limit": 1, **params})
    url = f"https://ws.audioscrobbler.com/2.0/?{q}"
    try:
        resp = urllib.request.urlopen(url, timeout=20)
    except urllib.error.HTTPError as e:
        if e.code < 500:
            raise
        resp = urllib.request.urlopen(url, timeout=20)  # Last.fm throws the odd 500; one retry clears most
    with resp:
        out = json.load(resp)
    if "error" in out:
        raise RuntimeError(out.get("message", out["error"]))
    return out


def fetch_art(url):
    """Album art inlined as a data URI; camo won't load external images inside an SVG."""
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            kind = resp.headers.get_content_type()
            data = resp.read()
    except OSError as e:
        print(f"album art skipped: {e}")
        return None
    return f"data:{kind};base64,{base64.b64encode(data).decode()}"


def fetch_week(key, now):
    def page(n):
        return lastfm(key, "user.getrecenttracks", limit=200, page=n,
                      **{"from": int(week_start(now).timestamp())})
    first = page(1)
    pages = min(int(first["recenttracks"]["@attr"]["totalPages"]), WEEK_PAGES)
    with ThreadPoolExecutor(4) as pool:
        return parse_week([first, *pool.map(page, range(2, pages + 1))], now)


def optional(fn, *args):
    """The extras shouldn't take the whole card down; they just drop off."""
    try:
        return fn(*args)
    except Exception as e:
        print(f"{fn.__name__} skipped: {e!r}")
        return None


def fetch_music(key):
    now = datetime.now(timezone.utc)
    m = parse_music(lastfm(key, "user.getrecenttracks"), lastfm(key, "user.getinfo"), now)
    if m:
        with ThreadPoolExecutor(4) as pool:
            art = pool.submit(fetch_art, m["art"])
            top = pool.submit(lastfm, key, "user.gettopartists", period="7day", limit=3)
            plays = pool.submit(optional, lambda: parse_playcount(lastfm(
                key, "track.getInfo", artist=m["artist"], track=m["track"], username=LASTFM_USER)))
            week = pool.submit(optional, fetch_week, key, now)
            m.update(art=art.result(), top=parse_top(top.result()), plays=plays.result(), week=week.result())
    return m


def music_svg(m, theme="sunset"):
    """The card as markup; api/music.py serves this live."""
    t = GLASS.get(theme, GLASS["sunset"])
    W, A, Y = 840, 108, 26  # A: art size, Y: art top
    X, R = 26 + A + 24, 600  # track column, this-week column

    if m["art"]:
        body = (f'<clipPath id="art"><rect x="26" y="{Y}" width="{A}" height="{A}" rx="10"/></clipPath>'
                f'<image href="{m["art"]}" x="26" y="{Y}" width="{A}" height="{A}" '
                f'preserveAspectRatio="xMidYMid slice" clip-path="url(#art)"/>')
    else:
        body = (f'<rect x="26" y="{Y}" width="{A}" height="{A}" rx="10" fill="{t["ink"]}" fill-opacity=".08"/>'
                f'<text x="{26 + A / 2}" y="{Y + A / 2 + 13}" text-anchor="middle" fill="{t["muted"]}" font-size="36">♪</text>')

    if m["playing"]:
        for i, d in enumerate((0, .3, .15, .45)):
            body += (f'<rect class="eq" style="animation-delay:{d}s" x="{X + i * 5}" y="42" '
                     f'width="3" height="12" rx="1" fill="{t["accent"]}"/>')
    plays = m.get("plays")
    count = f' · {plays:,} play{"s" if plays != 1 else ""}' if plays else ""
    if m["playing"]:
        body += f'<text x="{X + 28}" y="54" fill="{t["muted"]}" font-size="15" font-weight="500">Now playing{count}</text>'
    else:
        body += f'<text x="{X}" y="54" fill="{t["muted"]}" font-size="15" font-weight="500">Last played {m["ago"]}{count}</text>'
    body += (f'<text x="{X}" y="92" fill="{t["ink"]}" font-size="28" font-weight="700" letter-spacing="-0.5">'
             f'{escape(clip(m["track"], 24))}</text>'
             f'<text x="{X}" y="120" fill="{t["muted"]}" font-size="17" font-weight="500">{escape(clip(m["artist"], 34))}</text>')

    # this week's top artists share the card instead of adding another one
    week = m.get("week")
    head = f'{week["total"]:,} plays this week' if week else "This week"
    body += f'<text x="{R}" y="54" fill="{t["muted"]}" font-size="15" font-weight="500">{head}</text>'
    if week:  # plays per day, oldest first, right-aligned with the counts below
        peak = max(week["days"]) or 1
        for i, n in enumerate(week["days"]):
            h = max(2, round(16 * n / peak))
            fill, op = (t["accent"], .9) if n else (t["ink"], .2)
            body += (f'<rect class="spark" x="{W - 32 - 53 + i * 8}" y="{54 - h}" width="5" height="{h}" '
                     f'rx="1" fill="{fill}" fill-opacity="{op}"/>')
    for i, (name, plays) in enumerate(m["top"]):
        y = 82 + i * 24
        body += (f'<text x="{R}" y="{y}" fill="{t["ink"]}" font-size="16" font-weight="500">{escape(clip(name, 18))}</text>'
                 f'<text x="{W - 32}" y="{y}" text-anchor="end" fill="{t["muted"]}" font-size="16" font-weight="500">{plays}</text>')
    if not m["top"]:
        body += f'<text x="{R}" y="82" fill="{t["muted"]}" font-size="16" font-weight="500">Nothing yet</text>'

    verb = "Now playing" if m["playing"] else "Last played"
    label = f'{verb} on Spotify: {m["track"]} by {m["artist"]}'
    label += f', from {m["album"]}' if m["album"] else ""
    label += f". {m['scrobbles']:,} scrobbles."
    if week:
        label += f" {week['total']:,} plays in the last 7 days."
    if m["top"]:
        label += " Top this week: " + ", ".join(n for n, _ in m["top"]) + "."
    return glass_svg("music", theme, W, MUSIC_H, label, body)


def music_offline_svg(theme="sunset"):
    """Shown by the live endpoint when Last.fm can't be reached."""
    t = GLASS.get(theme, GLASS["sunset"])
    body = (f'<text x="30" y="54" fill="{t["muted"]}" font-size="15" font-weight="500">Last played</text>'
            f'<text x="30" y="92" fill="{t["ink"]}" font-size="26" font-weight="700" letter-spacing="-0.5">'
            f'Last.fm is taking a nap, back soon</text>')
    return glass_svg("music", theme, 840, MUSIC_H, "Last played on Spotify: Last.fm is unavailable right now.", body)


def live_music(key, theme="sunset"):
    """(svg, seconds Vercel's CDN may cache it). Failures get a short TTL so
    the real card comes back soon after Last.fm does."""
    try:
        m = fetch_music(key) if key else None
    except Exception as e:  # any failure should still produce an image, not a 500
        print(f"last.fm failed: {e!r}")
        m = None
    return (music_svg(m, theme), 60) if m else (music_offline_svg(theme), 10)


def render_music(m, theme="sunset"):
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "music.svg").write_text(music_svg(m, theme), encoding="utf-8")


if __name__ == "__main__":
    targets = sys.argv[1:] or ["stats", "music"]
    if "stats" in targets:
        token = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            render_stats(fetch_stats(token))
        else:
            print("no STATS_TOKEN/GITHUB_TOKEN set, skipped stats")
    if "music" in targets:
        key = os.environ.get("LASTFM_API_KEY")
        music = fetch_music(key) if key else None
        if music:
            render_music(music)
        else:
            print("no LASTFM_API_KEY or no scrobbles yet, skipped music.svg")
