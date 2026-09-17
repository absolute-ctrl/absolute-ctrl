"""Sequential reveal timeline.

The whole profile is printed like a terminal session: one thing at a time, in order, and nothing
starts before the thing before it has finished. A `Timeline` is just a clock. Every section asks it
for the current time, wraps its SVG in a group that snaps from hidden to visible at that time, and
then advances the clock. Because the clock only ever moves forward, the order on screen is exactly
the order the sections were built in -- no two things ever animate at once.

Reveals are instant by default (`<set>`, not a fade), which is what makes it read as text being
written rather than a block phasing in. The slow parts are explicit: progress bars, meter blocks
and typed command lines, which have real durations and are also charged to the same clock.
"""

DEFAULTS = {
    "enabled": True,          # false -> render everything already visible (no animation at all)
    "speed": 1.0,             # global multiplier: 2.0 plays the whole sequence twice as fast
    "start_delay": 0.25,      # dead time before the first thing appears
    "line_seconds": 0.07,     # gap after one printed line
    "chunk_seconds": 0.16,    # gap after a block that appears all at once (frames, headers)
    "section_seconds": 0.30,  # extra gap between sections
    "pause_seconds": 0.14,    # "thinking" pause, e.g. between a label and its result
    "block_seconds": 0.045,   # gap per meter/bar block when one fills up
    "bar_seconds": 0.80,      # default progress-bar fill
    "card_seconds": 0.16,     # gap between the parts of a program card
    "card_load_seconds": 0.35,  # how long a card screen shows its loading bar before the art
    "typing": {
        "enabled": True,          # the user's own command lines are typed out
        "chars_per_second": 26.0,
        "cursor": True,
        "blink_seconds": 1.0,
    },
    "logo": {
        "row_seconds": 0.025,   # one mosaic row of the manufacturer logo
        "bar_seconds": 1.10,    # the "initializing" bar under it
        "hold_seconds": 0.70,   # pause before the BIOS takes over
    },
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(base.get(k), dict) and isinstance(v, dict) else v
    return out


class Timeline:
    def __init__(self, cfg=None):
        a = _merge(DEFAULTS, (cfg or {}).get("animation"))
        self.cfg = a
        self.on = bool(a["enabled"])
        self.speed = float(a["speed"]) or 1.0
        self.t = self.d(float(a["start_delay"])) if self.on else 0.0
        self._n = 0

    # ---------------------------------------------------------------- clock
    def get(self, key, default=None):
        return self.cfg.get(key, default)

    def d(self, seconds):
        """A duration in wall-clock seconds, after the global speed multiplier."""
        return float(seconds) / self.speed

    def now(self):
        return self.t

    def wait(self, seconds):
        """Charge `seconds` to the clock and return the new time."""
        if self.on:
            self.t += self.d(seconds)
        return self.t

    def gap(self, kind="line"):
        return self.wait(self.cfg.get(f"{kind}_seconds", self.cfg["line_seconds"]))

    def uid(self, prefix="a"):
        self._n += 1
        return f"{prefix}{self._n}"

    @staticmethod
    def fmt(t):
        return f"{t:.2f}s"

    # --------------------------------------------------------------- reveal
    def set_visible(self, begin=None):
        """SMIL that snaps an element from hidden to visible. Instant on purpose."""
        return f'<set attributeName="opacity" to="1" begin="{self.fmt(self.now() if begin is None else begin)}" fill="freeze"/>'

    def show(self, svg, hold=None, kind="line", begin=None):
        """Reveal `svg` at the current time, then advance the clock by `hold`."""
        if not self.on:
            return svg
        out = f'<g opacity="0">{self.set_visible(begin)}{svg}</g>'
        self.wait(self.cfg[f"{kind}_seconds"] if hold is None else hold)
        return out

    def show_at(self, svg, begin):
        """Reveal `svg` at an explicit time without touching the clock."""
        if not self.on:
            return svg
        return f'<g opacity="0">{self.set_visible(begin)}{svg}</g>'

    def steps(self, items, hold=None, kind="line"):
        """Reveal a list of SVG fragments one after another."""
        return "".join(self.show(s, hold=hold, kind=kind) for s in items)
