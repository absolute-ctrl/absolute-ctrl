"""Turn an image into a grid of terminal characters, so a logo can be printed row by row.

Stdlib only (zlib is enough for PNG), because the renderer has to run on Vercel with no
dependencies. Non-interlaced 8-bit PNGs of any colour type are supported, which covers anything
exported from an image editor. Anything else raises, and the caller falls back to text.

Each cell gets two things: how much ink it has (how far the source is from the page colour), which
picks a character from the ramp, and a colour class (dark / mid / bright), which picks a palette
colour. That split is what keeps a dark visor readable next to bright gold trim: coverage draws the
shape, colour draws the material.
"""
import os
import struct
import zlib

RAMP = " .:-=+*#%@"
_cache = {}

DEFAULTS = {
    "src": "assets/helmet.png",
    "columns": 46,          # character grid width
    "cell_width": 6.0,      # px per character cell
    "row_height": 9.6,      # px per row
    "font_scale": 0.95,     # glyph size relative to one cell
    "ramp": RAMP,
    "threshold": 0.10,      # ink below this is treated as empty page
    "invert": False,        # true for art drawn light-on-dark
    "gamma": 1.0,
    "saturation": 0.16,     # above this, a cell counts as coloured (gold trim) rather than grey
    "dark_level": 0.35,     # luminance below this is the "dark" class (the visor)
    "bright_level": 0.42,   # coloured cells brighter than this are the "bright" class
    "colors": {"dark": "dim", "mid": "primary", "bright": "accent"},
    "density": {"dark": 0.6, "mid": 0.92, "bright": 1.0},
}


def merged(cfg):
    out = dict(DEFAULTS)
    out.update({k: v for k, v in (cfg or {}).items() if v is not None})
    for key in ("colors", "density"):
        merged_sub = dict(DEFAULTS[key])
        merged_sub.update((cfg or {}).get(key) or {})
        out[key] = merged_sub
    return out


# --------------------------------------------------------------------------- PNG
def decode_png(data):
    """Returns (width, height, rows) with rows[y][x] = (r, g, b, a), 0-255."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG (the mosaic logo needs a PNG; use mode 'image' for JPEG)")
    i, idat, pal, trns = 8, b"", None, None
    w = h = ct = 0
    while i + 8 <= len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ, body = data[i + 4:i + 8], data[i + 8:i + 8 + ln]
        i += 12 + ln
        if typ == b"IHDR":
            w, h, bd, ct, _, _, inter = struct.unpack(">IIBBBBB", body)
            if bd != 8 or inter != 0:
                raise ValueError("PNG must be 8-bit and non-interlaced")
        elif typ == b"PLTE":
            pal = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
    if not idat or not w:
        raise ValueError("PNG has no image data")
    raw = zlib.decompress(idat)
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    stride = w * ch
    out, prev, p = bytearray(stride * h), bytearray(stride), 0
    for y in range(h):
        flt = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if flt == 1:
            for x in range(ch, stride):
                line[x] = (line[x] + line[x - ch]) & 255
        elif flt == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif flt == 3:
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif flt == 4:
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                b, c = prev[x], (prev[x - ch] if x >= ch else 0)
                est = a + b - c
                da, db, dc = abs(est - a), abs(est - b), abs(est - c)
                line[x] = (line[x] + (a if da <= db and da <= dc else (b if db <= dc else c))) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line

    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            o = y * stride + x * ch
            if ct == 0:
                v = out[o]
                row.append((v, v, v, 255))
            elif ct == 4:
                v = out[o]
                row.append((v, v, v, out[o + 1]))
            elif ct == 2:
                row.append((out[o], out[o + 1], out[o + 2], 255))
            elif ct == 6:
                row.append((out[o], out[o + 1], out[o + 2], out[o + 3]))
            else:
                k = out[o]
                r, g, b = pal[k * 3:k * 3 + 3]
                row.append((r, g, b, trns[k] if trns and k < len(trns) else 255))
        rows.append(row)
    return w, h, rows


# --------------------------------------------------------------------------- mosaic
def cells(cfg, root):
    """Character grid for the logo: list of rows, each a list of (char, palette_key) or None."""
    c = merged(cfg)
    key = (c["src"], c["columns"], c["cell_width"], c["row_height"], c["ramp"], c["threshold"],
           c["invert"], c["gamma"], c["saturation"], c["dark_level"], c["bright_level"],
           tuple(sorted(c["colors"].items())), tuple(sorted(c["density"].items())))
    if key in _cache:
        return _cache[key]

    src = c["src"] if os.path.isabs(c["src"]) else os.path.join(root, c["src"])
    with open(src, "rb") as fh:
        w, h, px = decode_png(fh.read())

    cols = max(4, int(c["columns"]))
    rows_n = max(1, round(cols * (h / w) * (float(c["cell_width"]) / float(c["row_height"]))))
    ramp = c["ramp"] or RAMP
    grid = []
    for r in range(rows_n):
        y0, y1 = int(r * h / rows_n), max(int(r * h / rows_n) + 1, int((r + 1) * h / rows_n))
        line = []
        for q in range(cols):
            x0, x1 = int(q * w / cols), max(int(q * w / cols) + 1, int((q + 1) * w / cols))
            R = G = B = A = 0.0
            n = 0
            for y in range(y0, y1):
                prow = px[y]
                for x in range(x0, x1):
                    pr, pg, pb, pa = prow[x]
                    k = pa / 255.0
                    R += pr * k
                    G += pg * k
                    B += pb * k
                    A += k
                    n += 1
            R, G, B, A = R / n / 255.0, G / n / 255.0, B / n / 255.0, A / n
            mx, mn = max(R, G, B), min(R, G, B)
            lum = 0.299 * R + 0.587 * G + 0.114 * B
            sat = 0.0 if mx <= 0 else (mx - mn) / mx
            ink = (lum if c["invert"] else 1.0 - mn) * A
            if ink <= float(c["threshold"]):
                line.append(None)
                continue
            if sat > float(c["saturation"]):
                cls = "bright" if lum > float(c["bright_level"]) else "mid"
            else:
                cls = "dark" if lum < float(c["dark_level"]) else "mid"
            v = min(1.0, max(0.0, ink ** float(c["gamma"]) * float(c["density"][cls])))
            line.append((ramp[min(len(ramp) - 1, int(v * len(ramp)))], c["colors"][cls]))
        grid.append(line)
    _cache[key] = (grid, cols, rows_n, c)
    return _cache[key]


def runs(row):
    """Group a mosaic row into (start_column, text, palette_key) runs, so one <tspan> covers many
    characters instead of one per cell."""
    out, start, buf, key = [], 0, "", None
    for i, cell in enumerate(row):
        ch, k = (cell if cell else (" ", None))
        if k != key:
            if buf.strip() and key:
                out.append((start, buf, key))
            start, buf, key = i, "", k
        buf += ch
    if buf.strip() and key:
        out.append((start, buf, key))
    return out
