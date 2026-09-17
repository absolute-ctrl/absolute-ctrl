"""Renders the whole GitHub profile as one continuous retro CRT screen, from profile.json."""
import json
import math
import os
import random
import time

from .art import ARTS, Ctx
from . import image as slot_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, CW, CH = 880, 400, 290
CARD_X = [30, 450]


def load_config(path=None):
    with open(path or os.path.join(ROOT, "profile.json"), encoding="utf-8") as fh:
        return json.load(fh)


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


DEFAULT_PALETTE = {"background": "#0A0F0A", "panel": "#070B07", "screen": "#050805", "primary": "#33FF66",
                   "accent": "#FFB000", "dim": "#1F7A3A", "shade": "#0F3D1C", "glow": "#143A1C"}


def palette(cfg):
    pals = cfg.get("palettes") or {}
    base = dict(DEFAULT_PALETTE)
    base.update(pals.get(cfg.get("theme"), {}))
    base.update(cfg.get("palette_overrides") or {})
    return base


def ago(seconds):
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s ago"
    if s < 86400:
        return f"{s // 3600}h {s % 3600 // 60:02d}m ago"
    return f"{s // 86400}d {s % 86400 // 3600:02d}h ago"


class Profile:
    def __init__(self, cfg, telemetry):
        self.cfg, self.tel, self.P = cfg, telemetry, palette(cfg)
        slots = cfg["programs"]["slots"]
        self.order = (["boot", "whoami", "specs", "mission", "programs"]
                      + [f"slot-{s['id']}" for s in slots] + ["telemetry", "footer"])
        base, rate, floor = 1.4, 0.78, 0.15
        self.times, t = {}, 0.0
        for i, n in enumerate(self.order):
            d = max(floor, base * rate ** i)
            self.times[n] = (t, d)
            t += d

    # ------------------------------------------------------------ helpers
    def after(self, step, t):
        s, d = self.times[step]
        return s + d + t

    def reveal(self, step, t):
        return f'<animate attributeName="opacity" from="0" to="1" begin="{self.after(step, t):.2f}s" dur="0.05s" fill="freeze"/>'

    def cursor(self, step, x, y, t=0):
        return (f'<rect x="{x}" y="{y - 14}" width="10" height="17" fill="{self.P["primary"]}" opacity="0">'
                f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" '
                f'begin="{self.after(step, t):.2f}s" repeatCount="indefinite"/></rect>')

    def power(self, step, x, y, w, h):
        s, d = self.times[step]
        P = self.P
        return f'''<rect x="{x}" y="{y - 1}" width="{w}" height="{h + 2}" fill="{P["background"]}">
<animate attributeName="opacity" from="1" to="0" begin="{s + d * .55:.2f}s" dur="{d * .45:.2f}s" fill="freeze"/></rect>
<rect x="{x}" y="{y + h / 2 - 1:.1f}" width="{w}" height="2" fill="{P["primary"]}" opacity="0">
<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.6;1" begin="{s:.2f}s" dur="{d * .75:.2f}s" fill="freeze"/>
<animate attributeName="x" from="{x + w / 2}" to="{x}" begin="{s:.2f}s" dur="{d * .45:.2f}s" fill="freeze"/>
<animate attributeName="width" from="0" to="{w}" begin="{s:.2f}s" dur="{d * .45:.2f}s" fill="freeze"/></rect>'''

    def header(self, title, y=34, right=""):
        P = self.P
        r = f'<text x="{W - 28}" y="{y}" text-anchor="end" fill="{P["dim"]}" font-size="14">{right}</text>' if right else ""
        return (f'<text x="28" y="{y}" fill="{P["accent"]}" font-size="15" font-weight="700">&gt; {esc(title)}</text>{r}'
                f'<line x1="28" y1="{y + 12}" x2="{W - 28}" y2="{y + 12}" stroke="{P["dim"]}" stroke-dasharray="4 4"/>')

    def status_style(self, status):
        st = self.cfg.get("statuses", {}).get(status)
        return st or {"color": "accent", "in_use": True, "blink": False}

    # ------------------------------------------------------------ sections
    def sec_boot(self):
        P, c = self.P, self.cfg["boot"]
        b, y, t = "", 78, 0.1
        for i, (left, right) in enumerate(c["lines"]):
            lc, rc = (P["accent"], P["dim"]) if i == 0 else (P["primary"], P["accent"])
            b += (f'<text x="40" y="{y}" fill="{lc}" font-size="16" opacity="0" xml:space="preserve">{esc(left)}'
                  f'<tspan fill="{rc}">{esc(right)}</tspan>{self.reveal("boot", t)}</text>')
            y += 26
            t += 0.16
        prompt = c.get("prompt", "")
        b += f'<text x="40" y="{y + 14}" fill="{P["primary"]}" font-size="16" opacity="0">{esc(prompt)}{self.reveal("boot", t)}</text>'
        b += self.cursor("boot", 40 + len(prompt) * 9.6 + 4, y + 14, t)
        name = c.get("name", [])
        nm = "".join(f'<text x="{W - 40}" y="{118 + i * 46}" text-anchor="end" fill="{P["accent"]}" font-size="44" '
                     f'font-weight="700" letter-spacing="2">{esc(n)}</text>' for i, n in enumerate(name))
        b += (f'<g opacity="0">{self.reveal("boot", t + .3)}{nm}'
              f'<text x="{W - 40}" y="{118 + len(name) * 46 - 14}" text-anchor="end" fill="{P["dim"]}" font-size="14">{esc(c.get("tagline", ""))}</text></g>')
        return max(290, y + 60), b

    def sec_whoami(self):
        P, c = self.P, self.cfg["whoami"]
        b = self.header(c.get("title", "WHOAMI"))
        b += f'<text x="28" y="80" fill="{P["dim"]}" font-size="15">C:\\&gt; <tspan fill="{P["primary"]}">{esc(c.get("command", "whoami"))}</tspan></text>'
        for i, line in enumerate(c["lines"]):
            size = min(16.0, (W - 56) / (max(1, len(line)) * 0.6))
            b += f'<text x="28" y="{112 + i * 26}" fill="{P["accent"] if i == 0 else P["primary"]}" font-size="{size:.1f}" xml:space="preserve">{esc(line)}</text>'
        return 140 + len(c["lines"]) * 26 - 24, b

    def sec_specs(self):
        P, c = self.P, self.cfg["specs"]
        rows = c["rows"]
        cols = [28, 210, 520]
        b = self.header(c.get("title", "SYSTEM SPECS"))
        for x, h in zip(cols, c["columns"]):
            b += f'<text x="{x + 14}" y="84" fill="{P["accent"]}" font-size="14" font-weight="700">{esc(h)}</text>'
        bottom = 96 + len(rows) * 38
        b += (f'<rect x="28" y="62" width="{W - 56}" height="{bottom - 62}" fill="none" stroke="{P["dim"]}"/>'
              f'<line x1="28" y1="96" x2="{W - 28}" y2="96" stroke="{P["dim"]}"/>')
        for x in cols[1:]:
            b += f'<line x1="{x}" y1="62" x2="{x}" y2="{bottom}" stroke="{P["dim"]}"/>'
        for i, r in enumerate(rows):
            if i:
                b += f'<line x1="28" y1="{96 + i * 38}" x2="{W - 28}" y2="{96 + i * 38}" stroke="{P["dim"]}" opacity=".35"/>'
            for x, v in zip(cols, (list(r) + ["", "", ""])[:3]):
                if str(v).strip():
                    b += f'<text x="{x + 14}" y="{124 + i * 38}" fill="{P["primary"]}" font-size="16">{esc(v)}</text>'
                else:
                    b += f'<text x="{x + 14}" y="{124 + i * 38}" fill="{P["dim"]}" font-size="14" opacity=".8">{esc(c.get("placeholder", "--"))}</text>'
        return bottom + 30, b

    def sec_mission(self):
        P, c = self.P, self.cfg["mission"]
        b = self.header(c.get("title", "CURRENT MISSION"))
        for i, it in enumerate(c["items"]):
            y = 90 + i * 40
            n = max(0, min(10, int(it.get("level", 0))))
            b += f'<text x="28" y="{y}" fill="{P["accent"]}" font-size="15" font-weight="700">{esc(it["label"])}</text>'
            for j in range(10):
                x = 190 + j * 20
                if j < n:
                    b += (f'<rect x="{x}" y="{y - 14}" width="14" height="16" fill="{P["primary"]}" stroke="{P["dim"]}" opacity="0">'
                          f'{self.reveal("mission", i * .25 + j * .05)}</rect>')
                else:
                    b += f'<rect x="{x}" y="{y - 14}" width="14" height="16" fill="none" stroke="{P["dim"]}"/>'
            b += f'<text x="410" y="{y}" fill="{P["primary"]}" font-size="16">{esc(it["text"])}</text>'
        ny = 90 + len(c["items"]) * 40
        b += f'<text x="28" y="{ny}" fill="{P["dim"]}" font-size="13">{esc(c.get("note", ""))}</text>'
        return ny + 20, b

    def card(self, slot):
        P = self.P
        sid = slot["id"]
        st = self.status_style(slot.get("status", ""))
        col = P.get(st.get("color", "accent"), P["accent"])
        empty = not st.get("in_use", True)
        blink = ('<animate attributeName="opacity" values="1;1;.25;.25" keyTimes="0;.5;.5;1" dur="1.4s" repeatCount="indefinite"/>'
                 if st.get("blink") else "")
        art_name = slot.get("art", "idle")
        art_fn = ARTS.get(art_name, ARTS["idle"])
        opts = dict(self.cfg.get("art", {}).get(art_name, {}))
        img_cfg = slot.get("image") or {}
        try:
            img = slot_image.layer(sid, img_cfg, P, ROOT)
        except (OSError, ValueError) as err:
            img = f'<text x="34" y="62" fill="{P["accent"]}" font-size="10">image error: {esc(err)}</text>'
        if img:
            opts["label_position"] = img_cfg.get("label_position", "bottom")
            opts["noise"] = img_cfg.get("noise", 0.5)
            if "label" in img_cfg:
                opts["label"] = img_cfg["label"]
        art = img + art_fn(Ctx(sid, P, opts, esc))
        text_col = P["dim"] if empty else P["primary"]
        sub_col = P["dim"] if empty else P["accent"]
        return f'''<path d="M10 0 H{CW - 60} L{CW - 10} 40 V{CH - 10} Q{CW - 10} {CH} {CW - 20} {CH} H20 Q10 {CH} 10 {CH - 10} Z" fill="{P["panel"]}" stroke="{col}" stroke-width="3"/>
<text x="24" y="30" fill="{col}" font-size="15" font-weight="700">SLOT {esc(sid)}:</text>
<text x="{CW - 80}" y="30" text-anchor="end" fill="{col}" font-size="12">[{esc(slot.get("status", ""))}]{blink}</text>
<rect x="22" y="44" width="{CW - 44}" height="148" rx="6" fill="{P["screen"]}" stroke="{P["dim"]}"/>
<g clip-path="url(#scr-{esc(sid)})">{art}</g>
<text x="24" y="222" fill="{text_col}" font-size="15" font-weight="700">{esc(slot.get("title", ""))}</text>
<text x="24" y="248" fill="{sub_col}" font-size="13">{esc(slot.get("stack", ""))}</text>
<rect x="24" y="266" width="{CW - 48}" height="2" fill="{P["dim"]}" opacity=".6"/>'''

    def sec_telemetry(self):
        P, c, tel = self.P, self.cfg.get("telemetry", {}), self.tel or {}
        gh = tel.get("github")
        live = tel.get("mode") == "live"
        stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(tel.get("now", time.time())))
        right = f'{"LINK LIVE" if live else "SNAPSHOT"}  {stamp}'
        b = self.header(c.get("title", "TELEMETRY"), right=right)
        if live:
            b += (f'<rect x="{W - 28 - len(right) * 8.4 - 14}" y="24" width="8" height="10" fill="{P["accent"]}">'
                  f'<animate attributeName="opacity" values="1;1;.15;.15" keyTimes="0;.5;.5;1" dur="1s" repeatCount="indefinite"/></rect>')

        labels = c.get("labels", {})
        values = {
            "accesses": f"{tel['accesses']:,}" if tel.get("accesses") is not None else ("--" if live else "live only"),
            "previous_access": (ago(tel["now"] - tel["previous_access"]) if tel.get("previous_access")
                                else ("first contact" if live and tel.get("accesses") else ("--" if live else "live only"))),
        }
        if gh:
            values.update({k: f"{gh[k]:,}" for k in ("repos", "stars", "commits", "prs", "followers")})
        fields = c.get("fields", ["accesses", "previous_access", "repos", "stars", "commits", "prs", "followers"])
        y = 84
        for key in fields:
            if key not in values:
                if gh is None and key in ("repos", "stars", "commits", "prs", "followers"):
                    values[key] = "no link"
                else:
                    continue
            label = labels.get(key, key)
            dots = "." * max(3, 24 - len(label))
            b += (f'<text x="28" y="{y}" fill="{P["primary"]}" font-size="15" xml:space="preserve">{esc(label)} {dots} '
                  f'<tspan fill="{P["accent"]}">{esc(values[key])}</tspan></text>')
            y += 28
        left_bottom = y

        b += f'<text x="470" y="84" fill="{P["accent"]}" font-size="14" font-weight="700">{esc(c.get("languages_title", "LANGUAGE MIX"))}</text>'
        langs = (gh or {}).get("languages") or {}
        ry = 114
        if langs:
            total = sum(langs.values()) or 1
            for name, size in sorted(langs.items(), key=lambda kv: -kv[1])[: int(c.get("languages_shown", 5))]:
                pct = size / total
                blocks = max(1, round(pct * 20))
                b += f'<text x="470" y="{ry}" fill="{P["primary"]}" font-size="14">{esc(name[:12])}</text>'
                for j in range(20):
                    fill = P["primary"] if j < blocks else "none"
                    b += f'<rect x="{590 + j * 11}" y="{ry - 12}" width="8" height="14" fill="{fill}" stroke="{P["dim"]}"/>'
                b += f'<text x="{W - 28}" y="{ry}" text-anchor="end" fill="{P["accent"]}" font-size="13">{pct * 100:.1f}%</text>'
                ry += 28
        else:
            b += f'<text x="470" y="114" fill="{P["dim"]}" font-size="13">// awaiting GitHub token</text>'
            ry += 28
        return max(left_bottom, ry) + 14, b

    def sec_footer(self):
        P = self.P
        lines = self.cfg.get("footer", {}).get("lines", ["READY."])
        b = ""
        for i, line in enumerate(lines):
            size, col = (18, P["primary"]) if i == 0 else (16, P["accent"])
            b += f'<text x="28" y="{44 + i * 30}" fill="{col}" font-size="{size}">{esc(line)}</text>'
        last = lines[-1] if lines else ""
        b += self.cursor("footer", 28 + len(last) * 9.6 + 10, 44 + (len(lines) - 1) * 30)
        return 40 + len(lines) * 30, b

    # ------------------------------------------------------------ compose
    def build(self):
        P, cfg = self.P, self.cfg
        body, overlays, clips, y = "", "", "", 0

        def divider(yy):
            return (f'<line x1="14" y1="{yy - 2}" x2="{W - 14}" y2="{yy - 2}" stroke="{P["dim"]}" opacity=".5"/>'
                    f'<line x1="14" y1="{yy + 2}" x2="{W - 14}" y2="{yy + 2}" stroke="{P["dim"]}" opacity=".5"/>')

        for step, fn in [("boot", self.sec_boot), ("whoami", self.sec_whoami),
                         ("specs", self.sec_specs), ("mission", self.sec_mission)]:
            h, b = fn()
            body += f'<g transform="translate(0,{y})">{b}</g>' + divider(y + h)
            overlays += self.power(step, 0, y, W, h)
            y += h

        slots = cfg["programs"]["slots"]
        used = sum(1 for s in slots if self.status_style(s.get("status", "")).get("in_use", True))
        h = 56
        body += f'<g transform="translate(0,{y})">{self.header(cfg["programs"].get("title", "LOADED PROGRAMS"), right=f"{len(slots)} slots, {used} in use")}</g>'
        overlays += self.power("programs", 0, y, W, h)
        y += h

        n_rows = math.ceil(len(slots) / 2)
        for i, slot in enumerate(slots):
            row, col = divmod(i, 2)
            cy, cx = y + row * (CH + 20), CARD_X[col]
            clips += f'<clipPath id="scr-{esc(slot["id"])}"><rect x="22" y="44" width="{CW - 44}" height="148" rx="6"/></clipPath>'
            body += f'<g transform="translate({cx},{cy})">{self.card(slot)}</g>'
            top = cy - 4
            bot = y + n_rows * (CH + 20) + 10 if row == n_rows - 1 else top + CH + 20
            overlays += self.power(f"slot-{slot['id']}", col * (W // 2), top, W // 2, bot - top)
        y += n_rows * (CH + 20) + 10
        body += divider(y)

        for step, fn in [("telemetry", self.sec_telemetry), ("footer", self.sec_footer)]:
            h, b = fn()
            body += f'<g transform="translate(0,{y})">{b}</g>'
            if step == "telemetry":
                body += divider(y + h)
            overlays += self.power(step, 0, y, W, h)
            y += h

        H = y + 10
        clips += slot_image.shared_defs(ROOT)
        return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{esc(cfg.get("font", "monospace"))}">
<defs>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="2" fill="#000" opacity=".28"/></pattern>
<radialGradient id="glow" cx="50%" cy="20%" r="90%"><stop offset="0" stop-color="{P["glow"]}" stop-opacity=".5"/><stop offset="1" stop-color="{P["background"]}" stop-opacity="0"/></radialGradient>
<filter id="ph"><feGaussianBlur stdDeviation=".6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="screen"><rect width="{W}" height="{H}" rx="16"/></clipPath>
{clips}
</defs>
<title>{esc(cfg.get("title", cfg["user"]))}</title>
<g clip-path="url(#screen)">
<rect width="{W}" height="{H}" fill="{P["background"]}"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>
<g filter="url(#ph)">{body}</g>
<rect width="{W}" height="{H}" fill="url(#scan)"/>
{overlays}
</g>
<rect x="1.5" y="1.5" width="{W - 3}" height="{H - 3}" rx="15" fill="none" stroke="{P["dim"]}" stroke-width="3"/>
</svg>'''


def render(cfg, telemetry):
    random.seed(7)
    slot_image.reset()
    return Profile(cfg, telemetry).build()
