"""Renders the lake-scene images for the README and the LinkedIn banner.

Local only (needs Pillow): `py cards/scene.py [readme] [banner]` (all
when none given; RAIGON=path/to/raigon if it isn't a sibling). Reads the scene
stills from the raigon repo, writes WebPs to assets/scene/ and the LinkedIn PNGs to assets/banner/.
Every image comes in two times of day: sunset for dark mode, morning for light.
The hero also comes as a looping animated WebP made from recorded frames (hero_frames).
"""
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RAIGON = Path(os.environ.get("RAIGON", ROOT.parent / "raigon"))
FONT = Path(__file__).parent / "fonts" / "FamiljenGrotesk.ttf"

# app/site.css tokens, per theme
THEMES = {
    "sunset": {"ink": (241, 234, 220), "muted": (216, 205, 184), "accent": (233, 182, 96), "paper": (27, 24, 20), "glass": 0.46},
    "morning": {"ink": (29, 27, 23), "muted": (74, 68, 58), "accent": (176, 120, 20), "paper": (251, 248, 241), "glass": 0.64},
}

S = 2  # everything is drawn at 2x so it stays sharp on retina screens


def font(size, weight):
    f = ImageFont.truetype(str(FONT), size * S)
    f.set_variation_by_axes([weight])
    return f


def text(draw, xy, s, f, fill, track=0.0, anchor="la"):
    """Draws s with letter-spacing `track` (in em), keeping the font's kerning."""
    x, y = xy
    if not track:
        draw.text((x, y), s, font=f, fill=fill, anchor=anchor)
        return
    em = f.size * track
    for i, ch in enumerate(s):
        draw.text((x + f.getlength(s[:i]) + i * em, y), ch, font=f, fill=fill, anchor=anchor)


def ink_right(s, f, track=0.0):
    """x of the rightmost inked pixel when s is drawn at x=0 with `text`."""
    return f.getlength(s[:-1]) + (len(s) - 1) * f.size * track + f.getbbox(s[-1])[2]


def scene(name):
    return Image.open(RAIGON / "public" / "scene" / f"{name}.webp").convert("RGB")


def crop(img, cx, cy, w, h, zoom=1.0):
    """A w×h (1x px) view of the still centred near (cx, cy) in still px, zoomed in by `zoom`."""
    W, H = w * S, h * S
    scale = max(W / img.width, H / img.height) * zoom
    big = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    x = min(max(round(cx * scale - W / 2), 0), big.width - W)
    y = min(max(round(cy * scale - H / 2), 0), big.height - H)
    return big.crop((x, y, x + W, y + H))


def wash(img, color, stops):
    """Horizontal gradient of `color`; stops are (fraction across, alpha)."""
    w, h = img.size
    row = Image.new("L", (w, 1))
    for x in range(w):
        f = x / (w - 1)
        for (f0, a0), (f1, a1) in zip(stops, stops[1:]):
            if f0 <= f <= f1:
                row.putpixel((x, 0), round(255 * (a0 + (a1 - a0) * (f - f0) / (f1 - f0 or 1))))
                break
    layer = Image.new("RGB", (w, h), color)
    return Image.composite(layer, img, row.resize((w, h)))


def rounded(img, r):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *img.size), r * S, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


HERO_W, HERO_H = 828, 288
# the live hero: frames of raigon's real scene engine, recorded in Chrome (see FRAMES)
FRAMES = Path(__file__).parent / "hero-frames"
FPS, FADE = 15, 12  # the last FADE frames crossfade into the first, so the loop has no seam


def hero_overlay(name, t):
    """The wash and the copy as one transparent layer at 2x, laid over a still or each frame."""
    w, h = HERO_W * S, HERO_H * S
    # morning's sky is bright, so its wash reaches further to keep the copy clear of the trees
    stops = [(0, 0.82), (0.45, 0.6), (0.75, 0)] if name == "sunset" else [(0, 0.85), (0.58, 0.72), (0.88, 0)]
    row = Image.new("L", (w, 1))
    for x in range(w):
        f = x / (w - 1)
        for (f0, a0), (f1, a1) in zip(stops, stops[1:]):
            if f0 <= f <= f1:
                row.putpixel((x, 0), round(255 * (a0 + (a1 - a0) * (f - f0) / (f1 - f0 or 1))))
                break
    layer = Image.new("RGBA", (w, h), (*t["paper"], 0))
    layer.putalpha(row.resize((w, h)))
    d = ImageDraw.Draw(layer)
    x = 40 * S
    text(d, (x, 58 * S), "Rainer Gonzaga", font(60, 700), t["ink"], track=-0.04)
    text(d, (x, 136 * S), "Java Engineer Intern at ING Hubs Philippines", font(21, 500), t["accent"])
    text(d, (x, 170 * S), "Full-stack and AI engineer, trained in cybersecurity.", font(21, 500), t["muted"])
    text(d, (x, 230 * S), "raigon.dev", font(16, 500), t["muted"])
    return layer


