"""Generate the animated SVGs and the dynamic README sections from profile.json.

Usage: python3 scripts/build.py
Set GH_TOKEN to refresh stats and the "recently shipped" list from the GitHub API.
Stats only refresh when PROFILE_TOKEN is set, because the default Actions token
can't see private repos and would undercount.
"""

import json
import math
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PROFILE = json.loads((ROOT / "profile.json").read_text())

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
BG_0, BG_1 = "#0a0d16", "#11132a"


def write(path, svg):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(re.sub(r"\n\s*\n", "\n", svg.strip()) + "\n")


def wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


# --------------------------------------------------------------------------- header

def typing_timeline(words, char_w):
    """Discrete keyframes (seconds, width, active word) for a type/hold/delete loop."""
    frames, t = [], 0.0
    for i, word in enumerate(words):
        for n in range(len(word) + 1):
            frames.append((t, n * char_w, i))
            t += 0.075
        t += 1.6
        for n in range(len(word) - 1, -1, -1):
            frames.append((t, n * char_w, i))
            t += 0.03
        t += 0.35
    return frames, t


def smil_discrete(attr, frames, total, value):
    key_times = ";".join(f"{f[0] / total:.4f}" for f in frames)
    values = ";".join(f"{value(f):.1f}" for f in frames)
    return (f'<animate attributeName="{attr}" dur="{total:.2f}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="{key_times}" values="{values}"/>')


