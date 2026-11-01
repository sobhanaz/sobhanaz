#!/usr/bin/env python3
"""Build the animated 3D profile cards from live GitHub data.

Usage: GITHUB_TOKEN=... python3 build.py --user sobhanaz --out dist
Writes hero.svg, stats.svg, building.svg and city.svg. Only numbers that match the
public profile are shown, and private repositories are never listed.
"""
import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

PROFILE = {
    "name": "Sobhan Azimzadeh",
    "kicker": "FOUNDER · AI PRODUCT ENGINEER · IRAN · REMOTE",
    "role": "Founder & Technical Lead at TECSO",
    "lines": ["I ship LLM-powered products end-to-end, and the", "infrastructure that keeps them honest."],
    "chips": ["Go", "TypeScript", "Python", "Vue · Nuxt", "Kubernetes", "LLM agents"],
}
# Repos that are about the profile itself, not product work.
EXCLUDE = {"sobhanaz/sobhanaz", "Tecso-Dev/.github"}
BUILDING_DAYS = 90
BUILDING_ROWS = 5

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Inter',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"

# GitSkins "midnight / aura" palette, shared with the TECSO org cards.
C = dict(
    bg0="#020617", bg1="#0f172a", text="#e0e7ff", soft="#cbd5e1", muted="#94a3b8",
    accent="#818cf8", accent2="#a5b4fc", purple="#be5bf6", cyan="#5beaf6", green="#22c55e",
    deep="#1e1b4b",
)

QUERY = """
query($login: String!, $from: DateTime!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    year: contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
    recent: contributionsCollection(from: $from) {
      commitContributionsByRepository(maxRepositories: 25) {
        contributions { totalCount }
        repository { nameWithOwner name isPrivate owner { login } primaryLanguage { name color } }
      }
    }
  }
}
"""


# ---------------------------------------------------------------- data

def fetch(user, token):
    since = (datetime.now(timezone.utc) - timedelta(days=BUILDING_DAYS)).strftime("%Y-%m-%dT00:00:00Z")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user, "from": since}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-cards", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        sys.exit(f"GitHub API error: {payload['errors']}")
    return payload["data"]["user"]


def summarize(u):
    weeks = u["year"]["contributionCalendar"]["weeks"]
    days = [dict(d, week=wi) for wi, w in enumerate(weeks) for d in w["contributionDays"]]
    counts = [d["contributionCount"] for d in days]

    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    tail = counts[:-1] if counts and counts[-1] == 0 else counts  # today may not have started yet
    for c in reversed(tail):
        if not c:
            break
        current += 1
    best = max(days, key=lambda d: d["contributionCount"])

    repos = []
    for item in u["recent"]["commitContributionsByRepository"]:
        r = item["repository"]
        if r["isPrivate"] or r["nameWithOwner"] in EXCLUDE:
            continue
        lang = r["primaryLanguage"] or {}
        repos.append(dict(
            name=r["name"], owner=r["owner"]["login"], commits=item["contributions"]["totalCount"],
            lang=lang.get("name") or "", color=lang.get("color") or C["accent"],
        ))
    repos.sort(key=lambda r: -r["commits"])

    return dict(
        total=u["year"]["contributionCalendar"]["totalContributions"],
        active=sum(1 for c in counts if c), span=len(days), longest=longest, current=current,
        best=best, days=days, weeks=len(weeks),
        followers=u["followers"]["totalCount"], repos_public=u["repositories"]["totalCount"],
        building=repos[:BUILDING_ROWS], building_total=sum(r["commits"] for r in repos),
        updated=date.today().isoformat(),
    )


# ---------------------------------------------------------------- svg helpers

def shade(hex_color, f):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * f))) for v in (r, g, b))


