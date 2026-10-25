"""Main Launcher for Shanto Download Manager (SDM).
Starts API Server, WebSocket Telemetry, Clipboard Sniffer, and Opens Dashboard.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path
import uvicorn

# Ensure sdm directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

from sdm.api.server import app, manager
from sdm.core.clipboard import ClipboardWatcher


def on_clipboard_url(url: str) -> None:
    print(f"\n[SDM Clipboard Sniffer] Detected downloadable link: {url}")
    # Run async add_task in manager's loop if desired, or queue it
    # We can automatically add or log
    pass


def main():
    parser = argparse.ArgumentParser(description="Shanto Download Manager (SDM) Turbo Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=48912, help="Port (default: 48912)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser dashboard")
    parser.add_argument("--no-clipboard", action="store_true", help="Disable clipboard URL sniffer")
    args = parser.parse_args()

    print("=" * 65)
    print("  SHANTO DOWNLOAD MANAGER (SDM) — REVERSE-ENGINEERED TURBO CORE")
    print("=" * 65)
    print(f"  • Dashboard URL:  http://{args.host}:{args.port}")
    print(f"  • API Endpoint:   http://{args.host}:{args.port}/api")
    print(f"  • WebSocket Telemetry: ws://{args.host}:{args.port}/ws")
    print(f"  • Downloads Dir:  {manager.downloads_dir}")
    print(f"  • Dynamic Slices: 8-32 connections with dynamic tail-splitting")
    print("=" * 65)

    # Start clipboard sniffer daemon
    if not args.no_clipboard:
        watcher = ClipboardWatcher(on_url_detected=on_clipboard_url)
        watcher.start()
        print("[SDM] Clipboard URL Sniffer active")

    # Auto-open browser dashboard
    if not args.no_browser:
        def _open():
            time.sleep(1.2)
            webbrowser.open(f"http://{args.host}:{args.port}")
        threading.Thread(target=_open, daemon=True).start()

    # Run Uvicorn server
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
