"""Simulated streaming endpoints with known truth.

One generator (`request`) drives both the virtual-clock evaluation and the real HTTP server, so what the
harness measures over HTTP is the same process the evaluation scores.
"""
import math
import random
from dataclasses import dataclass


@dataclass
class Profile:
    name: str
    decode: float              # median decode tokens/s at zero load
    prefill: float             # input tokens/s
    rtt: float = 0.05          # network + scheduling floor (s)
    req_sigma: float = 0.08    # per-request lognormal spread of decode speed (batch mix, placement)
    tok_sigma: float = 0.25    # per-token inter-token-latency jitter
    stall_p: float = 0.0       # per-token chance of a stall (preemption, KV swap)
    stall_s: float = 0.0
    chunk: int = 1             # tokens per SSE event (server/proxy coalescing)
    load_amp: float = 0.0      # shared capacity: slowdown at peak load (0 = dedicated)
    load_period: float = 86400.0   # daily load cycle
    phase: float = 0.0

    def load(self, t):
        return self.load_amp * (0.5 + 0.5 * math.sin(2 * math.pi * t / self.load_period + self.phase))


def token_text(rng):
    # BPE-ish piece lengths: mostly 2-6 chars, sometimes 1 or long
    return "x" * max(1, min(12, int(rng.lognormvariate(1.25, 0.45))))


def request(p, ctx, out, t0, rng):
    """One streamed request sent at wall time t0.

    Returns (token_times, events, texts): token_times are seconds after send for every output token;
    events are (seconds after send, text) as the client would see them (coalesced into p.chunk tokens).
    """
    slow = 1 + p.load(t0)
    queue = rng.expovariate(1 / (0.4 * (slow - 1))) if slow > 1 else 0.0
    ttft = p.rtt + queue + ctx / p.prefill * slow * rng.lognormvariate(0, 0.05)
    rate = p.decode / slow * rng.lognormvariate(0, p.req_sigma)
    s = p.tok_sigma
    mu = -math.log(rate) - s * s / 2           # mean inter-token gap = 1/rate
    times, t = [ttft], ttft
    for _ in range(out - 1):
        t += rng.lognormvariate(mu, s)
        if p.stall_p and rng.random() < p.stall_p:
            t += p.stall_s
        times.append(t)
    texts = [token_text(rng) for _ in range(out)]
    events = [(times[min(i + p.chunk, out) - 1], "".join(texts[i:i + p.chunk])) for i in range(0, out, p.chunk)]
    return times, events, texts


def true_decode(times):
    return (len(times) - 1) / (times[-1] - times[0])


def truth(p, ctx, out, n=3000, seed=0):
    """Population medians over requests sent uniformly across the load cycle (the 'typical' user)."""
    rng = random.Random(seed)
    dec, ttft, e2e = [], [], []
    for _ in range(n):
        times, _, _ = request(p, ctx, out, rng.uniform(0, p.load_period), rng)
        dec.append(true_decode(times))
        ttft.append(times[0])
        e2e.append(out / times[-1])
    med = lambda xs: sorted(xs)[len(xs) // 2]
    return {"decode": med(dec), "ttft": med(ttft), "e2e": med(e2e)}