def framed(img, scale):
    """Rounded, with the same 6px inset as the cards so the edges line up."""
    w, h = round((HERO_W + 12) * scale), round((HERO_H + 12) * scale)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *img.size), round(16 * scale), fill=255)
    out.paste(img, (round(6 * scale), round(6 * scale)), mask)
    return out


def hero(name, t):
    """The still hero, for reduced motion: the raigon still under the overlay."""
    img = crop(scene(name), 760, 540, HERO_W, HERO_H, zoom=1.1).convert("RGBA")
    return framed(Image.alpha_composite(img, hero_overlay(name, t)), S)


def hero_frames(name, t):
    """The moving hero, or None before frames are recorded.

    FRAMES/hero-<name>-sheet.jpg is a 6-wide grid of 1242x432 frames (1.5x), 1/15 s
    apart, cut from the 1920x1080 canvas at x 0-1745, y 236-843 (the still's
    hero framing). Recorded on https://www.raigon.dev/?shot&dpr=1 (add =morning)
    by forcing innerWidth/innerHeight to 1920x1080, stopping the page's
    requestAnimationFrame loop, then per frame: window.__meadow.step(1/60) x3,
    __meadow.capture() and drawImage into the sheet. (?scroll renders black.)"""
    path = FRAMES / f"hero-{name}-sheet.jpg"
    if not path.exists():
        return None
    sheet = Image.open(path).convert("RGBA")
    fw, fh, cols = 1242, 432, 6
    frames = [sheet.crop(((i % cols) * fw, (i // cols) * fh, (i % cols + 1) * fw, (i // cols + 1) * fh))
              for i in range(cols * (sheet.height // fh))]
    loop = len(frames) - FADE
    frames = [Image.blend(frames[loop + i], frames[i], i / FADE) if i < FADE else frames[i] for i in range(loop)]
    over = hero_overlay(name, t).resize((fw, fh), Image.LANCZOS)
    return [framed(Image.alpha_composite(f, over), fw / HERO_W) for f in frames]


# Everything under the hero is glass over one blurred lake. Every card, the live
# stats and music cards included, is cut from the same sheet at its own spot, so
# the separate images read as one seamless surface.
PROJECTS = {
    "parc-ferme": ("Parc Fermé", "ML / race predictions", "F1 race odds, published every race weekend"),
    "resole": ("ReSole", "Mobile / marketplace", "AI-checked marketplace for used sneakers"),
    "wordwork": ("wordwork", "Offline-first PWA", "Daily German, Italian and Japanese study"),
}
CONTACT = {"web": "raigon.dev", "mail": "rainerdgonzaga@gmail.com", "linkedin": "in/rdgonzaga"}

W, GAP, R = 840, 6, 16  # sheet width, half the gutter between cards, corner radius
# rows top to bottom: (height, [(slug, width)]). stats and music are SVGs rendered
# by render.py; here they only get their slice of the lake (cards/bg-*.jpg), and
# their heights must match STATS_H / MUSIC_H there.
ROWS = [
    (None, [("parc-ferme", 280), ("resole", 280), ("wordwork", 280)]),  # sized by project_row_height
    (236, [("stats", 840)]),
    (160, [("music", 840)]),
    (68, [("web", 280), ("mail", 280), ("linkedin", 280)]),
]
LIVE = {"stats", "music"}


def rows():
    return [(h or project_row_height(cards[0][1]), cards) for h, cards in ROWS]


def layout():
    y = 0
    for h, cards in rows():
        x = 0
        for slug, w in cards:
            yield slug, x, y, w, h
            x += w
        y += h


def lake(name, t):
    """The tinted lake the sheet sits on, at 2x, blurred into a smooth gradient."""
    H = sum(h for h, _ in rows())
    img = crop(scene(name), 900, 600, W, H)
    img = img.resize((W // 8, H // 8), Image.LANCZOS).filter(ImageFilter.GaussianBlur(5))
    img = img.resize((W * S, H * S), Image.BICUBIC)
    return Image.blend(img, Image.new("RGB", img.size, t["paper"]), t["glass"] + 0.08)


def glass(lake_img, x, y, w, h):
    """The card's piece of the lake, inset by the gutter."""
    return lake_img.crop(((x + GAP) * S, (y + GAP) * S, (x + w - GAP) * S, (y + h - GAP) * S))


def finish(card, w, h):
    out = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    out.paste(rounded(card, R), (GAP * S, GAP * S))
    # hairline edge like the site's glass border
    edge = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle((GAP * S, GAP * S, (w - GAP) * S - 1, (h - GAP) * S - 1), R * S,
                                           outline=(255, 255, 255, 34), width=S)
    return Image.alpha_composite(out, edge)


# project cards: one padding on every side, measured from the ink (cap height
# of the name down to the last baseline), and the next baseline a fixed step on
PAD = 22
STEPS = (25, 27, 22)  # name -> type, type -> first line, line -> line


def project_lines(slug, width):
    title, kind, line = PROJECTS[slug]
    f = font(16, 500)
    return ([(title, font(24, 700), "ink", -0.025), (kind, font(15, 500), "accent", 0)]
            + [(ln, f, "ink", 0) for ln in wrap(line, f, width)])


def project_baselines(lines):
    cap = -lines[0][1].getbbox("H", anchor="ls")[1]
    ys = [PAD * S + cap]
    for i in range(1, len(lines)):
        ys.append(ys[-1] + STEPS[min(i - 1, 2)] * S)
    return ys


def project_row_height(w):
    """Tallest project card's inner height plus padding, plus the gutters."""
    inner = (w - 2 * GAP - 2 * PAD) * S
    tallest = max(project_baselines(project_lines(slug, inner))[-1] for slug in PROJECTS)
    return round(tallest / S) + PAD + 2 * GAP


def project_card(card, t, slug):
    d = ImageDraw.Draw(card)
    lines = project_lines(slug, card.width - 2 * PAD * S)
    for (s, f, fill, track), y in zip(lines, project_baselines(lines)):
        text(d, (PAD * S, y), s, f, t[fill], track=track, anchor="ls")


def contact_card(card, t, value):
    d = ImageDraw.Draw(card)
    f = font(17, 700)
    # baseline placed so the capitals sit dead centre
    top = f.getbbox("H", anchor="ls")[1]  # cap height, negative
    text(d, (PAD * S, (card.height - top) // 2), value, f, t["ink"], track=-0.01, anchor="ls")


def wrap(s, f, width, track=0.0):
    lines, cur = [], ""
    for word in s.split():
        nxt = f"{cur} {word}".strip()
        if cur and ink_right(nxt, f, track) > width:
            lines.append(cur)
            cur = word
        else:
            cur = nxt
    return lines + [cur] if cur else lines


def sheet(name, t):
    """{slug: card image}; live cards come back as their 1x background JPG."""
    lake_img = lake(name, t)
    out = {}
    for slug, x, y, w, h in layout():
        card = glass(lake_img, x, y, w, h)
        if slug in LIVE:
            out[slug] = card.resize((card.width // S, card.height // S), Image.LANCZOS)
            continue
        if slug in PROJECTS:
            project_card(card, t, slug)
        else:
            contact_card(card, t, CONTACT[slug])
        out[slug] = finish(card, w, h)
    return out


def banner(name, t):
    """LinkedIn: 1584×396 exactly, so drawn at 1x. The left ~400px of the
    bottom half sits under the avatar, so the copy goes top right."""
    img = scene(name)
    img = img.resize((1584, round(img.height * 1584 / img.width)), Image.LANCZOS)
    y = 268
    img = img.crop((0, y, 1584, y + 396))
    img = wash(img, t["paper"], [(0, 0), (0.5, 0), (0.82, 0.62), (1, 0.75)])
    d = ImageDraw.Draw(img)
    f1, f2 = ImageFont.truetype(str(FONT), 44), ImageFont.truetype(str(FONT), 24)
    f1.set_variation_by_axes([700])
    f2.set_variation_by_axes([500])
    right = 1584 - 64
    # right-align on the ink of the last glyph, not its advance, so all three lines end on one edge
    lines = [(96, "Full-stack and AI engineer,", f1, t["ink"], -0.02),
             (148, "trained in cybersecurity.", f1, t["ink"], -0.02),
             (220, "raigon.dev", f2, t["accent"], 0)]
    for y, s, f, fill, track in lines:
        text(d, (right - ink_right(s, f, track), y), s, f, fill, track=track)
    return img


def main(targets):
    out = ROOT / "assets" / "scene"
    out.mkdir(parents=True, exist_ok=True)
    (ROOT / "assets" / "banner").mkdir(exist_ok=True)
    for name, t in THEMES.items():
        if "readme" in targets:
            hero(name, t).save(out / f"hero-{name}.webp", quality=88, method=6)
            frames = hero_frames(name, t)
            if frames:
                frames[0].save(out / f"hero-{name}-live.webp", save_all=True, append_images=frames[1:],
                               duration=round(1000 / FPS), loop=0, quality=78, method=4)
            for slug, card in sheet(name, t).items():
                if slug in LIVE:  # ships in cards/ so CI and the Vercel function can inline it
                    card.save(ROOT / "cards" / f"bg-{slug}-{name}.jpg", quality=80, optimize=True)
                else:
                    card.save(out / f"{slug}-{name}.webp", quality=88, method=6)
        if "banner" in targets:
            banner(name, t).save(ROOT / "assets" / "banner" / f"linkedin-{name}.png", optimize=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["readme", "banner"])
