import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streambench.client import stream_once
from streambench.metrics import measure, naive_event_rate
from streambench.protocol import schedule
from streambench.server import make_server
from streambench.sim import Profile, request, true_decode
from streambench.stats import compare, median, winner


def test_compare_detects_difference_and_ties():
    rng = random.Random(0)
    a = [rng.gauss(300, 20) for _ in range(30)]
    b = [rng.gauss(250, 20) for _ in range(30)]
    c = [rng.gauss(300, 20) for _ in range(30)]
    assert compare(a, b) == 1 and compare(b, a) == -1
    assert compare(a, c) == 0
    assert winner({"a": a, "b": b})[0] == "a"
    assert winner({"a": a, "c": c})[0] is None


def test_coalesced_stream_measured_from_usage_not_events():
    p = Profile("x", decode=300, prefill=20000, chunk=8)
    rng = random.Random(1)
    errs, naive = [], []
    for _ in range(50):
        times, events, _ = request(p, 2000, 512, 0, rng)
        t = true_decode(times)
        errs.append(measure(events, 512, times[-1])["decode"] / t - 1)
        naive.append(naive_event_rate(events) / t - 1)
    assert abs(median(errs)) < 0.03
    assert median(naive) < -0.8     # 8 tokens per event -> ~1/8 of the speed


def test_peak_of_n_rises_with_n_on_volatile_endpoint():
    p = Profile("v", decode=300, prefill=20000, req_sigma=0.3)
    rng = random.Random(2)
    d = [true_decode(request(p, 1000, 256, 0, rng)[0]) for _ in range(200)]
    assert max(d[:5]) < max(d) and max(d[:5]) > median(d)


def test_schedule_interleaves_and_splits_sessions():
    s = schedule(["a", "b"], 5, 2)
    assert s == [["a", "b"] * 3, ["a", "b"] * 2]


def test_http_matches_virtual_clock():
    p = Profile("p", decode=200, prefill=40000, rtt=0.02, req_sigma=0.0, tok_sigma=0.01, chunk=2)
    srv = make_server([p], scale=1.0, seed=0)
    try:
        url = f"http://127.0.0.1:{srv.server_port}/p/v1/chat/completions"
        events, usage, t_end = stream_once(url, "sim", "a" * 8000, 40)
        m = measure(events, usage, t_end)
        assert usage == 40 and len(events) == 20
        assert abs(m["ttft"] - (0.02 + 2000 / 40000)) < 0.03
        assert abs(m["decode"] / 200 - 1) < 0.1
    finally:
        srv.shutdown()


def test_missing_usage_is_an_error():
    import http.server, threading

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n')

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        stream_once(f"http://127.0.0.1:{srv.server_port}/v1/chat/completions", "m", "x", 5)
        assert False, "should have raised"
    except RuntimeError as e:
        assert "usage" in str(e)
    finally:
        srv.shutdown()
