"""Background image for a slot screen, embedded in the SVG and tinted to the palette.

GitHub renders the SVG through <img>, which blocks external files, so the image is embedded as a
base64 data URI. The theme treatment is an SVG filter chain applied by the viewer's browser:
grayscale -> contrast -> optional posterize -> gradient map (screen -> dim -> highlight).
Because the colors come from the palette, switching theme re-tints the image automatically.
"""
import base64
import os
import struct

SCREEN = (22, 44, 356, 148)  # x, y, w, h in card coordinates
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
_cache = {}
_used = {}  # src -> def id, for the current render


def reset():
    _used.clear()


def shared_defs(root):
    """One embedded copy per distinct image, referenced by every slot that uses it."""
    out = ""
    for src, did in _used.items():
        uri, w, h = load(src, root)
        out += f'<image id="{did}" width="{w}" height="{h}" preserveAspectRatio="none" href="{uri}" xlink:href="{uri}"/>'
    return out


def _size(data):
    """Pixel size of PNG / GIF / JPEG / WebP bytes, stdlib only."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X":
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if kind == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L":
            b = int.from_bytes(data[21:25], "little")
            return 1 + (b & 0x3FFF), 1 + ((b >> 14) & 0x3FFF)
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise ValueError("unsupported image format (use PNG, JPEG, GIF or WebP)")


def load(src, root):
    """Returns (data_uri, width, height). `src` is a repo-relative path."""
    if src in _cache:
        return _cache[src]
    path = src if os.path.isabs(src) else os.path.join(root, src)
    with open(path, "rb") as fh:
        data = fh.read()
    w, h = _size(data)
    mime = MIME.get(os.path.splitext(path)[1].lower(), "image/png")
    _cache[src] = (f"data:{mime};base64,{base64.b64encode(data).decode()}", w, h)
    return _cache[src]


def _rgb(hexstr):
    h = hexstr.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _filter(fid, pal, cfg):
    def color(key, default):
        ref = str(cfg.get(key, default))
        return _rgb(ref if ref.startswith("#") else pal[ref])

    lo, mid, hi = color("shadow", "screen"), color("midtone", "dim"), color("highlight", "primary")
    c = float(cfg.get("contrast", 1.25))
    bright = float(cfg.get("brightness", 0.0))
    icpt = (1 - c) / 2 + bright
    levels = int(cfg.get("levels", 5))
    poster = ""
    if levels >= 2:
        steps = " ".join(f"{i / (levels - 1):.3f}" for i in range(levels))
        poster = (f'<feComponentTransfer><feFuncR type="discrete" tableValues="{steps}"/>'
                  f'<feFuncG type="discrete" tableValues="{steps}"/><feFuncB type="discrete" tableValues="{steps}"/></feComponentTransfer>')
    ramp = [f"{lo[ch]:.3f} {mid[ch]:.3f} {hi[ch]:.3f}" for ch in range(3)]
    return (f'<filter id="{fid}" x="-12%" y="-12%" width="124%" height="124%" color-interpolation-filters="sRGB">'
            f'<feColorMatrix type="matrix" values=".2126 .7152 .0722 0 0  .2126 .7152 .0722 0 0  .2126 .7152 .0722 0 0  0 0 0 1 0"/>'
            f'<feComponentTransfer><feFuncR type="linear" slope="{c}" intercept="{icpt:.3f}"/>'
            f'<feFuncG type="linear" slope="{c}" intercept="{icpt:.3f}"/><feFuncB type="linear" slope="{c}" intercept="{icpt:.3f}"/></feComponentTransfer>'
            f'{poster}{_cutout(cfg)}'
            f'<feComponentTransfer result="tint"><feFuncR type="table" tableValues="{ramp[0]}"/>'
            f'<feFuncG type="table" tableValues="{ramp[1]}"/><feFuncB type="table" tableValues="{ramp[2]}"/></feComponentTransfer>'
            f'{_haunt(cfg)}'
            f'</filter>')


def _haunt(cfg):
    """Optional bloom: a blurred copy of the picture with a faint sharp core over it.

    The subject stops reading as a photograph and starts reading as something glowing behind the
    glass -- more light, less detail. `radius` is how far the halo spreads, `halo` how bright it
    is, and `core` how much of the sharp original survives on top (low values are the ghostly end).
    """
    g = cfg.get("glow")
    if not g or not g.get("enabled", True):
        return ""
    radius = float(g.get("radius", 3.0))
    halo = float(g.get("halo", 1.0))
    core = float(g.get("core", 0.35))
    return (f'<feGaussianBlur in="tint" stdDeviation="{radius}" result="blur"/>'
            f'<feComponentTransfer in="blur" result="halo"><feFuncA type="linear" slope="{halo}"/></feComponentTransfer>'
            f'<feComponentTransfer in="tint" result="core"><feFuncA type="linear" slope="{core}"/></feComponentTransfer>'
            f'<feMerge><feMergeNode in="halo"/><feMergeNode in="core"/></feMerge>')


def _cutout(cfg):
    """Optional luminance key: the picture's own dark background becomes transparent, so the
    subject sits on the phosphor instead of inside a visible rectangle.

    Alpha is taken from the (already grayscaled and contrasted) luminance and then shaped by a
    curve: everything below `low` is fully transparent, everything above `high` fully opaque,
    with a soft ramp between. Because it runs before the gradient map, the colours are unaffected.
    """
    cut = cfg.get("cutout")
    if not cut or not cut.get("enabled", True):
        return ""
    lo = float(cut.get("low", 0.25))
    hi = max(lo + 1e-3, float(cut.get("high", 0.55)))
    gamma = float(cut.get("gamma", 1.0))
    floor = float(cut.get("floor", 0.0))      # alpha kept below `low`, 0 = fully cut
    ceil = float(cut.get("ceiling", 1.0))     # alpha reached above `high`
    steps = 17
    table = []
    for i in range(steps):
        v = i / (steps - 1)
        a = 0.0 if v <= lo else (1.0 if v >= hi else ((v - lo) / (hi - lo)) ** gamma)
        table.append(f"{floor + (ceil - floor) * a:.3f}")
    return (f'<feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  1 0 0 0 0"/>'
            f'<feComponentTransfer><feFuncA type="table" tableValues="{" ".join(table)}"/></feComponentTransfer>')


def layer(sid, cfg, pal, root, box=SCREEN):
    """SVG for the image layer of one slot (empty string when disabled).

    `box` is the (x, y, w, h) rectangle the image is fitted into. It defaults to a card screen;
    the manufacturer splash passes its own rectangle."""
    if not cfg or not cfg.get("enabled", True) or not cfg.get("src"):
        return ""
    uri, iw, ih = load(cfg["src"], root)
    cx, cy, cw, ch = (list(cfg.get("crop") or [0, 0, 1, 1]) + [0, 0, 1, 1][len(cfg.get("crop") or []):])[:4]
    rx, ry, rw, rh = cx * iw, cy * ih, cw * iw, ch * ih  # crop rect in source pixels
    sx, sy, sw, sh = box
    fit = cfg.get("fit", "contain")
    scale = (max if fit == "cover" else min)(sw / rw, sh / rh) * float(cfg.get("zoom", 1.0))
    ax, ay = (list(cfg.get("align") or [0.5, 0.5]) + [0.5, 0.5])[:2]
    # position so the crop rect sits inside the screen according to `align` (0 = left/top, 1 = right/bottom)
    dx = sx + (sw - rw * scale) * ax - rx * scale
    dy = sy + (sh - rh * scale) * ay - ry * scale
    mask_id, filt_id = f"imgmask-{sid}", f"imgfx-{sid}"
    did = _used.setdefault(cfg["src"], f"img{len(_used)}")
    treat = cfg.get("treatment", "theme")
    filt = _filter(filt_id, pal, cfg) if treat == "theme" else ""
    render = ' style="image-rendering:pixelated"' if cfg.get("pixelated") else ""
    use = f'<use href="#{did}" xlink:href="#{did}" transform="translate({dx:.1f},{dy:.1f}) scale({scale:.4f})"{render}/>'
    body = f'<g filter="url(#{filt_id})">{use}</g>' if filt else use

    # visible rect = crop rect on screen, clipped to the screen; edges fade into the phosphor
    vx, vy = max(sx, dx + rx * scale), max(sy, dy + ry * scale)
    vw, vh = min(sx + sw, dx + (rx + rw) * scale) - vx, min(sy + sh, dy + (ry + rh) * scale) - vy
    fade = max(0.0, min(0.45, float(cfg.get("fade_edges", 0.18))))
    if cfg.get("fade_shape", "box") == "radial":
        # One soft pool of light: full strength around the middle, falling away in every direction
        # at the same rate, so there are no corners and nothing to mark where the picture stops.
        inner = max(0.0, min(0.9, float(cfg.get("fade_inner", 0.15))))
        fx, fy = (list(cfg.get("fade_center") or [0.5, 0.5]) + [0.5, 0.5])[:2]
        mid = inner + (1 - inner) * 0.55
        grad = (f'<radialGradient id="{mask_id}-r" cx="{fx}" cy="{fy}" r="{float(cfg.get("fade_radius", 0.72))}">'
                f'<stop offset="0" stop-color="#fff"/><stop offset="{inner:.3f}" stop-color="#fff"/>'
                f'<stop offset="{mid:.3f}" stop-color="#fff" stop-opacity=".55"/>'
                f'<stop offset="1" stop-color="#000"/></radialGradient>')
        defs = (f'{filt}{grad}'
                f'<mask id="{mask_id}-a" maskUnits="userSpaceOnUse" x="{sx}" y="{sy}" width="{sw}" height="{sh}">'
                f'<rect x="{vx:.1f}" y="{vy:.1f}" width="{vw:.1f}" height="{vh:.1f}" fill="url(#{mask_id}-r)"/></mask>')
        return (f'<defs>{defs}</defs><g opacity="{float(cfg.get("opacity", 0.7))}">'
                f'<g mask="url(#{mask_id}-a)">{body}</g></g>'
                f'{_hotspot(mask_id, cfg, body, (vx, vy, vw, vh))}')
    stops = f'<stop offset="0" stop-color="#000"/><stop offset="{fade}" stop-color="#fff"/><stop offset="{1 - fade}" stop-color="#fff"/><stop offset="1" stop-color="#000"/>'
    defs = (f'{filt}<linearGradient id="{mask_id}-h">{stops}</linearGradient>'
            f'<linearGradient id="{mask_id}-v" x2="0" y2="1">{stops}</linearGradient>'
            f'<mask id="{mask_id}-a" maskUnits="userSpaceOnUse" x="{sx}" y="{sy}" width="{sw}" height="{sh}">'
            f'<rect x="{vx:.1f}" y="{vy:.1f}" width="{vw:.1f}" height="{vh:.1f}" fill="url(#{mask_id}-h)"/></mask>'
            f'<mask id="{mask_id}-b" maskUnits="userSpaceOnUse" x="{sx}" y="{sy}" width="{sw}" height="{sh}">'
            f'<rect x="{vx:.1f}" y="{vy:.1f}" width="{vw:.1f}" height="{vh:.1f}" fill="url(#{mask_id}-v)"/></mask>')
    return (f'<defs>{defs}</defs><g mask="url(#{mask_id}-b)" opacity="{float(cfg.get("opacity", 0.7))}">'
            f'<g mask="url(#{mask_id}-a)">{body}</g></g>')


def _hotspot(mask_id, cfg, body, rect):
    """Optional second pass of the same layer, masked to a soft circle on the face.

    It is the picture itself drawn again rather than a wash of colour over it, so the extra light
    only lands where the subject is: the face reads as the source of the glow and it falls off
    with distance, while the background stays exactly as transparent as it was.
    """
    h = cfg.get("hotspot")
    if not h or not h.get("enabled", True):
        return ""
    vx, vy, vw, vh = rect
    cx, cy = (list(h.get("center") or [0.5, 0.42]) + [0.5, 0.42])[:2]
    r = float(h.get("radius", 0.34))
    inner = max(0.0, min(0.95, float(h.get("inner", 0.0))))
    strength = max(0.0, min(1.0, float(h.get("strength", 0.45))))
    hid = f"{mask_id}-hot"
    return (f'<defs><radialGradient id="{hid}-g" cx="{cx}" cy="{cy}" r="{r}">'
            f'<stop offset="0" stop-color="#fff"/><stop offset="{inner:.3f}" stop-color="#fff"/>'
            f'<stop offset="{inner + (1 - inner) * 0.5:.3f}" stop-color="#fff" stop-opacity=".5"/>'
            f'<stop offset="1" stop-color="#000"/></radialGradient>'
            f'<mask id="{hid}" maskUnits="userSpaceOnUse" x="{vx:.1f}" y="{vy:.1f}" '
            f'width="{vw:.1f}" height="{vh:.1f}">'
            f'<rect x="{vx:.1f}" y="{vy:.1f}" width="{vw:.1f}" height="{vh:.1f}" '
            f'fill="url(#{hid}-g)"/></mask></defs>'
            f'<g opacity="{strength}"><g mask="url(#{hid})">{body}</g></g>')
