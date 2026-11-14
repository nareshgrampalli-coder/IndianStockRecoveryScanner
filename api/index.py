"""Vercel adapter for the browser-uploaded Screener tables."""

import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from dashboard import (
    build_copied_screens_payload,
    build_provisional_payload,
)
from data_processing.provisional_ranking import (
    STRATEGY_SOURCES,
    build_provisional_ranking,
    read_copied_screener_screens,
)

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        route = parse_qs(parsed.query).get("path", [parsed.path])[0]
        pages = {
            "/": "upload.html",
            "/upload": "upload.html",
            "/provisional-ranking": "provisional.html",
            "/copied-screens": "copied-screens.html",
            "/app.js": "app.js",
            "/styles.css": "styles.css",
        }
        if route.startswith("/api/"):
            self._send_json({"error": "Upload the Screener files before requesting data."}, 400)
        elif route in pages:
            path = WEB_ROOT / pages[route]
            if not path.is_file():
                self.send_error(404)
                return
            content_type = "text/javascript" if path.suffix == ".js" else (
                "text/css" if path.suffix == ".css" else "text/html; charset=utf-8"
            )
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(path.stat().st_size))
            self.end_headers()
            self.wfile.write(path.read_bytes())
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        route = parse_qs(parsed.query).get("path", [parsed.path])[0]
        if route not in {"/api/copied-screens", "/api/provisional-ranking"}:
            self._send_json({"error": "Not found."}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4_000_000:
                raise ValueError("Request must contain uploaded files and be under 4 MB.")
            payload = json.loads(self.rfile.read(length))
            uploaded = payload.get("files", {})
            if not isinstance(uploaded, dict):
                raise ValueError("Uploaded files must be provided as a file map.")
            with TemporaryDirectory() as temporary:
                root = Path(temporary)
                input_dir = root / "inputs"
                result_dir = root / "results"
                input_dir.mkdir()
                result_dir.mkdir()
                for input_name, _ in STRATEGY_SOURCES.values():
                    item = uploaded.get(input_name, {})
                    content = item.get("content", "") if isinstance(item, dict) else ""
                    (input_dir / input_name).write_text(
                        content if content.strip() else "Company,Market Cap Rs Cr\n",
                        encoding="utf-8-sig",
                    )
                if route == "/api/copied-screens":
                    screens = read_copied_screener_screens(input_dir, result_dir)
                    for screen in screens:
                        item = uploaded.get(
                            STRATEGY_SOURCES[screen["strategy"]][0], {}
                        )
                        if isinstance(item, dict) and item.get("name"):
                            screen["source_file"] = item["name"]
                    result = build_copied_screens_payload(screens)
                else:
                    frame = build_provisional_ranking(
                        input_dir, result_dir, root / "provisional-ranking.csv"
                    )
                    source_names = {
                        input_name: uploaded[input_name]["name"]
                        for input_name, _ in STRATEGY_SOURCES.values()
                        if isinstance(uploaded.get(input_name), dict)
                        and uploaded[input_name].get("name")
                    }
                    if source_names:
                        frame["source_files"] = frame["source_files"].map(
                            lambda value: ";".join(
                                source_names.get(name, name)
                                for name in str(value).split(";")
                            )
                        )
                    result = build_provisional_payload(frame)
            self._send_json(result, 200)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, 400)

    def _send_json(self, payload, status):
        content = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)
