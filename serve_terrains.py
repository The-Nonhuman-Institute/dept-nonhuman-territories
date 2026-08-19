"""Serve both terrain viewers locally, with caching turned off.

A browser will happily hold on to a cached index.html while still fetching a
fresh world.json, which produces the worst possible failure: a stale page
showing live data. That is how BASIN-02's viewer spent an evening displaying
BASIN-01's name over BASIN-02's numbers. No-store removes the possibility.

Loopback only. Nothing is exposed beyond this machine.

    python3 serve_terrains.py
"""
import functools, http.server, os, socketserver, threading

ROOT = os.path.dirname(os.path.abspath(__file__))
# The hub is served from the project root so it can reach both codices and the
# governance documents; each observation deck is served from its own viewer
# directory so a terrain can only ever serve its own files.
TERRAINS = (("HUB",      8730, "."),
            ("BASIN-01", 8731, "basin-01/viewer"),
            ("BASIN-02", 8732, "basin-02/viewer"),
            ("BASIN-03", 8733, "basin-03/viewer"),
            ("BASIN-04", 8734, "basin-04/viewer"))


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        http.server.SimpleHTTPRequestHandler.end_headers(self)

    def log_message(self, fmt, *args):
        return


class ThreadedServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    servers = []
    for name, port, path in TERRAINS:
        directory = os.path.join(ROOT, path)
        if not os.path.isdir(directory):
            print("  %s: no viewer at %s — skipped" % (name, path))
            continue
        handler = functools.partial(NoCache, directory=directory)
        # Threaded, one request at a time per thread. A single-threaded server
        # serves one connection at a time, and a browser opening a page that
        # pulls several files at once — or a client that holds a connection
        # open — stalls every later request behind it. The hub now serves
        # thousands of pages; it hung on exactly that.
        socketserver.TCPServer.allow_reuse_address = True
        server = ThreadedServer(("127.0.0.1", port), handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        page = "hub.html" if name == "HUB" else "index.html"
        print("  %-9s http://127.0.0.1:%d/%s" % (name, port, page))
    if not servers:
        return 1
    print("\nvisible only on this machine. Ctrl+C to stop.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nclosed.")
    finally:
        for s in servers:
            s.shutdown(); s.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
