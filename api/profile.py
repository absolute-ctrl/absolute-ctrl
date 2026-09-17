"""Live profile endpoint (Vercel Python function).

Every GitHub profile view makes GitHub's image proxy (camo) request this URL. The no-cache headers
below stop camo from reusing an old copy, so each access increments the counter and re-pulls stats.

    GET /api/profile            render + count this access
    GET /api/profile?nocount=1  render without counting (for your own testing)
"""
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from profilekit.render import load_config, render  # noqa: E402
from profilekit.telemetry import collect  # noqa: E402

HEADERS = {
    "Content-Type": "image/svg+xml; charset=utf-8",
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0, s-maxage=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Content-Type-Options": "nosniff",
}


def build(count):
    cfg = load_config(os.path.join(ROOT, "profile.json"))
    try:
        tel = collect(cfg, live=True, count=count)
    except Exception:
        traceback.print_exc()
        tel = {"mode": "live", "accesses": None, "previous_access": None, "github": None}
    return render(cfg, tel).encode("utf-8")


class handler(BaseHTTPRequestHandler):
    def _send(self, body, head_only=False):
        self.send_response(200)
        for k, v in HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        count = q.get("nocount", ["0"])[0] not in ("1", "true", "yes")
        try:
            body = build(count)
        except Exception:
            traceback.print_exc()
            body = (b'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="60"><rect width="880" height="60" '
                    b'fill="#0A0F0A"/><text x="20" y="36" fill="#FFB000" font-family="monospace" font-size="16">'
                    b'SIGNAL LOST: renderer error, check Vercel logs</text></svg>')
        self._send(body)

    def do_HEAD(self):
        self._send(b"", head_only=True)
