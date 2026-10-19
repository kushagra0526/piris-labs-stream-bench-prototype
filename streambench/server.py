"""Local OpenAI-compatible streaming server backed by sim profiles (for demos and tests; no real model).

POST /<profile>/v1/chat/completions  {"messages": [...], "max_tokens": N, "stream": true}
Context length = prompt characters / 4. `scale` speeds the clock up (sleeps divided by scale).
"""
import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .sim import request


def make_server(profiles, port=0, scale=1.0, seed=0):
    by_name = {p.name: p for p in profiles}
    rng = random.Random(seed)
    lock = threading.Lock()
    t_start = time.time()

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_POST(self):
            t_recv = time.perf_counter()
            name = self.path.strip("/").split("/")[0]
            p = by_name.get(name)
            if p is None or not self.path.endswith("/v1/chat/completions"):
                self.send_error(404)
                return
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            ctx = sum(len(m.get("content", "")) for m in body.get("messages", [])) // 4
            out = int(body.get("max_tokens", 256))
            with lock:
                sub = random.Random(rng.random())
            _, events, _ = request(p, ctx, out, (time.time() - t_start) * scale, sub)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            def send(obj):
                data = ("data: " + (obj if isinstance(obj, str) else json.dumps(obj)) + "\n\n").encode()
                self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                self.wfile.flush()

            for t, text in events:
                wait = t_recv + t / scale - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
                send({"choices": [{"index": 0, "delta": {"content": text}}]})
            send({"choices": [], "usage": {"prompt_tokens": ctx, "completion_tokens": out}})
            send("[DONE]")
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