def pts(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def fmt(n):
    return f"{n:,}"


def frame(w, h, uid, body, title, updated=None):
    """Card shell: midnight gradient, drifting aura orbs, glass inner card, 'updated' stamp."""
    stamp = (
        f'<text x="{w - 34}" y="{h - 28}" text-anchor="end" font-family="{MONO}" font-size="10" '
        f'fill="{C["muted"]}" fill-opacity=".8">live from GitHub · updated {updated}</text>'
    ) if updated else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
<title>{escape(title)}</title>
<defs>
  <linearGradient id="{uid}-bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="{C['bg0']}"/><stop offset="54%" stop-color="{C['bg1']}"/><stop offset="100%" stop-color="{C['bg0']}"/></linearGradient>
  <radialGradient id="{uid}-o1"><stop offset="0%" stop-color="{C['accent']}" stop-opacity=".75"/><stop offset="60%" stop-color="{C['accent']}" stop-opacity=".15"/><stop offset="100%" stop-color="{C['accent']}" stop-opacity="0"/></radialGradient>
  <radialGradient id="{uid}-o2"><stop offset="0%" stop-color="{C['purple']}" stop-opacity=".6"/><stop offset="60%" stop-color="{C['purple']}" stop-opacity=".13"/><stop offset="100%" stop-color="{C['purple']}" stop-opacity="0"/></radialGradient>
  <radialGradient id="{uid}-o3"><stop offset="0%" stop-color="{C['cyan']}" stop-opacity=".55"/><stop offset="60%" stop-color="{C['cyan']}" stop-opacity=".12"/><stop offset="100%" stop-color="{C['cyan']}" stop-opacity="0"/></radialGradient>
  <linearGradient id="{uid}-shine" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{C['accent2']}" stop-opacity=".15"/><stop offset="45%" stop-color="{C['accent']}" stop-opacity=".85"/><stop offset="100%" stop-color="{C['purple']}" stop-opacity=".2"/></linearGradient>
  <linearGradient id="{uid}-word" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{C['text']}"/><stop offset="55%" stop-color="{C['accent']}"/><stop offset="100%" stop-color="{C['purple']}"/></linearGradient>
  <linearGradient id="{uid}-sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#fff" stop-opacity="0"/><stop offset="50%" stop-color="#fff" stop-opacity=".16"/><stop offset="100%" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <clipPath id="{uid}-clip"><rect width="{w}" height="{h}" rx="22"/></clipPath>
</defs>
<style>
  .{uid}-a{{animation:{uid}-fa 10s ease-in-out infinite}}
  .{uid}-b{{animation:{uid}-fb 12s ease-in-out infinite 1s}}
  .{uid}-c{{animation:{uid}-fc 14s ease-in-out infinite .5s}}
  .{uid}-float{{animation:{uid}-float 4.5s ease-in-out infinite}}
  .{uid}-bob{{animation:{uid}-bob 5s ease-in-out infinite}}
  .{uid}-pulse{{animation:{uid}-pulse 2.4s ease-in-out infinite}}
  .{uid}-sweep{{animation:{uid}-sweep 5.5s ease-in-out infinite}}
  .{uid}-wave{{opacity:0;animation:{uid}-wave 7s linear infinite}}
  .{uid}-twinkle{{animation:{uid}-twinkle 3.6s ease-in-out infinite}}
  @keyframes {uid}-fa{{0%,100%{{transform:translate(0,0)}}50%{{transform:translate(26px,-18px)}}}}
  @keyframes {uid}-fb{{0%,100%{{transform:translate(0,0)}}50%{{transform:translate(-22px,16px)}}}}
  @keyframes {uid}-fc{{0%,100%{{transform:translate(0,0)}}50%{{transform:translate(16px,-10px)}}}}
  @keyframes {uid}-float{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-9px)}}}}
  @keyframes {uid}-bob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-3px)}}}}
  @keyframes {uid}-pulse{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}
  @keyframes {uid}-sweep{{0%{{transform:translateX(-260px)}}60%,100%{{transform:translateX(1100px)}}}}
  @keyframes {uid}-wave{{0%{{opacity:0}}6%{{opacity:.55}}14%,100%{{opacity:0}}}}
  @keyframes {uid}-twinkle{{0%,100%{{opacity:.15}}50%{{opacity:.9}}}}
  @media (prefers-reduced-motion:reduce){{.{uid}-a,.{uid}-b,.{uid}-c,.{uid}-float,.{uid}-bob,.{uid}-pulse,.{uid}-sweep,.{uid}-wave,.{uid}-twinkle{{animation:none}}}}
