"""The benchmark protocol: interleaved round-robin, several sessions spread over the day, fixed output length.

`run_virtual` runs it on sim profiles with a virtual clock (fast, used by evaluate.py).
`run_http` runs the same protocol against real endpoints through client.stream_once.
"""
from .metrics import measure, naive_event_rate
from .sim import request, true_decode


def schedule(names, n, sessions):
    """Round-robin order split into sessions: [[name, ...] per session]."""
    per = [n // sessions + (1 if s < n % sessions else 0) for s in range(sessions)]
    return [[k for _ in range(m) for k in names] for m in per]


def run_virtual(profiles, ctx, out, n, rng, sessions=3, day=86400.0, gap=1.0, start=None):
    by = {p.name: p for p in profiles}
    res = {p.name: [] for p in profiles}
    t0 = rng.uniform(0, day) if start is None else start
    for s, block in enumerate(schedule(list(by), n, sessions)):
        t = t0 + s * day / sessions
        for name in block:
            times, events, _ = request(by[name], ctx, out, t, rng)
            m = measure(events, out, times[-1])
            m["naive"] = naive_event_rate(events)
            m["true_decode"] = true_decode(times)
            res[name].append(m)
            t += times[-1] + gap
    return res


def run_http(endpoints, prompt, out, n, sessions=1, warmup=1, stream=None, log=print):
    """endpoints: {name: (url, model, api_key_or_None)}. Sessions run back to back here; for a real
    benchmark schedule them at different times of day (cron) and merge the JSONL."""
    from .client import stream_once
    stream = stream or stream_once
    res = {k: [] for k in endpoints}
    for k, (url, model, key) in endpoints.items():
        for _ in range(warmup):
            stream(url, model, prompt, out, key)
    for block in schedule(list(endpoints), n, sessions):
        for k in block:
            url, model, key = endpoints[k]
            events, usage, t_end = stream(url, model, prompt, out, key)
            m = measure(events, usage, t_end)
            m["naive"] = naive_event_rate(events)
            res[k].append(m)
            log(f"  {k:<14} ttft {m['ttft']:.2f}s  decode {m['decode']:.0f} tok/s  e2e {m['e2e']:.0f} tok/s")
    return res
