#!/usr/bin/env python3
"""Serve QA Portal UI build with SPA fallback for /runs, /ui-flows, /callback, etc."""

from __future__ import annotations

import argparse
import http.server
import socketserver
from pathlib import Path


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class SPARequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        if self.path.split("?", 1)[0].endswith((".js", ".html", ".wasm")):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        if self.path.split("?", 1)[0].endswith(".js"):
            self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def send_head(self):
        requested = self.path.split("?", 1)[0]
        file_path = Path(self.translate_path(requested))
        if not file_path.is_file():
            self.path = "/index.html"
        return super().send_head()

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def log_error(self, format, *args):
        if args and isinstance(args[-1], OSError):
            err = args[-1]
            if getattr(err, "winerror", None) in (10053, 10054):
                return
        if args and args[-1] in ("Broken pipe", "Connection reset by peer"):
            return
        super().log_error(format, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve QA Portal UI web build with SPA routing")
    parser.add_argument("--port", type=int, default=8151)
    parser.add_argument("--directory", default="build/web")
    args = parser.parse_args()

    web_dir = Path(__file__).resolve().parent / args.directory
    if not (web_dir / "index.html").is_file():
        raise SystemExit(f"Build output missing: {web_dir / 'index.html'}. Run 'flutter build web' first.")

    handler = lambda *h_args, **h_kwargs: SPARequestHandler(
        *h_args, directory=str(web_dir), **h_kwargs
    )
    with ThreadingHTTPServer(("0.0.0.0", args.port), handler) as httpd:
        print(f"[QA Portal] Serving at http://localhost:{args.port}/ (SPA routing enabled)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")


if __name__ == "__main__":
    main()
