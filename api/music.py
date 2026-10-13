"""Live music card for the README, served by Vercel at /api/music."""
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cards"))
import render  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body, ttl = render.live_music(os.environ.get("LASTFM_API_KEY"))
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        # browsers and GitHub's image proxy always revalidate; Vercel's CDN
        # holds it briefly so a burst of profile views is one Last.fm lookup
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.send_header("Vercel-CDN-Cache-Control", f"max-age={ttl}, stale-while-revalidate=60")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
