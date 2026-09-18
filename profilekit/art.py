"""Animated art for the cartridge screens. Every animation is a seamless SMIL loop.

All art draws inside the card's screen rect: x 22..378, y 44..192 (card-local coords).
Each function gets a Ctx and returns an SVG string. Ids are prefixed with the slot id,
so the same art type can be used in more than one slot.
"""
import math
import random

SX0, SY0, SX1, SY1 = 22, 44, 378, 192


class Ctx:
    def __init__(self, sid, pal, opts, esc):
        self.sid, self.pal, self.opts, self.esc = sid, pal, opts or {}, esc

    def c(self, ref):
        """Palette key ('primary') or literal hex ('#FF0000')."""
        return ref if str(ref).startswith("#") else self.pal[ref]


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def windows(on, dur, attr="opacity", on_val="1", off_val="0"):
    """Discrete looping animation: `attr` is on_val inside each (start, end) window of [0, dur)."""
    pts, state = [(0.0, off_val)], off_val
    for s, e in sorted(on):
        pts.append((s, on_val))
        pts.append((e, off_val))
    merged = {}
    for t, v in pts:
        merged[round(min(max(t / dur, 0), 1), 6)] = v
    keys = sorted(merged)
    if keys[-1] == 1.0 and len(keys) > 1:
        keys = keys[:-1]
    # keyTimes need full precision: rounding them to 2 decimals shifts a switch by tens of
    # milliseconds, which is what used to make the terrain drop a frame on every row wrap.
    return (f'<animate attributeName="{attr}" calcMode="discrete" dur="{f(dur)}s" repeatCount="indefinite" '
            f'keyTimes="{";".join(f"{k:.6f}" for k in keys)}" values="{";".join(merged[k] for k in keys)}"/>')


# --------------------------------------------------------------------------- terrain
def terrain(x):
    """Ridgeline heightfield flying toward the camera along +z, with hidden-line removal.

    Each world row is a static path. Perspective of a row at depth z is a uniform scale f/z about
    the vanishing point, so one animateTransform per row is enough. Rows are drawn twice (B then A
    copy) and visibility-swapped at their wrap point, which keeps painter order correct all loop.
    """
    P, sid = x.pal, x.sid
    T = float(x.opts.get("loop_seconds", 16))
    R = int(x.opts.get("rows", 22))
    cx, yh = 200, 94
    z_near, z_far, focal, cam = 1.0, 17.0, 104.0, 1.0
    xmax = 30.0

    xs, v = [0.0], 0.0
    while v < xmax:
        v += max(0.09, 0.05 * abs(v))
        xs.append(min(v, xmax))
    xs = [-q for q in reversed(xs[1:])] + xs

    tau = 2 * math.pi

    def height(X, k):
        a = tau * k / R
        ridge = 0.28 + 1.9 * (1 - math.exp(-(X / 3.2) ** 2))
        n = (0.55 * math.sin(0.85 * X + a + 1.3) * math.cos(0.33 * X - a)
             + 0.30 * math.sin(1.6 * X - 2 * a + 0.4)
             + 0.15 * math.sin(2.9 * X + a + 2.1))
        return ridge * (0.5 + 0.5 * n)

    # scale keyframes, denser near the camera where 1/z changes fastest
    n_keys = 18
    phis = [1 - (1 - i / n_keys) ** 2 for i in range(n_keys + 1)]
    scales = [focal / (z_far + (z_near - z_far) * p) for p in phis]
    kt = ";".join(f"{p:.4f}" for p in phis)
    sv = ";".join(f"{s:.3f}" for s in scales)
    op_keys = "0;0.3;1"

    defs, b_uses, a_uses = "", "", ""
    for k in range(R):
        pts = " ".join(f"{f(X)},{cam - height(X, k):.3f}" for X in xs)
        d = f"M{-xmax},{cam + 14} L{pts} L{xmax},{cam + 14}"
        begin = -k * T / R
        defs += (f'<path id="{sid}-row{k}" d="{d}" fill="{P["screen"]}" stroke="{P["primary"]}" '
                 f'stroke-width="1.2" vector-effect="non-scaling-stroke" stroke-linejoin="round">'
                 f'<animateTransform attributeName="transform" type="scale" dur="{f(T)}s" begin="{begin:.3f}s" '
                 f'repeatCount="indefinite" keyTimes="{kt}" values="{sv}"/>'
                 f'<animate attributeName="stroke-opacity" dur="{f(T)}s" begin="{begin:.3f}s" repeatCount="indefinite" '
                 f'keyTimes="{op_keys}" values="0;.75;1"/></path>')
        wrap = T * (1 - k / R)
        a_uses += f'<use href="#{sid}-row{k}" xlink:href="#{sid}-row{k}">{windows([(0, wrap)], T, "visibility", "visible", "hidden")}</use>'
        if k:
            b_uses += f'<use href="#{sid}-row{k}" xlink:href="#{sid}-row{k}">{windows([(wrap, T)], T, "visibility", "visible", "hidden")}</use>'

    stars = ""
    rnd = random.Random(sid)
    for _ in range(14):
        stars += f'<rect x="{rnd.randint(30, 370)}" y="{rnd.randint(50, yh - 8)}" width="2" height="2" fill="{P["dim"]}"/>'
    hud = (f'<text x="32" y="60" fill="{P["dim"]}" font-size="10">SEED 0x7F3A</text>'
           f'<text x="368" y="60" text-anchor="end" fill="{P["dim"]}" font-size="10">Z+</text>'
           f'<rect x="346" y="53" width="3" height="7" fill="{P["accent"]}">'
           f'<animate attributeName="opacity" values="1;.2;1" dur="{f(T / 10)}s" repeatCount="indefinite"/></rect>')
    return (f'<defs>{defs}</defs>{stars}'
            f'<line x1="{SX0}" y1="{yh}" x2="{SX1}" y2="{yh}" stroke="{P["dim"]}"/>'
            f'<g transform="translate({cx},{yh})">{b_uses}{a_uses}</g>{hud}')


