"""Run the protocol over real HTTP and write a benchmark card.

python bench.py --sim                       # local simulated endpoints (clock sped up 10x), no network
python bench.py --endpoint mine=https://host/v1/chat/completions,model-id --endpoint other=...,model-id
                                            # your own endpoints; key from STREAMBENCH_API_KEY
Only point this at endpoints you are allowed to benchmark.
"""
import argparse
import json

from streambench.card import card
from streambench.protocol import run_http


def demo_profiles():
    from streambench.sim import Profile
    return [
        Profile("steady", decode=320, prefill=30000, rtt=0.06, req_sigma=0.05, tok_sigma=0.2),
        Profile("volatile", decode=300, prefill=36000, rtt=0.08, req_sigma=0.30, tok_sigma=0.35,
                stall_p=0.004, stall_s=0.2, load_amp=0.35, phase=1.0),
        Profile("chunky", decode=290, prefill=14000, rtt=0.05, req_sigma=0.08, chunk=16),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--endpoint", action="append", default=[], help="name=url,model")
    ap.add_argument("--ctx", type=int, nargs="+", default=[10_000, 100_000])
    ap.add_argument("--out", type=int, default=512)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--sessions", type=int, default=1)
    a = ap.parse_args()

    scale = 1.0
    if a.sim:
        from streambench.server import make_server
        scale = 10.0
        srv = make_server(demo_profiles(), scale=scale, seed=7)
        eps = {p.name: (f"http://127.0.0.1:{srv.server_port}/{p.name}/v1/chat/completions", "sim", None)
               for p in demo_profiles()}
    else:
        eps = {}
        for e in a.endpoint:
            name, rest = e.split("=", 1)
            url, model = rest.rsplit(",", 1)
            eps[name] = (url, model, None)
    if not eps:
        ap.error("give --sim or at least one --endpoint")

    by_ctx, runs = {}, []
    for ctx in a.ctx:
        prompt = ("Summarise the following log. " + "lorem ipsum dolor sit amet " * (ctx * 4 // 27))[: ctx * 4]
        print(f"context {ctx:,} tokens")
        res = run_http(eps, prompt, a.out, a.n, sessions=a.sessions,
                       log=print if scale == 1 else (lambda *_: None))  # sim clock: print after converting
        for k, ms in res.items():
            for m in ms:   # undo the sim clock speed-up so numbers read in real seconds
                m["ttft"] *= scale
                m["decode"] = m["decode"] / scale if m["decode"] else None
                m["e2e"] /= scale
                m["naive"] = m["naive"] / scale if m["naive"] else None
                runs.append({"ctx": ctx, "endpoint": k, **m})
        by_ctx[ctx] = res
    proto = {"Output length": f"{a.out} tokens (max_tokens), temperature 0",
             "Runs": f"{a.n} per endpoint per context, round-robin interleaved, 1 warm-up each",
             "Sessions": f"{a.sessions}" + (" (run more at other times of day and merge runs.jsonl)" if a.sessions == 1 else ""),
             "Token count": "usage.completion_tokens (stream_options.include_usage)",
             "Client": "Python http.client, timestamps at SSE event receipt",
             "Endpoints": ", ".join(f"{k} ({v[1]})" for k, v in eps.items())}
    if a.sim:
        proto["Note"] = "simulated local endpoints, clock sped up 10x and converted back"
    open("out/card.md", "w", encoding="utf-8").write(card(by_ctx, proto))
    with open("out/runs.jsonl", "w") as f:
        for r in runs:
            f.write(json.dumps(r) + "\n")
    print("wrote out/card.md and out/runs.jsonl")


if __name__ == "__main__":
    main()
