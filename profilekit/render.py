"""Renders the whole GitHub profile as one continuous retro CRT screen, from profile.json.

The screen is printed, not faded in. Every section asks the shared Timeline (profilekit/anim.py)
for the current time, snaps itself into view at that time, then advances the clock: a line of text
appears whole and instantly, a bar or a meter fills block by block, a command line is typed out
character by character. Because the clock only moves forward, nothing ever overlaps anything else.

Layout, colours, sizes, effects, timings and every string come from profile.json.
"""
import json
import math
import os
import random
import time

from .anim import Timeline
from .art import ARTS, Ctx
from . import image as slot_image
from . import mosaic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CW, CH = 400, 290  # card size; the art in art.py is drawn for exactly this box

LAYOUT = {"width": 880, "margin": 28, "card_columns": 2, "card_gap": 20, "card_row_gap": 20,
          "corner_radius": 16, "border": True, "section_gap": 0}
EFFECTS = {"scanlines": True, "scanline_opacity": 0.28, "scanline_spacing": 4,
           "glow": True, "blur": 0.6, "flicker": 0.0, "dividers": True}
SIZES = {"header": 15, "body": 15, "small": 13, "boot": 16, "boot_name": 44, "tagline": 14,
         "table": 16, "table_header": 14, "meter": 16, "card_title": 15, "card_stack": 13,
         "card_slot": 15, "card_status": 12, "telemetry": 15, "footer": 18, "logo_name": 42,
         "note": 13}

DEFAULT_PALETTE = {"background": "#0A0F0A", "panel": "#070B07", "screen": "#050805", "primary": "#33FF66",
                   "accent": "#FFB000", "dim": "#1F7A3A", "shade": "#0F3D1C", "glow": "#143A1C"}


def load_config(path=None):
    with open(path or os.path.join(ROOT, "profile.json"), encoding="utf-8") as fh:
        return json.load(fh)


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def palette(cfg):
    pals = cfg.get("palettes") or {}
    base = dict(DEFAULT_PALETTE)
    base.update(pals.get(cfg.get("theme"), {}))
    base.update(cfg.get("palette_overrides") or {})
    return base