</style>
<g clip-path="url(#{uid}-clip)">
  <rect width="{w}" height="{h}" fill="url(#{uid}-bg)"/>
  <g opacity=".55">
    <circle class="{uid}-a" cx="{w * .82:.0f}" cy="{h * .16:.0f}" r="{min(h * .62, 230):.0f}" fill="url(#{uid}-o1)"/>
    <circle class="{uid}-b" cx="{w * .1:.0f}" cy="{h * .95:.0f}" r="{min(h * .55, 210):.0f}" fill="url(#{uid}-o2)"/>
    <circle class="{uid}-c" cx="{w * .97:.0f}" cy="{h * .92:.0f}" r="{min(h * .42, 170):.0f}" fill="url(#{uid}-o3)"/>
  </g>
  <rect x="16" y="16" width="{w - 32}" height="{h - 32}" rx="18" fill="#fff" fill-opacity=".03" stroke="url(#{uid}-shine)" stroke-width="1.2"/>
{body}
  {stamp}
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="21.5" fill="none" stroke="{C['accent']}" stroke-opacity=".35"/>
</svg>
"""


def extruded(x, y, text, size, uid, depth=5, anchor="start", family=SANS, weight=800, spacing=-1):
    """Text with a stacked 3D extrusion under a gradient face."""
    attrs = f'text-anchor="{anchor}" font-family="{family}" font-size="{size}" font-weight="{weight}" letter-spacing="{spacing}"'
    layers = [
        f'<text x="{x + i * .55:.2f}" y="{y + i * .85:.2f}" {attrs} fill="{shade(C["deep"], 1 - i * .08)}">{escape(text)}</text>'
        for i in range(depth, 0, -1)
    ]
    layers.append(f'<text x="{x}" y="{y}" {attrs} fill="url(#{uid}-word)">{escape(text)}</text>')
    return "".join(layers)


def kicker(x, y, text, anchor="start"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{MONO}" font-size="11" letter-spacing="3" fill="{C["muted"]}">{escape(text)}</text>'


def iso_cube(cx, cy, a, color, stroke):
    """Isometric cube whose top-front vertex sits at (cx, cy)."""
    k = .866 * a
    top = [(cx, cy - a), (cx + k, cy - a / 2), (cx, cy), (cx - k, cy - a / 2)]
    right = [(cx, cy), (cx + k, cy - a / 2), (cx + k, cy + a / 2), (cx, cy + a)]
    left = [(cx, cy), (cx, cy + a), (cx - k, cy + a / 2), (cx - k, cy - a / 2)]
    s = f'stroke="{stroke}" stroke-opacity=".55" stroke-width=".8" stroke-linejoin="round"'
    return (
        f'<polygon points="{pts(left)}" fill="{shade(color, .62)}" {s}/>'
        f'<polygon points="{pts(right)}" fill="{shade(color, .45)}" {s}/>'
        f'<polygon points="{pts(top)}" fill="{shade(color, 1.0)}" {s}/>'
    )


# ---------------------------------------------------------------- cards

def hero(s):
    w, h, uid = 860, 320, "h"
    p = PROFILE
    chips, x = [], 44
    for label in p["chips"]:
        cw = len(label) * 7.25 + 26
        chips.append(
            f'<rect x="{x:.1f}" y="268" width="{cw:.1f}" height="28" rx="14" fill="{C["accent"]}" fill-opacity=".12" stroke="{C["accent"]}" stroke-opacity=".35"/>'
            f'<text x="{x + cw / 2:.1f}" y="286.5" text-anchor="middle" font-family="{MONO}" font-size="12" fill="#c7d2fe">{escape(label)}</text>'
        )
        x += cw + 8

    top = s["building"][0] if s["building"] else None
    live = ""
    if top:
        label = f'{top["name"]} · {fmt(top["commits"])} commits in {BUILDING_DAYS} days'
        lw = 124 + len(label) * 7.1
        live = (
            f'<rect x="44" y="226" width="{lw:.0f}" height="30" rx="15" fill="{C["green"]}" fill-opacity=".08" stroke="{C["green"]}" stroke-opacity=".45"/>'
            f'<circle cx="62" cy="241" r="6" fill="{C["green"]}" fill-opacity=".25" class="{uid}-pulse"/><circle cx="62" cy="241" r="3.2" fill="{C["green"]}"/>'
            f'<text x="74" y="245" font-family="{MONO}" font-size="10.5" letter-spacing="1.5" fill="#86efac">NOW SHIPPING</text>'
            f'<text x="180" y="245.5" font-family="{MONO}" font-size="12" fill="{C["text"]}">{escape(label)}</text>'
        )

    # Isometric stack: 3x3 base, 2x2 middle, 1 top, plus a floating cube.
    a, ox, oy = 27, 702, 160
    def at(i, j, k):
        return ox + (i - j) * .866 * a, oy + (i + j) * a / 2 - k * a
    cubes = [(i, j, 0, "#312e81") for i in range(3) for j in range(3)]
    cubes += [(i + .5, j + .5, 1, "#4f46e5") for i in range(2) for j in range(2)]
    cubes += [(1, 1, 2, "#6366f1")]
    cubes.sort(key=lambda c: (c[2], c[0] + c[1]))
    stack = "".join(iso_cube(*at(i, j, k), a, col, C["accent2"]) for i, j, k, col in cubes)
    fx, fy = at(1, 1, 3.55)
    shadow_x, shadow_y = at(1, 1, 2)
    stars = "".join(
        f'<circle class="{uid}-twinkle" style="animation-delay:{d}s" cx="{sx}" cy="{sy}" r="{r}" fill="{C["accent2"]}"/>'
        for sx, sy, r, d in [(590, 70, 1.4, 0), (812, 96, 1.2, 1.1), (606, 262, 1.1, 2.0), (824, 240, 1.5, .6), (760, 54, 1, 1.7)]
    )
    orbit = "M 545 176 a 155 46 0 1 0 310 0 a 155 46 0 1 0 -310 0"
    body = f"""  {kicker(44, 52, p['kicker'])}
  {extruded(42, 120, p['name'], 50, uid, depth=6, spacing=-1.5)}
  <text x="44" y="156" font-family="{SANS}" font-size="18" font-weight="600" fill="{C['soft']}">{escape(p['role'])}</text>
  <text x="44" y="188" font-family="{SANS}" font-size="14.5" fill="{C['muted']}">{escape(p['lines'][0])}</text>
  <text x="44" y="209" font-family="{SANS}" font-size="14.5" fill="{C['muted']}">{escape(p['lines'][1])}</text>
  {live}
  {''.join(chips)}
  {stars}
  <path d="{orbit}" fill="none" stroke="{C['accent']}" stroke-opacity=".28" stroke-dasharray="2 7"/>
  <ellipse cx="{shadow_x:.0f}" cy="{oy + 3 * a + 8:.0f}" rx="138" ry="30" fill="{C['accent']}" fill-opacity=".10"/>
  {stack}
  <ellipse cx="{shadow_x:.1f}" cy="{shadow_y - a / 2:.1f}" rx="16" ry="6" fill="#000" fill-opacity=".35"/>
  <g class="{uid}-float">{iso_cube(fx, fy, a * .82, "#a5b4fc", "#e0e7ff")}
    <polygon points="{pts([(fx, fy - a * .82), (fx + .866 * a * .82, fy - a * .41), (fx, fy), (fx - .866 * a * .82, fy - a * .41)])}" fill="#fff" fill-opacity=".25"/></g>
  <circle r="4" fill="{C['cyan']}"><animateMotion dur="9s" repeatCount="indefinite" path="{orbit}"/></circle>
  <circle r="3" fill="{C['purple']}"><animateMotion dur="9s" begin="-4.5s" repeatCount="indefinite" path="{orbit}"/></circle>"""
    return frame(w, h, uid, body, f"{p['name']} — {p['role']}")


def stats(s):
    w, h, uid = 860, 222, "s"
    tiles = [
        ("CONTRIBUTIONS", fmt(s["total"]), "in the last year", C["accent"]),
        ("ACTIVE DAYS", fmt(s["active"]), f"of the last {s['span']}", C["purple"]),
        ("LONGEST STREAK", fmt(s["longest"]), "days in a row", C["cyan"]),
        ("PUBLIC REPOS", fmt(s["repos_public"]), "on GitHub", C["accent2"]),
        ("FOLLOWERS", fmt(s["followers"]), "on GitHub", "#f0abfc"),
    ]
    tw, th, depth, gap = 146, 100, 9, 16
    x0 = (w - (5 * tw + 4 * gap + depth)) / 2
    out = [kicker(44, 48, "ACTIVITY · LAST 12 MONTHS")]
    for i, (label, value, cap, color) in enumerate(tiles):
        x, y = x0 + i * (tw + gap), 66
        cid = f"{uid}-t{i}"
        out.append(
            f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y}" width="{tw}" height="{th}" rx="10"/></clipPath>'
            f'<g class="{uid}-bob" style="animation-delay:{-i * .6:.1f}s">'
            f'<polygon points="{pts([(x + tw - 6, y + 4), (x + tw + depth, y + depth + 4), (x + tw + depth, y + th + depth - 6), (x + tw - 6, y + th - 4)])}" fill="{shade(color, .32)}"/>'
            f'<polygon points="{pts([(x + 6, y + th - 2), (x + tw - 4, y + th - 2), (x + tw + depth - 2, y + th + depth), (x + depth + 4, y + th + depth)])}" fill="{shade(color, .22)}"/>'
            f'<rect x="{x:.1f}" y="{y}" width="{tw}" height="{th}" rx="10" fill="{C["bg1"]}" stroke="{color}" stroke-opacity=".55"/>'
            f'<rect x="{x:.1f}" y="{y}" width="{tw}" height="{th}" rx="10" fill="{color}" fill-opacity=".07"/>'
            f'<g clip-path="url(#{cid})"><rect class="{uid}-sweep" style="animation-delay:{i * .35:.2f}s" x="{x - 120:.1f}" y="{y}" width="110" height="{th}" fill="url(#{uid}-sweep)"/></g>'
            f'<text x="{x + 14:.1f}" y="{y + 24}" font-family="{MONO}" font-size="9.5" letter-spacing="1.8" fill="{C["muted"]}">{label}</text>'
            f'{extruded(x + 13, y + 64, value, 32, uid, depth=4, spacing=-.5)}'
            f'<text x="{x + 14:.1f}" y="{y + 86}" font-family="{SANS}" font-size="11.5" fill="{C["soft"]}">{escape(cap)}</text>'
            f'</g>'
        )
    return frame(w, h, uid, "  " + "\n  ".join(out), f"{fmt(s['total'])} contributions in the last year, {s['active']} active days, longest streak {s['longest']} days", s["updated"])


def building(s):
    rows = s["building"]
    w, uid = 860, "b"
    h = 140 + max(1, len(rows)) * 48 + 30
    out = [
        kicker(44, 50, f"WHAT I'M BUILDING · LAST {BUILDING_DAYS} DAYS"),
        f'<text x="44" y="80" font-family="{SANS}" font-size="20" font-weight="700" fill="{C["text"]}">Public commits by project</text>',
        f'<text x="{w - 44}" y="80" text-anchor="end" font-family="{MONO}" font-size="13" fill="{C["accent2"]}">{fmt(s["building_total"])} commits</text>',
    ]
    top = max((r["commits"] for r in rows), default=1)
    bx, bmax, depth = 330, 380, 7
    for i, r in enumerate(rows):
        y = 112 + i * 48
        length = max(12, bmax * r["commits"] / top)
        color = r["color"]
        front = [(bx, y + 8), (bx + length, y + 8), (bx + length, y + 28), (bx, y + 28)]
        topf = [(bx, y + 8), (bx + depth, y + 8 - depth), (bx + length + depth, y + 8 - depth), (bx + length, y + 8)]
        side = [(bx + length, y + 8), (bx + length + depth, y + 8 - depth), (bx + length + depth, y + 28 - depth), (bx + length, y + 28)]
        cid = f"{uid}-r{i}"
        name = r["name"] if len(r["name"]) <= 30 else r["name"][:29] + "…"
        out.append(
            f'<text x="44" y="{y + 18}" font-family="{SANS}" font-size="14.5" font-weight="700" fill="{C["text"]}">{escape(name)}</text>'
            f'<circle cx="49" cy="{y + 32}" r="4" fill="{color}"/>'
            f'<text x="59" y="{y + 36}" font-family="{MONO}" font-size="11" fill="{C["muted"]}">{escape(r["owner"])}{(" · " + escape(r["lang"])) if r["lang"] else ""}</text>'
            f'<polygon points="{pts(topf)}" fill="{shade(color, 1.15)}" fill-opacity=".95"/>'
            f'<polygon points="{pts(side)}" fill="{shade(color, .5)}"/>'
            f'<polygon points="{pts(front)}" fill="{shade(color, .8)}"/>'
            f'<clipPath id="{cid}"><polygon points="{pts(front)}"/></clipPath>'
            f'<g clip-path="url(#{cid})"><rect class="{uid}-sweep" style="animation-delay:{i * .4:.1f}s" x="{bx - 120}" y="{y + 8}" width="110" height="20" fill="url(#{uid}-sweep)"/></g>'
            f'<text x="{bx + length + depth + 12:.1f}" y="{y + 24}" font-family="{MONO}" font-size="13" font-weight="700" fill="{C["text"]}">{fmt(r["commits"])}</text>'
        )
    if not rows:
        out.append(f'<text x="44" y="130" font-family="{SANS}" font-size="14" fill="{C["muted"]}">No public commits in this window.</text>')
    out.append(f'<text x="44" y="{h - 28}" font-family="{MONO}" font-size="10" fill="{C["muted"]}" fill-opacity=".8">Public repositories only · private client work is not listed</text>')
    return frame(w, h, uid, "  " + "\n  ".join(out), f"What I'm building: public commits by project in the last {BUILDING_DAYS} days", s["updated"])


def city(s):
    w, h, uid = 860, 452, "c"
    days = s["days"]
    nonzero = sorted(d["contributionCount"] for d in days if d["contributionCount"])
    top = nonzero[-1] if nonzero else 1
    q = [nonzero[int(len(nonzero) * f)] for f in (.25, .5, .75)] if nonzero else [1, 1, 1]
    levels = ["#3730a3", "#4f46e5", "#8b5cf6", "#22d3ee"]

    ux, uy, vx, vy = 12.2, 3.0, -8.0, 6.2
    weeks = s["weeks"]
    x0 = (w - (weeks * ux + 7 * -vx)) / 2 + 7 * -vx
    y0 = 184

    def base(wk, d):
        return x0 + wk * ux + d * vx, y0 + wk * uy + d * vy

    # Floor under the whole grid.
    f0, f1, f2, f3 = base(-.6, -.6), base(weeks + .2, -.6), base(weeks + .2, 7.2), base(-.6, 7.2)
    out = [
        kicker(44, 50, "CONTRIBUTION CITY · LAST 12 MONTHS"),
        f'<text x="44" y="80" font-family="{SANS}" font-size="20" font-weight="700" fill="{C["text"]}">{fmt(s["total"])} contributions, one tower per day</text>',
        f'<polygon points="{pts([f0, f1, f2, f3])}" fill="{C["accent"]}" fill-opacity=".05" stroke="{C["accent"]}" stroke-opacity=".25"/>',
    ]
    shrink = .84
    cells = sorted(days, key=lambda d: (d["week"] * uy + d["weekday"] * vy, d["week"]))
    for d in cells:
        c = d["contributionCount"]
        bx, by = base(d["week"], d["weekday"])
        p0, p1 = (bx, by), (bx + ux * shrink, by + uy * shrink)
        p2, p3 = (bx + (ux + vx) * shrink, by + (uy + vy) * shrink), (bx + vx * shrink, by + vy * shrink)
        if not c:
            out.append(f'<polygon points="{pts([p0, p1, p2, p3])}" fill="{C["accent"]}" fill-opacity=".09"/>')
            continue
        lvl = sum(c > t for t in q)
        color = levels[lvl]
        hgt = 5 + 72 * math.log1p(c) / math.log1p(top)
        up = lambda p: (p[0], p[1] - hgt)
        out.append(
            f'<polygon points="{pts([p3, p2, up(p2), up(p3)])}" fill="{shade(color, .62)}"/>'
            f'<polygon points="{pts([p1, p2, up(p2), up(p1)])}" fill="{shade(color, .45)}"/>'
            f'<polygon points="{pts([up(p0), up(p1), up(p2), up(p3)])}" fill="{color}"/>'
            f'<polygon class="{uid}-wave" style="animation-delay:{d["week"] * .1 - 7:.2f}s" points="{pts([up(p0), up(p1), up(p2), up(p3)])}" fill="#fff"/>'
        )
        if d is s["best"]:
            bxp, byp = up(p0)[0] + (ux + vx) * shrink / 2, up(p0)[1] + (uy + vy) * shrink / 2
            out.append(
                f'<line x1="{bxp:.1f}" y1="{byp - 4:.1f}" x2="{bxp:.1f}" y2="{byp - 26:.1f}" stroke="{C["cyan"]}" stroke-opacity=".8"/>'
                f'<circle cx="{bxp:.1f}" cy="{byp - 28:.1f}" r="3" fill="{C["cyan"]}" class="{uid}-pulse"/>'
                f'<text x="{bxp:.1f}" y="{byp - 36:.1f}" text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{C["cyan"]}">best day · {c}</text>'
            )

    # Month labels along the front edge.
    seen = None
    for d in days:
        if d["weekday"] != 0:
            continue
        m = d["date"][:7]
        if m != seen and d["week"] < weeks - 2:
            seen = m
            lx, ly = base(d["week"], 7.6)
            out.append(f'<text x="{lx:.1f}" y="{ly + 12:.1f}" font-family="{MONO}" font-size="10" fill="{C["muted"]}">{datetime.strptime(m, "%Y-%m").strftime("%b")}</text>')

    best = s["best"]
    best_label = datetime.strptime(best["date"], "%Y-%m-%d").strftime("%b %-d")
    facts = f'{fmt(s["active"])} active days · longest streak {s["longest"]} days · current streak {s["current"]} days · best day {best["contributionCount"]} on {best_label}'
    out.append(f'<text x="44" y="{h - 28}" font-family="{MONO}" font-size="10.5" fill="{C["soft"]}">{escape(facts)}</text>')
    legend_x = w - 44 - 4 * 18 - 60
    out.append(f'<text x="{legend_x - 8}" y="78" text-anchor="end" font-family="{MONO}" font-size="10" fill="{C["muted"]}">less</text>')
    for i, col in enumerate(levels):
        out.append(f'<rect x="{legend_x + i * 18}" y="68" width="13" height="13" rx="3" fill="{col}"/>')
    out.append(f'<text x="{legend_x + 4 * 18 + 4}" y="78" font-family="{MONO}" font-size="10" fill="{C["muted"]}">more</text>')
    return frame(w, h, uid, "  " + "\n  ".join(out), f"Contribution city: {fmt(s['total'])} contributions in the last year as 3D towers", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    s = summarize(fetch(args.user, token))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in (("hero", hero), ("stats", stats), ("building", building), ("city", city)):
        (out / f"{name}.svg").write_text(fn(s), encoding="utf-8")
    print(json.dumps({k: v for k, v in s.items() if k not in ("days",)}, default=str, indent=1))


if __name__ == "__main__":
    main()
