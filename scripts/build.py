"""Build the static profile.svg (snapshot + fallback). The live, per-access version is api/profile.py.

    python scripts/build.py                     # placeholder telemetry
    GITHUB_TOKEN=... python scripts/build.py    # with GitHub stats
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from profilekit.render import load_config, render  # noqa: E402
from profilekit.telemetry import collect  # noqa: E402

if __name__ == "__main__":
    cfg = load_config()
    svg = render(cfg, collect(cfg, live=False))
    with open(os.path.join(ROOT, "profile.svg"), "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"profile.svg written ({len(svg) / 1024:.0f} KB)")