# --------------------------------------------------------------------------- terminal
def terminal(x):
    """SDSF-style job output that keeps scrolling new records, with a live counter."""
    P, sid, esc = x.pal, x.sid, x.esc
    step = float(x.opts.get("step_seconds", 0.45))
    rnd = random.Random("cobol-" + sid)
    M, V, lh, top = 16, 6, 14, 90
    lines, seq = [], 0
    for r in range(M):
        if r % 7 == 6:
            lines.append((f"IGZ0001I CUSTPROC STEP{r // 7 + 1:02d}0 CPU {rnd.randint(1, 9)}.{rnd.randint(10, 99)}S", "dim"))
        else:
            ok = rnd.random() > .12
            seq += 1
            lines.append((f"{seq:05d} CUST-{rnd.randint(1000, 9999)} {rnd.randint(10, 99999):>8}.{rnd.randint(10, 99)}  "
                          f"{'00' if ok else '04'}", "primary" if ok else "accent"))
    rows = ""
    for i in range(M + V):
        text, col = lines[i % M]
        rows += f'<text x="34" y="{top + i * lh}" fill="{P[col]}" font-size="11" xml:space="preserve">{esc(text)}</text>'
    dur = M * step
    scroll = ";".join(f"0 {-i * lh}" for i in range(M))
    kt = ";".join(f"{i / M:.4f}" for i in range(M))

    counters = ""
    for i in range(M):
        n = 1200 + (i + 1) * 587 + rnd.randint(0, 40)
        w = [(i * step, (i + 1) * step)]
        counters += (f'<text x="34" y="184" fill="{P["accent"]}" font-size="11" opacity="0" xml:space="preserve">'
                     f'REC {n:07d}  9M REC/S  RC=0000{windows(w, dur)}</text>')

    return (f'<clipPath id="{sid}-term"><rect x="{SX0}" y="{top - 11}" width="{SX1 - SX0}" height="{V * lh}"/></clipPath>'
            f'<rect x="{SX0}" y="{SY0 + 2}" width="{SX1 - SX0}" height="18" fill="{P["shade"]}"/>'
            f'<text x="34" y="59" fill="{P["accent"]}" font-size="11" font-weight="700" xml:space="preserve">{esc(x.opts.get("header", "SDSF OUTPUT"))}</text>'
            f'<text x="34" y="76" fill="{P["dim"]}" font-size="11" xml:space="preserve">{esc(x.opts.get("columns", ""))}</text>'
            f'<g clip-path="url(#{sid}-term)"><g>{rows}'
            f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" dur="{f(dur)}s" '
            f'repeatCount="indefinite" keyTimes="{kt}" values="{scroll}"/></g></g>'
            f'<line x1="{SX0}" y1="{top + V * lh - 8}" x2="{SX1}" y2="{top + V * lh - 8}" stroke="{P["dim"]}" stroke-dasharray="2 3"/>'
            f'{counters}'
            f'<rect x="262" y="174" width="7" height="12" fill="{P["primary"]}">'
            f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" repeatCount="indefinite"/></rect>')


# --------------------------------------------------------------------------- voxels
def voxels(x):
    """Isometric chunk; the top block gets mined (outline, crack stages, particles) and placed back."""
    P = x.pal
    D = float(x.opts.get("loop_seconds", 5))
    s = D / 5.0  # timeline below is authored for 5 s

    def faces(px, py, top):
        return (f'<polygon points="{px},{py} {px + 16},{py - 8} {px + 32},{py} {px + 16},{py + 8}" fill="{top}"/>'
                f'<polygon points="{px},{py} {px + 16},{py + 8} {px + 16},{py + 26} {px},{py + 18}" fill="{P["dim"]}"/>'
                f'<polygon points="{px + 32},{py} {px + 16},{py + 8} {px + 16},{py + 26} {px + 32},{py + 18}" fill="{P["shade"]}"/>')

    columns = [(0, 0, 1), (1, 0, 2), (2, 0, 1), (3, 0, 1), (0, 1, 1), (1, 1, 3), (2, 1, 1), (3, 1, 1),
               (0, 2, 1), (1, 2, 1), (2, 2, 2)]
    ox, oy = 164, 116
    out, target = "", (1, 1, 2)
    tx = ty = 0
    for gx, gy, h in columns:
        for k in range(h):
            px, py = ox + (gx - gy) * 16, oy + (gx + gy) * 8 - k * 18
            top = P["accent"] if k == h - 1 and h > 1 else P["primary"]
            if (gx, gy, k) == target:
                tx, ty = px, py
                out += f'<g>{faces(px, py, top)}{windows([(0, 2.3 * s), (3.6 * s, D)], D)}</g>'
            else:
                out += faces(px, py, top)

    ink = P["screen"]
    stages = [
        [(8, 0, 14, 2, 12, 5), (20, 18, 22, 21)],
        [(14, 2, 19, -1, 24, 1), (4, 9, 6, 13, 4, 16), (27, 10, 25, 14)],
        [(24, 1, 22, 4), (6, 13, 10, 15), (25, 14, 28, 17), (11, -3, 13, -5)],
        [(19, -1, 17, -5), (10, 15, 11, 19), (22, 21, 20, 23), (30, 3, 26, 5)],
    ]
    cracks = ""
    for i, segs in enumerate(stages):
        t0 = (0.7 + i * 0.4) * s
        body = "".join(f'<polyline points="{" ".join(f"{tx + a},{ty + b}" for a, b in zip(seg[::2], seg[1::2]))}" '
                       f'fill="none" stroke="{ink}" stroke-width="1.6"/>' for seg in segs)
        cracks += f'<g opacity="0">{body}{windows([(t0, 2.3 * s)], D)}</g>'

    hexo = (f'{tx},{ty} {tx + 16},{ty - 8} {tx + 32},{ty} {tx + 32},{ty + 18} {tx + 16},{ty + 26} {tx},{ty + 18}')
    outline = (f'<g opacity="0" fill="none" stroke="{ink}" stroke-width="1.4"><polygon points="{hexo}"/>'
               f'<polyline points="{tx},{ty} {tx + 16},{ty + 8} {tx + 32},{ty}"/><line x1="{tx + 16}" y1="{ty + 8}" x2="{tx + 16}" y2="{ty + 26}"/>'
               f'{windows([(0.5 * s, 2.3 * s)], D)}</g>')
    flash = (f'<polygon points="{hexo}" fill="none" stroke="{P["accent"]}" stroke-width="2" opacity="0">'
             f'{windows([(3.6 * s, 3.8 * s)], D)}</polygon>')

    parts = ""
    rnd = random.Random("dig")
    for i in range(6):
        dx, up = rnd.uniform(-26, 26), rnd.uniform(8, 20)
        col = P["accent"] if i % 2 else P["dim"]
        t0, t1 = 2.3 * s, 2.95 * s
        parts += (f'<rect x="{tx + 14}" y="{ty + 6}" width="4" height="4" fill="{col}" opacity="0">'
                  f'{windows([(t0, t1)], D)}'
                  f'<animateTransform attributeName="transform" type="translate" dur="{f(D)}s" repeatCount="indefinite" '
                  f'keyTimes="0;{t0 / D:.4f};{(t0 + t1) / 2 / D:.4f};{t1 / D:.4f};1" '
                  f'values="0 0;0 0;{dx / 2:.1f} {-up:.1f};{dx:.1f} {up * .6:.1f};{dx:.1f} {up * .6:.1f}"/></rect>')
    return f'<g transform="translate(200,119) scale(1.45) translate(-188,-131)">{out}{cracks}{outline}{parts}{flash}</g>'


# --------------------------------------------------------------------------- engine
def engine(x):
    """Engine diagram -> shader compile log -> Gouraud-shaded triangle, looping."""
    P, sid, esc, o = x.pal, x.sid, x.esc, x.opts
    D = float(o.get("loop_seconds", 12))
    s = D / 12.0
    names = (o.get("nodes") or ["input", "scene", "renderer", "OpenGL", "Vulkan"]) + [""] * 5

    # phase 1: diagram
    boxes = [(36, 72, names[0]), (36, 132, names[1]), (154, 102, names[2]), (272, 72, names[3]), (272, 132, names[4])]
    g1 = ""
    for a, c in [((128, 67), (154, 97)), ((128, 127), (154, 97)), ((246, 97), (272, 67)), ((246, 97), (272, 127))]:
        g1 += f'<line x1="{a[0]}" y1="{a[1]}" x2="{c[0]}" y2="{c[1]}" stroke="{P["dim"]}" stroke-width="1.5"/>'
    for i, (bx, by, t) in enumerate(boxes):
        g1 += f'<rect x="{bx}" y="{by - 16}" width="92" height="26" fill="{P["screen"]}" stroke="{P["accent"] if i == 2 else P["primary"]}"/>'
        g1 += f'<text x="{bx + 46}" y="{by + 2}" text-anchor="middle" fill="{P["primary"]}" font-size="12">{esc(t)}</text>'
    pulse = (f'<circle r="3" fill="{P["accent"]}"><animateMotion dur="1.4s" repeatCount="indefinite" '
             f'path="M128,67 L154,97 L246,97 L272,127"/></circle>')
    g1 += pulse + f'<text x="36" y="184" fill="{P["dim"]}" font-size="11">frame 000001  16.6ms</text>'
    p1 = f'<g>{g1}{windows([(0, 4.4 * s)], D)}</g>'

    # phase 2: compile log
    t_log, t_end = 4.6 * s, 7.6 * s
    log = [(o.get("command", "$ engine build"), "dim"), ("compiling shaders...", "accent")]
    for sh in o.get("shaders", ["basic.vert", "basic.frag"]):
        log.append((f"  {sh:<14} .spv  ok", "primary"))
    log.append(("pipeline created", "primary"))
    p2 = ""
    gap = (t_end - t_log - 0.9 * s) / max(1, len(log))
    for i, (text, col) in enumerate(log):
        t0 = t_log + i * gap
        p2 += f'<text x="36" y="{66 + i * 17}" fill="{P[col]}" font-size="12" opacity="0" xml:space="preserve">{esc(text)}{windows([(t0, t_end)], D)}</text>'
    bar_t0, bar_t1 = t_log + gap, t_log + (len(log) - 1) * gap
    bar = (f'<g opacity="0">{windows([(bar_t0, t_end)], D)}'
           f'<rect x="36" y="174" width="300" height="8" fill="none" stroke="{P["dim"]}"/>'
           f'<rect x="38" y="176" width="0" height="4" fill="{P["accent"]}">'
           f'<animate attributeName="width" dur="{f(D)}s" repeatCount="indefinite" '
           f'keyTimes="0;{bar_t0 / D:.4f};{bar_t1 / D:.4f};1" values="0;0;296;296"/></rect></g>')
    p2 += bar

    # phase 3: Gouraud triangle. Barycentric interpolation baked into flat sub-triangles:
    # no blend modes or filters, so it renders the same in every browser GitHub users have.
    cols = [x.c(v) for v in (o.get("triangle_colors") or ["#FF3B4E", "#3BFF6A", "#3B7BFF"])[:3]]
    rgb = [tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for h in cols]
    V = [(200, 54), (128, 170), (272, 170)]
    N = int(o.get("triangle_subdivisions", 18))

    def at(i, j):  # lattice point: i steps down from V0, j steps toward V2
        a, b, c = (N - i) / N, (i - j) / N, j / N
        return (a * V[0][0] + b * V[1][0] + c * V[2][0], a * V[0][1] + b * V[1][1] + c * V[2][1]), (a, b, c)

    def shade(ws):
        w = [sum(q) / 3 for q in zip(*ws)]
        r, g, bl = (min(255, round(sum(w[k] * rgb[k][ch] for k in range(3)) * 1.15)) for ch in range(3))
        return f"#{r:02x}{g:02x}{bl:02x}"

    layers = ""
    for i in range(N):
        for j in range(i + 1):
            for tri_ij in ([(i, j), (i + 1, j), (i + 1, j + 1)], [(i, j), (i + 1, j + 1), (i, j + 1)] if j < i else None):
                if not tri_ij:
                    continue
                pts, ws = zip(*(at(a, b) for a, b in tri_ij))
                col = shade(ws)
                layers += (f'<polygon points="{" ".join(f"{px:.1f},{py:.1f}" for px, py in pts)}" '
                           f'fill="{col}" stroke="{col}" stroke-width=".6"/>')
    grads = ""
    t_tri = 7.8 * s
    p3 = (f'<g opacity="0">{windows([(t_tri, D)], D)}'
          f'<g>{layers}</g>'
          f'<text x="36" y="184" fill="{P["dim"]}" font-size="11">vkQueuePresent  frame 000001  16.6ms</text>'
          f'<text x="368" y="60" text-anchor="end" fill="{P["accent"]}" font-size="10">HELLO TRIANGLE</text></g>')
    flash = (f'<rect x="{SX0}" y="{SY0}" width="{SX1 - SX0}" height="{SY1 - SY0}" fill="{P["primary"]}" opacity="0">'
             f'{windows([(t_tri, t_tri + 0.08 * s)], D, on_val=".25")}</rect>')
    return f'{p1}{p2}{p3}{flash}'


# --------------------------------------------------------------------------- idle
def idle(x):
    """Empty slot: drifting static, one slow rolling band, blinking cursor. Quiet on purpose.
    When the slot has an image, these layers draw on top of it (label moved per `label_position`).

    The static is a few complete speckle fields swapped in turn, so the grain keeps moving without
    animating every dot: the screen breathes, the picture on it does not."""
    P, sid, esc = x.pal, x.sid, x.esc
    rnd = random.Random("idle-" + sid)
    density = float(x.opts.get("noise", 1.0))
    per = max(0, int(240 * density))
    fields = max(1, int(x.opts.get("noise_fields", 3)))
    cycle = float(x.opts.get("noise_seconds", 0.55))
    noise = ""
    for i in range(fields):
        dots = "".join(f'<rect x="{rnd.randint(24, 372)}" y="{rnd.randint(46, 188)}" width="3" height="2" '
                       f'fill="{P["primary"]}" opacity="{rnd.choice([.08, .14, .22])}"/>' for _ in range(per))
        if not dots:
            continue
        if fields == 1:
            noise += dots
        else:
            win = [(i * cycle / fields, (i + 1) * cycle / fields)]
            noise += f'<g opacity="0">{windows(win, cycle)}{dots}</g>'
    band = (f'<rect x="{SX0}" y="{SY0}" width="{SX1 - SX0}" height="22" fill="{P["primary"]}" opacity=".04">'
            f'<animate attributeName="y" values="{SY0 - 22};{SY1}" dur="{f(float(x.opts.get("band_seconds", 7)))}s" '
            f'repeatCount="indefinite"/></rect>')
    label = str(x.opts.get("label", "NO SIGNAL"))
    pos = x.opts.get("label_position", "center")
    if not label or pos == "none":
        return noise + band
    bw = max(140, len(label) * 8 + 44)
    bx, by = {"center": (200 - bw / 2, 102), "bottom": (200 - bw / 2, 156),
              "top": (200 - bw / 2, 50), "bottom-right": (370 - bw, 156),
              "right": (370 - bw, 102), "left": (30, 102)}.get(pos, (200 - bw / 2, 102))
    tx = bx + (bw - 16) / 2
    return (noise + band +
            f'<rect x="{bx:.0f}" y="{by}" width="{bw:.0f}" height="30" fill="{P["screen"]}" stroke="{P["dim"]}"/>'
            f'<text x="{tx:.0f}" y="{by + 20}" text-anchor="middle" fill="{P["dim"]}" font-size="13">{esc(label)}</text>'
            f'<rect x="{tx + len(label) * 3.9 + 6:.0f}" y="{by + 10}" width="7" height="12" fill="{P["dim"]}">'
            f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.6s" repeatCount="indefinite"/></rect>')


ARTS = {"terrain": terrain, "terminal": terminal, "voxels": voxels, "engine": engine, "idle": idle}
