#!/usr/bin/env python
"""Serve local stock-screen and final-results dashboards."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
STRATEGIES = {
    "strategy_1_quality": "Strategy 1 · Quality",
    "strategy_2_deep_value": "Strategy 2 · Deep value",
    "strategy_3_primary": "Strategy 3 · Primary",
    "strategy_4_entry_timing": "Strategy 4 · Entry timing",
}


def truthy(value) -> bool:
    return value is True or str(value).strip().lower() in {"true", "1", "yes"}


def json_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def stock_records(frame: pd.DataFrame) -> list[dict]:
    records = []
    for row in frame.to_dict(orient="records"):
        record = {key: json_value(value) for key, value in row.items()}
        record["name"] = record.get("name") or record.get("nifty_name") or ""
        for field in STRATEGIES:
            record[field] = truthy(record.get(field))
        records.append(record)
    return sorted(
        records,
        key=lambda item: (
            item.get("rank") is None,
            item.get("rank") if item.get("rank") is not None else float("inf"),
        ),
    )


def build_dashboard_payload(frame: pd.DataFrame) -> dict:
    records = stock_records(frame)
    primary = [row for row in records if row["strategy_3_primary"]]
    quality = [row for row in primary if row["strategy_1_quality"]]
    entry_timing = [row for row in quality if row["strategy_4_entry_timing"]]
    counts = {
        "universe": len(records),
        "strategy_1_quality": sum(row["strategy_1_quality"] for row in records),
        "strategy_2_deep_value": sum(row["strategy_2_deep_value"] for row in records),
        "strategy_3_primary": len(primary),
        "after_quality_filter": len(quality),
        "after_entry_timing_filter": len(entry_timing),
        "final_ranking": len(records),
        "multi_screen": sum(
            (row.get("strategy_membership_count") or 0) > 1 for row in records
        ),
    }
    return {
        "counts": counts,
        "primary_candidates": primary,
        "quality_candidates": quality,
        "final_candidates": records,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    workbook_path = ROOT / "screening_results.xlsx"

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/screens":
            self._send_data("screens")
        elif route == "/api/dashboard":
            self._send_data("dashboard")
        elif route in {"/", "/screens"}:
            self._send_file(WEB_ROOT / "index.html")
        elif route == "/dashboard":
            self._send_file(WEB_ROOT / "dashboard.html")
        elif route in {"/app.js", "/styles.css"}:
            self._send_file(WEB_ROOT / route.lstrip("/"))
        else:
            self.send_error(404)

    def _send_data(self, view: str):
        try:
            if not self.workbook_path.is_file():
                raise FileNotFoundError(
                    f"{self.workbook_path} was not found. Run app.py first to generate the ranked workbook."
                )
            try:
                frame = pd.read_excel(self.workbook_path, sheet_name="Final_Ranking")
            except ValueError:
                frame = pd.read_excel(self.workbook_path, sheet_name="Ranked Watchlist")
            records = stock_records(frame)
            payload = (
                {"stocks": records}
                if view == "screens" else build_dashboard_payload(frame)
            )
            self._send_json(payload)
        except (OSError, ValueError, KeyError) as exc:
            self._send_json({"error": str(exc)}, status=503)

    def _send_json(self, payload: dict, status: int = 200):
        content = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _send_file(self, path: Path):
        if not path.is_file():
            self.send_error(404)
            return
        content = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", default="screening_results.xlsx")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    DashboardHandler.workbook_path = Path(args.workbook).resolve()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Stock screens: http://{args.host}:{args.port}/")
    print(f"Final dashboard: http://{args.host}:{args.port}/dashboard")
    print(f"Workbook: {DashboardHandler.workbook_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