def merged(defaults, over):
    out = dict(defaults)
    out.update({k: v for k, v in (over or {}).items() if v is not None})
    return out


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
        self.tl = Timeline(cfg)
        self.L = merged(LAYOUT, cfg.get("layout"))
        self.FX = merged(EFFECTS, cfg.get("effects"))
        self.S = merged(SIZES, cfg.get("sizes"))
        self.W = int(self.L["width"])
        self.M = int(self.L["margin"])
        self.cols = max(1, int(self.L["card_columns"]))
        gap = int(self.L["card_gap"])
        span = self.cols * CW + (self.cols - 1) * gap
        left = max(10, (self.W - span) / 2)
        self.card_x = [left + i * (CW + gap) for i in range(self.cols)]

    # ------------------------------------------------------------ small helpers
    def adv(self, size):
        """Character advance of the monospace font at `size`."""
        return float(size) * 0.6

    def text(self, x, y, s, fill=None, size=None, weight=None, anchor=None, extra=""):
        size = self.S["body"] if size is None else size
        out = f'<text x="{float(x):.1f}" y="{float(y):.1f}" fill="{fill or self.P["primary"]}" font-size="{size}"'
        if weight:
            out += f' font-weight="{weight}"'
        if anchor:
            out += f' text-anchor="{anchor}"'
        return f'{out} xml:space="preserve"{extra}>{esc(s)}</text>'

    def header(self, title, y=34, right=""):
        P, W, M = self.P, self.W, self.M
        r = self.text(W - M, y, right, P["dim"], self.S["small"], anchor="end") if right else ""
        return (self.text(M, y, f"> {title}", P["accent"], self.S["header"], weight="700") + r +
                f'<line x1="{M}" y1="{y + 12}" x2="{W - M}" y2="{y + 12}" stroke="{P["dim"]}" stroke-dasharray="4 4"/>')

    def divider(self, y):
        P = self.P
        return (f'<line x1="14" y1="{y - 2}" x2="{self.W - 14}" y2="{y - 2}" stroke="{P["dim"]}" opacity=".5"/>'
                f'<line x1="14" y1="{y + 2}" x2="{self.W - 14}" y2="{y + 2}" stroke="{P["dim"]}" opacity=".5"/>')

    def timed(self, svg, begin, end=None):
        """Visible from `begin`, and hidden again at `end` if given."""
        tl = self.tl
        if not tl.on:
            return svg if end is None else ""
        off = f'<set attributeName="opacity" to="0" begin="{tl.fmt(end)}" fill="freeze"/>' if end is not None else ""
        return (f'<g opacity="0"><set attributeName="opacity" to="1" begin="{tl.fmt(begin)}" fill="freeze"/>'
                f'{off}{svg}</g>')

    def blink_cursor(self, x, y, size=None, begin=None, fill=None):
        """A cursor that starts blinking at `begin` and keeps blinking."""
        size = self.S["body"] if size is None else size
        tl = self.tl
        t = tl.now() if begin is None else begin
        blink = tl.d(tl.cfg["typing"]["blink_seconds"])
        return (f'<rect x="{float(x):.1f}" y="{y - size + 2:.1f}" width="{self.adv(size):.1f}" '
                f'height="{size + 2:.1f}" fill="{fill or self.P["primary"]}" opacity="0">'
                f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="{blink:.2f}s" '
                f'begin="{tl.fmt(t)}" repeatCount="indefinite"/></rect>')

    def typed(self, x, y, body, prompt="", size=None, fill=None, prompt_fill=None, cursor=False, hold=None):
        """A line the *user* types: the prompt appears whole, the command arrives character by
        character. This is the one thing that is deliberately slow-typed."""
        tl, P = self.tl, self.P
        size = self.S["body"] if size is None else size
        fill, prompt_fill = fill or P["primary"], prompt_fill or P["dim"]
        adv = self.adv(size)
        px = x + len(prompt) * adv
        typing, n = tl.cfg["typing"], len(body)
        head = self.text(x, y, prompt, prompt_fill, size) if prompt else ""

        if not tl.on or not typing["enabled"] or not n:
            svg = head + self.text(px, y, body, fill, size)
            if cursor and typing["cursor"]:
                svg += self.blink_cursor(px + n * adv + 2, y, size)
            return tl.show(svg, hold=hold)

        begin = tl.now()
        cps = max(1.0, float(typing["chars_per_second"]))
        dur = tl.d(n / cps)
        cid = tl.uid("type")
        keys = ";".join(f"{i / (n + 1):.4f}" for i in range(n + 1))
        widths = ";".join(f"{i * adv:.1f}" for i in range(n + 1))
        out = self.timed(head, begin) if head else ""
        out += (f'<clipPath id="{cid}"><rect x="{px:.1f}" y="{y - size - 2:.1f}" width="0" height="{size * 1.6:.1f}">'
                f'<animate attributeName="width" calcMode="discrete" begin="{tl.fmt(begin)}" dur="{dur:.2f}s" '
                f'keyTimes="{keys}" values="{widths}" fill="freeze"/></rect></clipPath>'
                f'<g clip-path="url(#{cid})">{self.text(px, y, body, fill, size)}</g>')
        if typing["cursor"]:
            xs = ";".join(f"{px + i * adv + 2:.1f}" for i in range(n + 1))
            blink = tl.d(typing["blink_seconds"])
            stop = ("" if cursor else
                    f'<set attributeName="opacity" to="0" begin="{tl.fmt(begin + dur + tl.d(0.25))}" fill="freeze"/>')
            out += (f'<rect x="{px + 2:.1f}" y="{y - size + 2:.1f}" width="{adv:.1f}" height="{size + 2:.1f}" '
                    f'fill="{P["primary"]}" opacity="0">'
                    f'<animate attributeName="x" calcMode="discrete" begin="{tl.fmt(begin)}" dur="{dur:.2f}s" '
                    f'keyTimes="{keys}" values="{xs}" fill="freeze"/>'
                    f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="{blink:.2f}s" '
                    f'begin="{tl.fmt(begin)}" repeatCount="indefinite"/>{stop}</rect>')
        tl.wait(n / cps)
        tl.wait(tl.cfg["line_seconds"] if hold is None else hold)
        return out

    def block_bar(self, x, y, w, h, seconds=None, blocks=24, color=None, frame=True, lead="",
                  percent=False, percent_x=None, percent_size=None, hide_after=None):
        """A bar that fills one block at a time, terminal style. Charges its fill to the clock.
        `hide_after` (seconds) makes the whole thing disappear once it is full."""
        tl, P = self.tl, self.P
        col = color or P["accent"]
        seconds = tl.cfg["bar_seconds"] if seconds is None else seconds
        begin, dur = tl.now(), tl.d(seconds)
        off = None if hide_after is None else begin + dur + tl.d(hide_after)
        n = max(1, int(blocks))
        pad = 2
        bw = (w - pad * (n + 1)) / n
        out = self.timed(lead, begin, off) if lead else ""
        if frame:
            out += self.timed(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" fill="none" '
                              f'stroke="{P["dim"]}"/>', begin, off)
        for i in range(n):
            block = (f'<rect x="{x + pad + i * (bw + pad):.1f}" y="{y + pad:.1f}" width="{bw:.1f}" '
                     f'height="{h - 2 * pad}" fill="{col}"/>')
            out += self.timed(block, begin + dur * (i / n), off)
        if percent:
            size = percent_size or self.S["small"]
            px = x + w + 12 if percent_x is None else percent_x
            for i in range(n):
                t0, t1 = begin + dur * (i / n), begin + dur * ((i + 1) / n)
                label = f"{round((i + 1) * 100 / n):>3d}%"
                out += self.timed(self.text(px, y + h - 1, label, col, size), t0,
                                  (t1 if i < n - 1 else off))
        tl.wait(seconds)
        return out

    def status_style(self, status):
        st = self.cfg.get("statuses", {}).get(status)
        return st or {"color": "accent", "in_use": True, "blink": False}

    # ------------------------------------------------------------ sections
    def sec_logo(self):
        """Manufacturer splash: the helmet printed row by row, then the brand, then a fill bar."""
        P, tl, W = self.P, self.tl, self.W
        c = self.cfg.get("logo") or {}
        art = c.get("art") or {}
        lg = tl.cfg["logo"]
        b, y = "", 38

        top_l, top_r = c.get("top_left", ""), c.get("top_right", "")
        if top_l or top_r:
            row = (self.text(self.M, y, top_l, P["dim"], self.S["small"]) +
                   self.text(W - self.M, y, top_r, P["dim"], self.S["small"], anchor="end"))
            b += tl.show(row, kind="chunk")
            y += 20

        mode = art.get("mode", "ascii")
        if mode == "image" and art.get("src"):
            iw, ih = float(art.get("width", 360)), float(art.get("height", 300))
            try:
                b += tl.show(slot_image.layer("logo", art, P, ROOT, box=((W - iw) / 2, y, iw, ih)),
                             kind="chunk")
            except (OSError, ValueError) as err:
                b += tl.show(self.text(self.M, y + 20, f"logo image error: {err}", P["accent"], self.S["small"]))
                ih = 30
            y += ih + 14
        elif mode != "none":
            try:
                grid, cols, rows_n, mc = mosaic.cells(art, ROOT)
                cw, rh = float(mc["cell_width"]), float(mc["row_height"])
                size = cw / 0.6 * float(mc["font_scale"])
                x0 = (W - cols * cw) / 2
                for r, row in enumerate(grid):
                    # every glyph gets its own x, so the grid stays square whatever font the
                    # browser actually falls back to
                    spans = "".join(
                        f'<tspan x="{" ".join(f"{x0 + (col + k) * cw:.1f}" for k in range(len(txt)))}" '
                        f'fill="{P.get(key, P["primary"])}">{esc(txt)}</tspan>'
                        for col, txt, key in mosaic.runs(row))
                    if spans:
                        b += tl.show(f'<text y="{y + r * rh:.1f}" font-size="{size:.2f}" '
                                     f'xml:space="preserve">{spans}</text>', hold=lg["row_seconds"])
                    else:
                        tl.wait(lg["row_seconds"])
                y += rows_n * rh + 16
            except (OSError, ValueError, KeyError) as err:
                b += tl.show(self.text(self.M, y + 16, f"logo art unavailable: {err}", P["dim"], self.S["small"]))
                y += 34

        if c.get("name"):
            b += tl.show(self.text(W / 2, y + self.S["logo_name"] * 0.8, c["name"], P["accent"],
                                   self.S["logo_name"], weight="700", anchor="middle",
                                   extra=f' letter-spacing="{c.get("name_spacing", 6)}"'), kind="chunk")
            y += self.S["logo_name"] + 10
        if c.get("tagline"):
            b += tl.show(self.text(W / 2, y + 14, c["tagline"], P["dim"], self.S["tagline"], anchor="middle"),
                         kind="chunk")
            y += 28

        if c.get("bar", True):
            bw = float(c.get("bar_width", 340))
            b += tl.show(self.text((W - bw) / 2, y + 12, c.get("bar_label", "INITIALIZING"),
                                   P["primary"], self.S["small"]), hold=0.05)
            y += 20
            b += self.block_bar((W - bw) / 2, y, bw, 14, seconds=lg["bar_seconds"],
                                blocks=int(c.get("bar_blocks", 28)), percent=True)
            y += 26

        for line in c.get("lines", []):
            b += tl.show(self.text(W / 2, y + 14, line, P["dim"], self.S["small"], anchor="middle"))
            y += 22
        tl.wait(lg["hold_seconds"])

        if c.get("frame", True):
            b = (f'<rect x="{self.M - 12}" y="16" width="{W - 2 * (self.M - 12)}" height="{y + 6}" rx="10" '
                 f'fill="none" stroke="{P["dim"]}" opacity=".45"/>') + b
        return y + 34, b

    def sec_boot(self):
        P, tl, c = self.P, self.tl, self.cfg["boot"]
        size = self.S["boot"]
        adv = self.adv(size)
        bar_w = float(c.get("bar_width", 150))
        b, y = "", 78
        for i, item in enumerate(c["lines"]):
            if isinstance(item, dict):
                left, right = item.get("left", ""), item.get("right", "")
                bar, pause = bool(item.get("bar", False)), item.get("pause")
            else:
                left, right = (list(item) + ["", ""])[:2]
                bar, pause = False, None
            lc, rc = (P["accent"], P["dim"]) if i == 0 else (P["primary"], P["accent"])
            b += tl.show(self.text(40, y, left, lc, size),
                         hold=tl.cfg["pause_seconds"] if pause is None else pause)
            rx = 40 + len(left) * adv
            if bar:
                b += self.block_bar(rx, y - size + 3, bar_w, size, seconds=float(c.get("bar_seconds", 0.5)),
                                    blocks=int(c.get("bar_blocks", 12)), color=P["dim"], frame=False)
                rx += bar_w + 10
            if right:
                b += tl.show(self.text(rx, y, right, rc, size))
            y += 26

        prompt = c.get("prompt", "")
        if prompt:
            head, sep, cmd = prompt.partition(">")
            b += self.typed(40, y + 14, cmd.strip() if sep else prompt,
                            prompt=(head + "> " if sep else ""), size=size, cursor=True)
            y += 26

        name = c.get("name", [])
        if name:
            nm = "".join(self.text(self.W - 40, 118 + i * 46, n, P["accent"], self.S["boot_name"],
                                   weight="700", anchor="end", extra=' letter-spacing="2"')
                         for i, n in enumerate(name))
            nm += self.text(self.W - 40, 118 + len(name) * 46 - 14, c.get("tagline", ""), P["dim"],
                            self.S["tagline"], anchor="end")
            b += tl.show(nm, kind="chunk")
        return max(290, y + 46), b

    def sec_whoami(self):
        P, tl, c = self.P, self.tl, self.cfg["whoami"]
        b = tl.show(self.header(c.get("title", "WHOAMI")), kind="chunk")
        b += self.typed(self.M, 80, c.get("command", "whoami"), prompt=c.get("prompt", "C:\\> "),
                        size=self.S["header"], cursor=False)
        for i, line in enumerate(c["lines"]):
            size = min(float(self.S["body"]) + 1, (self.W - 2 * self.M) / (max(1, len(line)) * 0.6))
            b += tl.show(self.text(self.M, 112 + i * 26, line,
                                   P["accent"] if i == 0 else P["primary"], f"{size:.1f}"))
        return 140 + len(c["lines"]) * 26 - 24, b

    def sec_specs(self):
        P, tl, c = self.P, self.tl, self.cfg["specs"]
        W, M = self.W, self.M
        rows = c["rows"]
        cols = c.get("column_x") or [M, 210, 520]
        b = tl.show(self.header(c.get("title", "SYSTEM SPECS")), kind="chunk")
        bottom = 96 + len(rows) * 38
        frame = (f'<rect x="{M}" y="62" width="{W - 2 * M}" height="{bottom - 62}" fill="none" stroke="{P["dim"]}"/>'
                 f'<line x1="{M}" y1="96" x2="{W - M}" y2="96" stroke="{P["dim"]}"/>')
        for x in cols[1:]:
            frame += f'<line x1="{x}" y1="62" x2="{x}" y2="{bottom}" stroke="{P["dim"]}"/>'
        frame += "".join(self.text(x + 14, 84, h, P["accent"], self.S["table_header"], weight="700")
                         for x, h in zip(cols, c["columns"]))
        b += tl.show(frame, kind="chunk")
        for i, r in enumerate(rows):
            row = (f'<line x1="{M}" y1="{96 + i * 38}" x2="{W - M}" y2="{96 + i * 38}" stroke="{P["dim"]}" '
                   f'opacity=".35"/>' if i else "")
            for x, v in zip(cols, (list(r) + ["", "", ""])[:3]):
                if str(v).strip():
                    row += self.text(x + 14, 124 + i * 38, v, P["primary"], self.S["table"])
                else:
                    row += self.text(x + 14, 124 + i * 38, c.get("placeholder", "--"), P["dim"],
                                     self.S["table_header"], extra=' opacity=".8"')
            b += tl.show(row)
        return bottom + 30, b

    def sec_mission(self):
        P, tl, c = self.P, self.tl, self.cfg["mission"]
        b = tl.show(self.header(c.get("title", "CURRENT MISSION")), kind="chunk")
        slots = int(c.get("meter_slots", 10))
        mx, tx = float(c.get("meter_x", 190)), float(c.get("text_x", 410))
        for i, it in enumerate(c["items"]):
            y = 90 + i * 40
            n = max(0, min(slots, int(it.get("level", 0))))
            row = self.text(self.M, y, it["label"], P["accent"], self.S["header"], weight="700")
            row += self.text(tx, y, it["text"], P["primary"], self.S["meter"])
            row += "".join(f'<rect x="{mx + j * 20:.0f}" y="{y - 14}" width="14" height="16" fill="none" '
                           f'stroke="{P["dim"]}"/>' for j in range(slots))
            b += tl.show(row, hold=tl.cfg["pause_seconds"])
            for j in range(n):  # the meter fills one block at a time
                b += tl.show(f'<rect x="{mx + j * 20:.0f}" y="{y - 14}" width="14" height="16" '
                             f'fill="{P["primary"]}" stroke="{P["dim"]}"/>', kind="block")
            tl.wait(tl.cfg["line_seconds"])
        ny = 90 + len(c["items"]) * 40
        b += tl.show(self.text(self.M, ny, c.get("note", ""), P["dim"], self.S["note"]))
        return ny + 20, b

    def card(self, slot):
        """One program cartridge, assembled in order: shell, screen, load bar, art, labels."""
        P, tl = self.P, self.tl
        sid = slot["id"]
        st = self.status_style(slot.get("status", ""))
        col = P.get(st.get("color", "accent"), P["accent"])
        empty = not st.get("in_use", True)
        blink = ('<animate attributeName="opacity" values="1;1;.25;.25" keyTimes="0;.5;.5;1" dur="1.4s" '
                 'repeatCount="indefinite"/>') if st.get("blink") else ""

        shell = (f'<path d="M10 0 H{CW - 60} L{CW - 10} 40 V{CH - 10} Q{CW - 10} {CH} {CW - 20} {CH} H20 '
                 f'Q10 {CH} 10 {CH - 10} Z" fill="{P["panel"]}" stroke="{col}" stroke-width="3"/>'
                 f'{self.text(24, 30, f"SLOT {sid}:", col, self.S["card_slot"], weight="700")}'
                 f'<text x="{CW - 80}" y="30" text-anchor="end" fill="{col}" font-size="{self.S["card_status"]}">'
                 f'[{esc(slot.get("status", ""))}]{blink}</text>'
                 f'<rect x="22" y="44" width="{CW - 44}" height="148" rx="6" fill="{P["screen"]}" '
                 f'stroke="{P["dim"]}"/>')
        out = tl.show(shell, kind="card")

        load = float(tl.cfg["card_load_seconds"])
        if tl.on and load > 0:
            lead = self.text(60, 106, slot.get("loading", self.cfg["programs"].get("loading", "LOADING")),
                             P["dim"], self.S["small"])
            out += self.block_bar(60, 118, CW - 120, 12, seconds=load, blocks=14, color=P["dim"],
                                  lead=lead, hide_after=0.0)

        art_name = slot.get("art", "idle")
        art_fn = ARTS.get(art_name, ARTS["idle"])
        opts = dict(self.cfg.get("art", {}).get(art_name, {}))
        img_cfg = slot.get("image") or {}
        try:
            img = slot_image.layer(sid, img_cfg, P, ROOT)
        except (OSError, ValueError) as err:
            img = self.text(34, 62, f"image error: {err}", P["accent"], 10)
        if img:
            opts["label_position"] = img_cfg.get("label_position", "bottom")
            opts["noise"] = img_cfg.get("noise", 0.5)
            if "label" in img_cfg:
                opts["label"] = img_cfg["label"]
        art = img + art_fn(Ctx(sid, P, opts, esc))
        out += tl.show(f'<g clip-path="url(#scr-{esc(sid)})">{art}</g>', kind="card")

        text_col = P["dim"] if empty else P["primary"]
        sub_col = P["dim"] if empty else P["accent"]
        out += tl.show(self.text(24, 222, slot.get("title", ""), text_col, self.S["card_title"], weight="700"),
                       kind="card")
        out += tl.show(self.text(24, 248, slot.get("stack", ""), sub_col, self.S["card_stack"]) +
                       f'<rect x="24" y="266" width="{CW - 48}" height="2" fill="{P["dim"]}" opacity=".6"/>',
                       kind="card")
        return out

    def sec_telemetry(self):
        P, tl = self.P, self.tl
        c, tel = self.cfg.get("telemetry", {}), self.tel or {}
        W, M = self.W, self.M
        gh = tel.get("github")
        live = tel.get("mode") == "live"
        stamp = time.strftime(c.get("time_format", "%Y-%m-%d %H:%M UTC"), time.gmtime(tel.get("now", time.time())))
        right = f'{c.get("live_label", "LINK LIVE") if live else c.get("snapshot_label", "SNAPSHOT")}  {stamp}'
        head = self.header(c.get("title", "TELEMETRY"), right=right)
        if live:
            head += (f'<rect x="{W - M - len(right) * 8.4 - 14:.0f}" y="24" width="8" height="10" '
                     f'fill="{P["accent"]}"><animate attributeName="opacity" values="1;1;.15;.15" '
                     f'keyTimes="0;.5;.5;1" dur="1s" repeatCount="indefinite"/></rect>')
        b = tl.show(head, kind="chunk")

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
                    values[key] = c.get("no_link_text", "no link")
                else:
                    continue
            label = labels.get(key, key)
            dots = "." * max(3, int(c.get("leader_width", 24)) - len(label))
            b += tl.show(f'<text x="{M}" y="{y}" fill="{P["primary"]}" font-size="{self.S["telemetry"]}" '
                         f'xml:space="preserve">{esc(label)} {dots} '
                         f'<tspan fill="{P["accent"]}">{esc(values[key])}</tspan></text>')
            y += 28
        left_bottom = y

        lang_x = float(c.get("languages_x", 470))
        bar_x = float(c.get("language_bar_x", 590))
        b += tl.show(self.text(lang_x, 84, c.get("languages_title", "LANGUAGE MIX"), P["accent"],
                               self.S["table_header"], weight="700"), kind="chunk")
        langs = (gh or {}).get("languages") or {}
        blocks = int(c.get("language_blocks", 20))
        ry = 114
        if langs:
            total = sum(langs.values()) or 1
            for name, size in sorted(langs.items(), key=lambda kv: -kv[1])[: int(c.get("languages_shown", 5))]:
                pct = size / total
                filled = max(1, round(pct * blocks))
                row = self.text(lang_x, ry, name[:12], P["primary"], self.S["table_header"])
                row += "".join(f'<rect x="{bar_x + j * 11:.0f}" y="{ry - 12}" width="8" height="14" fill="none" '
                               f'stroke="{P["dim"]}"/>' for j in range(blocks))
                b += tl.show(row, hold=0.02)
                for j in range(filled):  # bars fill block by block, left to right
                    b += tl.show(f'<rect x="{bar_x + j * 11:.0f}" y="{ry - 12}" width="8" height="14" '
                                 f'fill="{P["primary"]}" stroke="{P["dim"]}"/>',
                                 hold=tl.cfg["block_seconds"] * 0.5)
                b += tl.show(self.text(W - M, ry, f"{pct * 100:.1f}%", P["accent"], self.S["small"], anchor="end"))
                ry += 28
        else:
            b += tl.show(self.text(lang_x, 114, c.get("no_languages_text", "// awaiting GitHub token"),
                                   P["dim"], self.S["small"]))
            ry += 28
        return max(left_bottom, ry) + 14, b

    def sec_footer(self):
        P, tl = self.P, self.tl
        c = self.cfg.get("footer", {})
        lines = c.get("lines", ["READY."])
        b = ""
        for i, line in enumerate(lines):
            size, col = (self.S["footer"], P["primary"]) if i == 0 else (self.S["body"] + 1, P["accent"])
            b += tl.show(self.text(self.M, 44 + i * 30, line, col, size))
        last = lines[-1] if lines else ""
        if c.get("cursor", True):
            b += self.blink_cursor(self.M + len(last) * self.adv(self.S["body"] + 1) + 10,
                                   44 + (len(lines) - 1) * 30, self.S["body"] + 1)
        return 40 + len(lines) * 30, b

    # ------------------------------------------------------------ compose
    def build(self):
        P, cfg, tl, W = self.P, self.cfg, self.tl, self.W
        body, clips, y = "", "", 0
        extra = float(self.L.get("section_gap", 0))

        def close(height):
            """Divider under a finished section, plus the pause before the next one starts."""
            nonlocal y
            out = ""
            if self.FX["dividers"]:
                out = tl.show(self.divider(y + height), hold=tl.cfg["section_seconds"], kind="chunk")
            else:
                tl.wait(tl.cfg["section_seconds"])
            y += height + extra
            return out

        sections = []
        logo = cfg.get("logo")  # no "logo" block at all, or "enabled": false -> no splash
        if logo and logo.get("enabled", True):
            sections.append(self.sec_logo)
        sections += [self.sec_boot, self.sec_whoami, self.sec_specs, self.sec_mission]
        for fn in sections:
            h, b = fn()
            body += f'<g transform="translate(0,{y})">{b}</g>'
            body += close(h)

        pcfg = cfg["programs"]
        slots = pcfg["slots"]
        used = sum(1 for s in slots if self.status_style(s.get("status", "")).get("in_use", True))
        right = pcfg.get("count_format", "{total} slots, {used} in use").format(total=len(slots), used=used)
        head = tl.show(self.header(pcfg.get("title", "LOADED PROGRAMS"), right=right), kind="chunk")
        body += f'<g transform="translate(0,{y})">{head}</g>'
        y += 56

        gap_y = int(self.L["card_row_gap"])
        n_rows = math.ceil(len(slots) / self.cols)
        for i, slot in enumerate(slots):
            row, col = divmod(i, self.cols)
            cy, cx = y + row * (CH + gap_y), self.card_x[col]
            clips += (f'<clipPath id="scr-{esc(slot["id"])}"><rect x="22" y="44" width="{CW - 44}" '
                      f'height="148" rx="6"/></clipPath>')
            body += f'<g transform="translate({cx:.0f},{cy})">{self.card(slot)}</g>'
            tl.wait(tl.cfg["section_seconds"] * 0.5)
        y += n_rows * (CH + gap_y) + 10
        if self.FX["dividers"]:
            body += tl.show(self.divider(y), hold=tl.cfg["section_seconds"], kind="chunk")

        for step, fn in [("telemetry", self.sec_telemetry), ("footer", self.sec_footer)]:
            h, b = fn()
            body += f'<g transform="translate(0,{y})">{b}</g>'
            if step == "telemetry":
                body += close(h)
            else:
                y += h

        H = y + 10
        clips += slot_image.shared_defs(ROOT)
        fx = self.FX
        sp = max(2, int(fx["scanline_spacing"]))
        blur = (f'<filter id="ph"><feGaussianBlur stdDeviation="{float(fx["blur"])}" result="b"/>'
                f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
                if float(fx["blur"]) > 0 else "")
        scan = (f'<pattern id="scan" width="{sp}" height="{sp}" patternUnits="userSpaceOnUse">'
                f'<rect width="{sp}" height="{max(1, sp // 2)}" fill="#000" '
                f'opacity="{float(fx["scanline_opacity"])}"/></pattern>' if fx["scanlines"] else "")
        glow = (f'<radialGradient id="glow" cx="50%" cy="20%" r="90%">'
                f'<stop offset="0" stop-color="{P["glow"]}" stop-opacity=".5"/>'
                f'<stop offset="1" stop-color="{P["background"]}" stop-opacity="0"/></radialGradient>'
                if fx["glow"] else "")
        flicker = ""
        if float(fx["flicker"]) > 0:
            k = min(0.3, float(fx["flicker"]))
            flicker = (f'<rect width="{W}" height="{H}" fill="{P["background"]}" opacity="0">'
                       f'<animate attributeName="opacity" values="0;{k:.3f};0;{k * .6:.3f};0" dur="4s" '
                       f'repeatCount="indefinite"/></rect>')
        radius = int(self.L["corner_radius"])
        border = (f'<rect x="1.5" y="1.5" width="{W - 3}" height="{H - 3}" rx="{max(0, radius - 1)}" fill="none" '
                  f'stroke="{P["dim"]}" stroke-width="3"/>' if self.L["border"] else "")
        return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{esc(cfg.get("font", "monospace"))}">
<defs>
{scan}{glow}{blur}
<clipPath id="screen"><rect width="{W}" height="{H}" rx="{radius}"/></clipPath>
{clips}
</defs>
<title>{esc(cfg.get("title", cfg["user"]))}</title>
<g clip-path="url(#screen)">
<rect width="{W}" height="{H}" fill="{P["background"]}"/>
{f'<rect width="{W}" height="{H}" fill="url(#glow)"/>' if fx["glow"] else ""}
<g{' filter="url(#ph)"' if blur else ""}>{body}</g>
{f'<rect width="{W}" height="{H}" fill="url(#scan)"/>' if fx["scanlines"] else ""}
{flicker}
</g>
{border}
</svg>'''


def render(cfg, telemetry):
    random.seed(7)
    slot_image.reset()
    return Profile(cfg, telemetry).build()