def constellation(cx, cy):
    rnd = [0.13, 0.71, 0.42, 0.88, 0.27, 0.56, 0.94, 0.05, 0.63, 0.38, 0.81, 0.19, 0.5, 0.33, 0.76, 0.09, 0.67, 0.44]
    nodes = []
    for ring, (count, radius) in enumerate([(1, 0), (6, 72), (11, 150)]):
        for k in range(count):
            a = 2 * math.pi * k / max(count, 1) + ring * 0.4
            jitter = 1 + (rnd[(k + ring * 5) % len(rnd)] - 0.5) * 0.35
            nodes.append((cx + math.cos(a) * radius * jitter * 1.25, cy + math.sin(a) * radius * jitter * 0.82, ring))
    edges = []
    for i, a in enumerate(nodes):
        dists = sorted((math.dist(a[:2], b[:2]), j) for j, b in enumerate(nodes) if j != i)
        for _, j in dists[:3]:
            if (j, i) not in edges:
                edges.append((i, j))
    out = []
    for n, (i, j) in enumerate(edges):
        (x1, y1, _), (x2, y2, _) = nodes[i], nodes[j]
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="edge"/>')
        if n % 3 == 0:
            dur = 2.2 + rnd[n % len(rnd)] * 2.5
            out.append(f'<circle r="2.6" fill="url(#pulse)" opacity="0">'
                       f'<animateMotion dur="{dur:.2f}s" begin="{rnd[(n + 3) % len(rnd)] * 3:.2f}s" repeatCount="indefinite" '
                       f'path="M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}"/>'
                       f'<animate attributeName="opacity" values="0;1;1;0" dur="{dur:.2f}s" begin="{rnd[(n + 3) % len(rnd)] * 3:.2f}s" repeatCount="indefinite"/>'
                       f'</circle>')
    for k, (x, y, ring) in enumerate(nodes):
        r = [9, 5, 3.5][ring]
        delay = rnd[k % len(rnd)] * 4
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 2.6:.1f}" fill="url(#glow)" class="twinkle" style="animation-delay:{delay:.2f}s"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" class="node n{ring}"/>')
    return "\n".join(out)


def header():
    p = PROFILE
    fs, char_w = 22, 22 * 0.6
    term_x = 92 + len("$ now building ") * char_w
    frames, total = typing_timeline(p["building"], char_w)
    words = []
    for i, word in enumerate(p["building"]):
        words.append(f'''
      <clipPath id="w{i}"><rect x="{term_x:.1f}" y="300" height="40" width="0">
        {smil_discrete("width", frames, total, lambda f, i=i: f[1] if f[2] == i else 0)}
      </rect></clipPath>
      <text x="{term_x:.1f}" y="327" clip-path="url(#w{i})" class="mono typed">{escape(word)}</text>''')
    cursor = smil_discrete("x", frames, total, lambda f: term_x + f[1] + 2)
    return f'''
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="420" viewBox="0 0 1200 420" role="img" aria-label="{escape(p["name"])}, {escape(p["role"])}. {escape(p["headline"])}">
  <title>{escape(p["name"])} · {escape(p["role"])}</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG_0}"/><stop offset="1" stop-color="{BG_1}"/></linearGradient>
    <linearGradient id="ink" x1="0" y1="0" x2="1200" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#a78bfa"/><stop offset="0.33" stop-color="#22d3ee"/><stop offset="0.66" stop-color="#f472b6"/><stop offset="1" stop-color="#a78bfa"/>
      <animateTransform attributeName="gradientTransform" type="translate" values="0 0;-600 0;0 0" dur="10s" repeatCount="indefinite"/>
    </linearGradient>
    <radialGradient id="glow"><stop offset="0" stop-color="#a5b4fc" stop-opacity="0.55"/><stop offset="1" stop-color="#a5b4fc" stop-opacity="0"/></radialGradient>
    <radialGradient id="pulse"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#22d3ee"/></radialGradient>
    <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="70"/></filter>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="#fff" stroke-opacity="0.045"/></pattern>
    <linearGradient id="fade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0.15"/><stop offset="0.6" stop-color="#fff" stop-opacity="1"/></linearGradient>
    <mask id="gridmask"><rect width="1200" height="420" fill="url(#fade)"/></mask>
    <clipPath id="frame"><rect width="1200" height="420" rx="28"/></clipPath>
  </defs>
  <style>
    .sans {{ font-family: {SANS}; }}
    .mono {{ font-family: {MONO}; }}
    .edge {{ stroke: #a5b4fc; stroke-opacity: 0.16; stroke-width: 1; }}
    .node {{ fill: #c7d2fe; }}
    .n0 {{ fill: #fff; }}
    .twinkle {{ animation: twinkle 4s ease-in-out infinite; opacity: 0.2; }}
    @keyframes twinkle {{ 0%,100% {{ opacity: 0.15; }} 50% {{ opacity: 0.9; }} }}
    .dot {{ animation: blink 1.6s ease-in-out infinite; }}
    @keyframes blink {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.25; }} }}
    .wave {{ transform-box: fill-box; transform-origin: 70% 80%; animation: wave 2.6s ease-in-out infinite; }}
    @keyframes wave {{ 0%,60%,100% {{ transform: rotate(0); }} 10%,30% {{ transform: rotate(16deg); }} 20%,40% {{ transform: rotate(-8deg); }} }}
    .caret {{ animation: caret 1s steps(1) infinite; }}
    @keyframes caret {{ 50% {{ opacity: 0; }} }}
    .typed {{ fill: #67e8f9; font-size: {fs}px; }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>
  <g clip-path="url(#frame)">
    <rect width="1200" height="420" fill="url(#bg)"/>
    <g filter="url(#blur)" opacity="0.55">
      <circle cx="160" cy="40" r="170" fill="#7c3aed"><animateTransform attributeName="transform" type="translate" values="0 0;90 50;0 0" dur="16s" repeatCount="indefinite"/></circle>
      <circle cx="1040" cy="380" r="190" fill="#0891b2"><animateTransform attributeName="transform" type="translate" values="0 0;-110 -40;0 0" dur="19s" repeatCount="indefinite"/></circle>
      <circle cx="760" cy="10" r="130" fill="#db2777" opacity="0.7"><animateTransform attributeName="transform" type="translate" values="0 0;-60 70;0 0" dur="14s" repeatCount="indefinite"/></circle>
    </g>
    <rect width="1200" height="420" fill="url(#grid)" mask="url(#gridmask)"/>
    <g>{constellation(945, 210)}</g>
  </g>
  <rect x="0.5" y="0.5" width="1199" height="419" rx="28" fill="none" stroke="#fff" stroke-opacity="0.08"/>

  <g>
    <rect x="64" y="64" width="{58 + len(p["role"]) * 10.4:.0f}" height="34" rx="17" fill="#fff" fill-opacity="0.06" stroke="#fff" stroke-opacity="0.12"/>
    <circle cx="84" cy="81" r="5" fill="#4ade80" class="dot"/>
    <text x="100" y="86.5" class="mono" font-size="14" letter-spacing="2.5" fill="#c7d2fe">{escape(p["role"].upper())}</text>
  </g>
  <g>
    <text x="62" y="182" class="sans" font-size="76" font-weight="800" letter-spacing="-2.5" fill="#fff">Hi, I'm {escape(p["name"])}<tspan fill="#a78bfa">.</tspan></text>
    <text x="{90 + (len(p["name"]) + 9) * 28:.0f}" y="178" font-size="58" class="wave">👋</text>
  </g>
  <g>
    <text x="64" y="240" class="sans" font-size="30" font-weight="600" letter-spacing="-0.5" fill="url(#ink)">{escape(p["headline"])}</text>
  </g>
  <g>
    <rect x="64" y="292" width="560" height="52" rx="12" fill="#000" fill-opacity="0.35" stroke="#fff" stroke-opacity="0.1"/>
    <text x="92" y="327" class="mono" font-size="{fs}" fill="#6b7280">$ <tspan fill="#e5e7eb">now building</tspan></text>
    {"".join(words)}
    <rect x="{term_x:.1f}" y="308" width="11" height="24" fill="#67e8f9" class="caret">{cursor}</rect>
  </g>
</svg>'''


# --------------------------------------------------------------------------- cards

def art(kind, a1, a2):
    """Small animated illustration, drawn in a 200x170 box."""
    dim = 'stroke="#fff" stroke-opacity="0.14" fill="none"'
    if kind == "radar":
        blips = "".join(
            f'<circle cx="{100 + math.cos(t) * r:.0f}" cy="{85 + math.sin(t) * r:.0f}" r="4" fill="{a1}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;0" keyTimes="0;{d};{d + 0.03:.2f};1" dur="4s" repeatCount="indefinite"/></circle>'
            for t, r, d in [(-1.1, 50, 0.07), (0.4, 68, 0.32), (2.1, 34, 0.58), (3.6, 60, 0.83)])
        return f'''
      {"".join(f'<circle cx="100" cy="85" r="{r}" {dim}/>' for r in (26, 52, 78))}
      <path d="M22 85H178M100 7V163" {dim}/>
      <g><path d="M100 85L100 7A78 78 0 0 1 167.5 46Z" fill="url(#sweep)"/>
        <animateTransform attributeName="transform" type="rotate" from="0 100 85" to="360 100 85" dur="4s" repeatCount="indefinite"/></g>
      {blips}
      <circle cx="100" cy="85" r="4" fill="#fff"/>'''
    if kind == "screenshot":
        rows = "".join(f'<rect x="{38 if i % 3 else 30}" y="{52 + i * 17}" width="{[120, 96, 132, 80, 110, 70][i]}" height="7" rx="3.5" fill="#fff" fill-opacity="0.12"/>' for i in range(6))
        corners = "".join(f'<path d="{d}" stroke="{a1}" stroke-width="3" fill="none" stroke-linecap="round"/>' for d in
                          ["M12 30V14H28", "M172 14H188V30", "M188 140V156H172", "M28 156H12V140"])
        return f'''
      <rect x="20" y="22" width="160" height="126" rx="10" fill="#fff" fill-opacity="0.04" stroke="#fff" stroke-opacity="0.16"/>
      <path d="M20 40H180" stroke="#fff" stroke-opacity="0.12"/>
      {"".join(f'<circle cx="{32 + i * 10}" cy="31" r="2.6" fill="#fff" fill-opacity="0.25"/>' for i in range(3))}
      {rows}
      <rect x="20" y="40" width="160" height="22" fill="url(#scan)"><animate attributeName="y" values="40;126;40" dur="3.2s" repeatCount="indefinite"/></rect>
      <g>{corners}<animate attributeName="opacity" values="0.35;1;0.35" dur="1.6s" repeatCount="indefinite"/></g>'''
    if kind == "rewrite":
        lines = "".join(f'<rect x="20" y="{24 + i * 26}" width="{w}" height="9" rx="4.5" fill="#fff" fill-opacity="0.13"/>'
                        for i, w in enumerate([150, 120, 0, 140, 96]) if w)
        return f'''
      {lines}
      <rect x="20" y="76" width="164" height="9" rx="4.5" fill="#f87171" fill-opacity="0.75">
        <animate attributeName="width" values="164;164;0;0;164" keyTimes="0;0.3;0.45;0.9;1" dur="4.5s" repeatCount="indefinite"/></rect>
      <path d="M14 80.5H190" stroke="#f87171" stroke-width="2" stroke-dasharray="176" stroke-dashoffset="176">
        <animate attributeName="stroke-dashoffset" values="176;176;0;0;176" keyTimes="0;0.1;0.25;0.9;1" dur="4.5s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;0.3;0.4;0.95;1" dur="4.5s" repeatCount="indefinite"/></path>
      <rect x="20" y="76" width="0" height="9" rx="4.5" fill="{a1}">
        <animate attributeName="width" values="0;0;110;110;0" keyTimes="0;0.45;0.6;0.9;1" dur="4.5s" repeatCount="indefinite"/></rect>
      <text x="20" y="160" font-family="{MONO}" font-size="13" fill="{a1}" opacity="0">✓ sounds human
        <animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;0.6;0.65;0.9;1" dur="4.5s" repeatCount="indefinite"/></text>'''
    if kind == "ledger":
        cells = []
        for r in range(5):
            for c in range(3):
                w = [70, 46, 40][c]
                x = [16, 98, 156][c]
                d = (r * 3 + c) / 15
                cells.append(f'<rect x="{x}" y="{22 + r * 26}" width="{w}" height="16" rx="4" fill="#fff" fill-opacity="0.08">'
                             f'<animate attributeName="fill" values="#ffffff;{a1};#ffffff" keyTimes="0;0.5;1" dur="0.9s" begin="{d * 3:.2f}s;b{r}{c}.end+2.1s" id="b{r}{c}"/>'
                             f'<animate attributeName="fill-opacity" values="0.08;0.8;0.08" keyTimes="0;0.5;1" dur="0.9s" begin="{d * 3:.2f}s;c{r}{c}.end+2.1s" id="c{r}{c}"/></rect>')
        return f'''
      <rect x="6" y="12" width="196" height="138" rx="10" fill="#fff" fill-opacity="0.03" stroke="#fff" stroke-opacity="0.14"/>
      {"".join(cells)}
      <circle cx="176" cy="150" r="16" fill="{a2}"/><path d="M169 150l5 5 9-10" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'''
    if kind == "chart":
        pts = [(10, 130), (34, 112), (58, 120), (82, 88), (106, 96), (130, 62), (154, 72), (178, 34), (194, 40)]
        d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        candles = "".join(
            f'<g><path d="M{x} {y - 14}V{y + 14}" stroke="#fff" stroke-opacity="0.25"/><rect x="{x - 5}" y="{y - 8}" width="10" height="16" rx="2" fill="{a1 if i % 3 else "#f87171"}" fill-opacity="0.55"/></g>'
            for i, (x, y) in enumerate(pts[1:-1]))
        return f'''
      {"".join(f'<path d="M0 {y}H200" stroke="#fff" stroke-opacity="0.07"/>' for y in (40, 80, 120))}
      {candles}
      <path d="{d} L194,160 L10,160Z" fill="url(#area)" opacity="0"><animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;0.4;0.6;0.92;1" dur="4s" repeatCount="indefinite"/></path>
      <path d="{d}" fill="none" stroke="{a1}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="320" stroke-dashoffset="320">
        <animate attributeName="stroke-dashoffset" values="320;0;0;320" keyTimes="0;0.5;0.92;1" dur="4s" repeatCount="indefinite"/></path>
      <circle r="5" fill="#fff"><animateMotion dur="4s" keyPoints="0;1;1;0" keyTimes="0;0.5;0.92;1" calcMode="linear" repeatCount="indefinite" path="{d}"/></circle>'''
    if kind == "flow":
        nodes = [(20, 40, "interview"), (110, 22, "workflow"), (110, 110, "rank"), (186, 70, "impact")]
        edges = [(0, 1), (0, 2), (1, 3), (2, 3), (1, 2)]
        out = []
        for n, (i, j) in enumerate(edges):
            (x1, y1, _), (x2, y2, _) = nodes[i], nodes[j]
            path = f"M{x1},{y1} C{(x1 + x2) / 2},{y1} {(x1 + x2) / 2},{y2} {x2},{y2}"
            out.append(f'<path d="{path}" stroke="#fff" stroke-opacity="0.18" fill="none"/>')
            out.append(f'<circle r="3.5" fill="{a1}"><animateMotion dur="2.4s" begin="-{n * 0.45:.2f}s" repeatCount="indefinite" path="{path}"/></circle>')
        for k, (x, y, label) in enumerate(nodes):
            out.append(f'<circle cx="{x}" cy="{y}" r="11" fill="{BG_1}" stroke="{a1}" stroke-width="2">'
                       f'<animate attributeName="r" values="11;13;11" dur="2.4s" begin="{k * 0.6}s" repeatCount="indefinite"/></circle>')
            out.append(f'<text x="{x}" y="{y + 30}" text-anchor="middle" font-family="{MONO}" font-size="11" fill="#9ca3af">{label}</text>')
        return "\n".join(out)
    raise ValueError(kind)


STATUS = {
    "live": ("LIVE", "#4ade80"),
    "store": ("CHROME WEB STORE", "#f472b6"),
    "oss": ("OPEN SOURCE", "#a3e635"),
    "private": ("PRIVATE BUILD", "#9ca3af"),
}


def card(p):
    a1, a2 = p["accent"]
    label, color = STATUS[p["status"]]
    desc = "".join(f'<tspan x="36" dy="{0 if i == 0 else 25}">{escape(line)}</tspan>'
                   for i, line in enumerate(wrap(p["description"], 34)))
    tags, x = [], 36
    for tag in p["tags"]:
        w = len(tag) * 7.3 + 22
        tags.append(f'<rect x="{x}" y="258" width="{w:.0f}" height="26" rx="13" fill="#fff" fill-opacity="0.05" stroke="#fff" stroke-opacity="0.12"/>'
                    f'<text x="{x + w / 2:.0f}" y="275.5" text-anchor="middle" class="mono" font-size="12" fill="#cbd5e1">{escape(tag)}</text>')
        x += w + 8
    dot = (f'<circle cx="52" cy="49" r="4.5" fill="{color}"><animate attributeName="opacity" values="1;0.3;1" dur="1.8s" repeatCount="indefinite"/></circle>'
           if p["status"] == "live" else f'<circle cx="52" cy="49" r="4.5" fill="{color}"/>')
    arrow = "→" if p["url"] else "✉"
    return f'''
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="320" viewBox="0 0 600 320" role="img" aria-label="{escape(p["title"])}: {escape(p["description"])}">
  <title>{escape(p["title"])}</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG_0}"/><stop offset="1" stop-color="#121628"/></linearGradient>
    <linearGradient id="edge" x1="0" y1="0" x2="600" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{a1}" stop-opacity="0.9"/><stop offset="0.25" stop-color="#fff" stop-opacity="0.08"/>
      <stop offset="0.75" stop-color="#fff" stop-opacity="0.08"/><stop offset="1" stop-color="{a2}" stop-opacity="0.9"/>
      <animateTransform attributeName="gradientTransform" type="rotate" values="0 300 160;360 300 160" dur="8s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="title" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="{a1}"/></linearGradient>
    <radialGradient id="halo"><stop offset="0" stop-color="{a2}" stop-opacity="0.35"/><stop offset="1" stop-color="{a2}" stop-opacity="0"/></radialGradient>
    <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{a1}" stop-opacity="0"/><stop offset="1" stop-color="{a1}" stop-opacity="0.55"/></linearGradient>
    <linearGradient id="scan" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a1}" stop-opacity="0"/><stop offset="1" stop-color="{a1}" stop-opacity="0.45"/></linearGradient>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a1}" stop-opacity="0.35"/><stop offset="1" stop-color="{a1}" stop-opacity="0"/></linearGradient>
    <clipPath id="frame"><rect width="600" height="320" rx="22"/></clipPath>
  </defs>
  <style>
    .sans {{ font-family: {SANS}; }}
    .mono {{ font-family: {MONO}; }}
    .nudge {{ animation: nudge 1.8s ease-in-out infinite; }}
    @keyframes nudge {{ 0%,100% {{ transform: translateX(0); }} 50% {{ transform: translateX(4px); }} }}
  </style>
  <g clip-path="url(#frame)">
    <rect width="600" height="320" fill="url(#bg)"/>
    <circle cx="500" cy="120" r="200" fill="url(#halo)"><animate attributeName="r" values="180;220;180" dur="6s" repeatCount="indefinite"/></circle>
  </g>
  <rect x="1" y="1" width="598" height="318" rx="21" fill="none" stroke="url(#edge)" stroke-width="1.5"/>
  <rect x="36" y="34" width="{label.__len__() * 8.6 + 38:.0f}" height="30" rx="15" fill="{color}" fill-opacity="0.1" stroke="{color}" stroke-opacity="0.35"/>
  {dot}
  <text x="64" y="54" class="mono" font-size="12" letter-spacing="1.5" fill="{color}">{label}</text>
  <text x="36" y="118" class="sans" font-size="32" font-weight="800" letter-spacing="-1" fill="url(#title)">{escape(p["title"])}</text>
  <text x="36" y="156" class="sans" font-size="17" fill="#9ca3af">{desc}</text>
  {"".join(tags)}
  <g transform="translate(372 46)">{art(p["art"], a1, a2)}</g>
  <g class="nudge"><text x="564" y="276" text-anchor="end" class="mono" font-size="13" fill="{a1}">{escape(p["cta"])} {arrow}</text></g>
</svg>'''


# --------------------------------------------------------------------------- loop

def loop():
    steps = [("Signal", "spot the shift"), ("Bet", "frame the hypothesis"), ("Prototype", "ship it in days"), ("Learn", "measure, then decide")]
    xs, top, bot, r = [150, 450, 750, 1050], 150, 220, 35
    straight = xs[-1] - xs[0]
    total = 2 * straight + 2 * math.pi * r
    path = f"M{xs[0]},{top} H{xs[-1]} A{r},{r} 0 0 1 {xs[-1]},{bot} H{xs[0]} A{r},{r} 0 0 1 {xs[0]},{top}"
    dur = 9
    out = []
    for i, (name, caption) in enumerate(steps):
        t = (xs[i] - xs[0]) / total
        k0, k1, k2 = max(t - 0.01, 0), t, min(t + 0.12, 0.99)
        hl = f'keyTimes="0;{k0:.3f};{k1:.3f};{k2:.3f};1" dur="{dur}s" repeatCount="indefinite"'
        out.append(f'''
    <circle cx="{xs[i]}" cy="{top}" r="26" fill="url(#halo)" opacity="0"><animate attributeName="opacity" values="0;0;1;0;0" {hl}/></circle>
    <circle cx="{xs[i]}" cy="{top}" r="9" fill="{BG_1}" stroke="#a78bfa" stroke-width="2.5"/>
    <circle cx="{xs[i]}" cy="{top}" r="4" fill="#a78bfa"><animate attributeName="fill" values="#a78bfa;#a78bfa;#fff;#a78bfa;#a78bfa" {hl}/></circle>
    <text x="{xs[i]}" y="{top - 96}" text-anchor="middle" class="mono" font-size="12" letter-spacing="2" fill="#6b7280">0{i + 1}</text>
    <text x="{xs[i]}" y="{top - 68}" text-anchor="middle" class="sans" font-size="22" font-weight="700" fill="#f3f4f6">{name}
      <animate attributeName="fill" values="#f3f4f6;#f3f4f6;#67e8f9;#f3f4f6;#f3f4f6" {hl}/></text>
    <text x="{xs[i]}" y="{top - 42}" text-anchor="middle" class="sans" font-size="15" fill="#9ca3af">{caption}</text>''')
    return f'''
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="270" viewBox="0 0 1200 270" role="img" aria-label="How I work: {", ".join(s[0] for s in steps)}, repeat.">
  <title>Signal → Bet → Prototype → Learn</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG_0}"/><stop offset="1" stop-color="{BG_1}"/></linearGradient>
    <radialGradient id="halo"><stop offset="0" stop-color="#22d3ee" stop-opacity="0.6"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></radialGradient>
    <linearGradient id="trail" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#a78bfa"/><stop offset="1" stop-color="#22d3ee"/></linearGradient>
  </defs>
  <style>.sans {{ font-family: {SANS}; }} .mono {{ font-family: {MONO}; }}</style>
  <rect width="1200" height="270" rx="28" fill="url(#bg)"/>
  <rect x="0.5" y="0.5" width="1199" height="269" rx="28" fill="none" stroke="#fff" stroke-opacity="0.08"/>
  <path d="{path}" fill="none" stroke="#fff" stroke-opacity="0.1" stroke-width="2"/>
  <path d="{path}" fill="none" stroke="url(#trail)" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="140 {total - 140:.0f}">
    <animate attributeName="stroke-dashoffset" from="140" to="{140 - total:.0f}" dur="{dur}s" repeatCount="indefinite"/></path>
  <circle r="14" fill="url(#halo)"><animateMotion dur="{dur}s" repeatCount="indefinite" path="{path}"/></circle>
  <circle r="4.5" fill="#fff"><animateMotion dur="{dur}s" repeatCount="indefinite" path="{path}"/></circle>
  {"".join(out)}
  <rect x="540" y="{bot - 14}" width="120" height="28" rx="14" fill="{BG_1}" stroke="#fff" stroke-opacity="0.1"/>
  <text x="600" y="{bot + 5}" text-anchor="middle" class="mono" font-size="13" fill="#9ca3af">↺ repeat</text>
</svg>'''


# --------------------------------------------------------------------------- stats

def stats(data):
    tiles = [(data["repos"], "prototypes & repos"), (data["live"], "live deployments"),
             (data["languages"], "languages"), (data["since"], "building since")]
    out = []
    for i, (value, label) in enumerate(tiles):
        x = 30 + i * 288
        out.append(f'''
  <g>
    <rect x="{x}" y="30" width="276" height="110" rx="20" fill="#fff" fill-opacity="0.035" stroke="#fff" stroke-opacity="0.09"/>
    <text x="{x + 28}" y="90" class="sans" font-size="42" font-weight="800" letter-spacing="-1.5" fill="url(#ink)">{escape(str(value))}</text>
    <text x="{x + 28}" y="118" class="mono" font-size="13" letter-spacing="1" fill="#9ca3af">{escape(label.upper())}</text>
  </g>''')
    return f'''
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="170" viewBox="0 0 1200 170" role="img" aria-label="{data["repos"]} repos, {data["live"]} live deployments, {data["languages"]} languages, building since {data["since"]}">
  <defs>
    <linearGradient id="ink" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#a78bfa"/></linearGradient>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG_0}"/><stop offset="1" stop-color="{BG_1}"/></linearGradient>
  </defs>
  <style>
    .sans {{ font-family: {SANS}; }} .mono {{ font-family: {MONO}; }}
  </style>
  <rect width="1200" height="170" rx="28" fill="url(#bg)"/>
  <rect x="0.5" y="0.5" width="1199" height="169" rx="28" fill="none" stroke="#fff" stroke-opacity="0.08"/>
  {"".join(out)}
</svg>'''


# --------------------------------------------------------------------------- footer

def footer():
    waves = []
    for i, (color, amp, dur, op) in enumerate([("#a78bfa", 14, 7, 0.5), ("#22d3ee", 10, 9, 0.4), ("#f472b6", 8, 11, 0.3)]):
        def wave(phase):
            pts = " ".join(f"{x},{60 + amp * math.sin(x / 95 + phase + i):.1f}" for x in range(0, 1201, 20))
            return f"M{pts}"
        frames = ";".join(wave(p) for p in (0, math.pi, 2 * math.pi))
        waves.append(f'<path fill="none" stroke="{color}" stroke-opacity="{op}" stroke-width="2" d="{wave(0)}">'
                     f'<animate attributeName="d" values="{frames}" dur="{dur}s" repeatCount="indefinite"/></path>')
    return f'''
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="120" viewBox="0 0 1200 120" role="img" aria-label="Every repo here started as a question.">
  <style>.mono {{ font-family: {MONO}; }}</style>
  {"".join(waves)}
  <text x="600" y="110" text-anchor="middle" class="mono" font-size="14" fill="#8b949e">every repo here started as a question</text>
</svg>'''


# --------------------------------------------------------------------------- github data

def gh(path, token):
    req = urllib.request.Request(f"https://api.github.com{path}", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def fetch_repos(token, private):
    path = "/user/repos?affiliation=owner&per_page=100" if private else f"/users/{PROFILE['handle']}/repos?per_page=100"
    repos, page = [], 1
    while batch := gh(f"{path}&page={page}", token):
        repos += batch
        page += 1
    return [r for r in repos if not r["fork"]]


def stats_data(repos):
    first = min(datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) for r in repos)
    return {
        "repos": len(repos),
        "live": sum(1 for r in repos if r.get("homepage")),
        "languages": len({r["language"] for r in repos if r["language"]}),
        "since": first.strftime("%b %Y"),
    }


def recent_markdown(repos):
    lines = []
    for r in sorted(repos, key=lambda r: r["pushed_at"], reverse=True):
        if r["private"] or r["archived"] or r["name"] == PROFILE["handle"]:
            continue
        when = datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")).strftime("%d %b")
        parts = [f'`{when}` &nbsp; [**{r["name"]}**]({r["html_url"]})']
        desc = r["description"] or ""
        if desc and not desc.startswith("A repository for"):
            parts.append(desc)
        if r.get("homepage"):
            parts.append(f'[↗ demo]({r["homepage"]})')
        lines.append("- " + " · ".join(parts))
        if len(lines) == 5:
            break
    return "\n".join(lines)


def cards_markdown():
    cells = []
    for p in PROFILE["projects"]:
        img = f'<img src="assets/cards/{p["slug"]}.svg" width="49%" alt="{escape(p["title"])}: {escape(p["description"])}"/>'
        cells.append(f'<a href="{p["url"]}">{img}</a>' if p["url"] else img)
    return "\n".join("<p align=\"center\">\n" + "\n".join(cells[i:i + 2]) + "\n</p>" for i in range(0, len(cells), 2))


def replace_section(text, name, body):
    pattern = re.compile(rf"(<!-- {name}:start -->).*?(<!-- {name}:end -->)", re.S)
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


def main():
    write(ASSETS / "header.svg", header())
    write(ASSETS / "loop.svg", loop())
    write(ASSETS / "footer.svg", footer())
    for p in PROFILE["projects"]:
        write(ASSETS / "cards" / f"{p['slug']}.svg", card(p))

    readme_path = ROOT / "README.md"
    readme = replace_section(readme_path.read_text(), "cards", cards_markdown())

    profile_token, token = os.environ.get("PROFILE_TOKEN"), os.environ.get("GH_TOKEN")
    if profile_token or token:
        all_repos = fetch_repos(profile_token, private=True) if profile_token else None
        public = [r for r in (all_repos or fetch_repos(token, private=False)) if not r["private"]]
        readme = replace_section(readme, "recent", recent_markdown(public))
        if all_repos and not any(r["private"] for r in all_repos):
            print("PROFILE_TOKEN can't see private repos; keeping existing stats. "
                  "Give the token access to all repositories.")
        elif all_repos:
            write(ASSETS / "stats.svg", stats(stats_data(all_repos)))
            readme = re.sub(r"<!-- updated -->.*?<!-- /updated -->",
                            f"<!-- updated -->{datetime.now(timezone.utc):%d %b %Y}<!-- /updated -->", readme)
    readme_path.write_text(readme)


if __name__ == "__main__":
    main()
