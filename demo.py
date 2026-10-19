"""Three simulated GLM-style endpoints with known truth (virtual clock, ~5 s).

A quick test (5 runs, one sitting, report the peak) vs the protocol (30 runs over 3 sessions, median + CI).
python demo.py
"""
import random

from bench import demo_profiles
from streambench.protocol import run_virtual
from streambench.sim import truth
from streambench.stats import median, median_ci, winner

OUT = 512
ps = demo_profiles()
tr = {c: {p.name: truth(p, c, OUT, n=1500, seed=1) for p in ps} for c in (10_000, 100_000)}

print("TRUTH (median over a whole day of requests), 10k context:")
for p in ps:
    print(f"  {p.name:<9} decode {tr[10_000][p.name]['decode']:5.0f} tok/s")

rng = random.Random(3)
quick = run_virtual(ps, 10_000, OUT, 5, rng, sessions=1)
print("\nQUICK TEST: 5 runs each, one sitting, headline = peak")
for k, v in quick.items():
    d = [m["decode"] for m in v]
    print(f"  {k:<9} peak {max(d):5.0f}   median {median(d):5.0f}   counting SSE events: {median([m['naive'] for m in v]):5.0f}")
print(f"  -> crowns '{max(quick, key=lambda k: max(m['decode'] for m in quick[k]))}'")

full = run_virtual(ps, 10_000, OUT, 30, rng, sessions=3)
print("\nPROTOCOL: 30 runs each, 3 sessions across the day, tokens from usage, median [95% CI]")
for k, v in full.items():
    d = [m["decode"] for m in v]
    lo, hi = median_ci(d)
    print(f"  {k:<9} {median(d):5.0f} [{lo:.0f}-{hi:.0f}]   peak {max(d):.0f}")
w, tied = winner({k: [m["decode"] for m in v] for k, v in full.items()})
print(f"  -> {w + ' is faster than both (95%)' if w else 'tie: ' + ', '.join(tied)}"
      f"   (ranking these same 30 runs by peak would crown '{max(full, key=lambda k: max(m['decode'] for m in full[k]))}')")

print("\nAT 100k CONTEXT (truth): decode speed vs what the user waits for")
for p in ps:
    t = tr[100_000][p.name]
    print(f"  {p.name:<9} TTFT {t['ttft']:4.1f} s   decode {t['decode']:4.0f} tok/s   end-to-end {t['e2e']:4.0f} tok/s")
