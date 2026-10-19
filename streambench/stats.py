"""Summaries and comparisons that survive a sceptical reader: median + bootstrap CI, ties allowed."""
import random


def quantile(xs, q):
    s = sorted(xs)
    if not s:
        return None
    k = (len(s) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def median(xs):
    return quantile(xs, 0.5)


def summary(xs):
    return {"n": len(xs), "median": median(xs), "p10": quantile(xs, 0.1), "p90": quantile(xs, 0.9),
            "peak": max(xs), "min": min(xs)}


def boot_medians(xs, rng, b):
    n = len(xs)
    return [median([xs[rng.randrange(n)] for _ in range(n)]) for _ in range(b)]


def median_ci(xs, b=1000, level=0.95, seed=0):
    m = boot_medians(xs, random.Random(seed), b)
    a = (1 - level) / 2
    return quantile(m, a), quantile(m, 1 - a)


def compare(a, b, boots=1000, level=0.95, seed=0):
    """+1 if a's median is higher with `level` confidence, -1 if lower, 0 = can't tell (tie)."""
    rng = random.Random(seed)
    d = [x - y for x, y in zip(boot_medians(a, rng, boots), boot_medians(b, rng, boots))]
    lo, hi = quantile(d, (1 - level) / 2), quantile(d, 1 - (1 - level) / 2)
    return 1 if lo > 0 else -1 if hi < 0 else 0


def winner(samples, boots=1000, level=0.95, seed=0):
    """samples: {name: [values]} (higher is better). Returns (name, beaten-by-all-others?) or (None, tied names).

    A winner must beat every other endpoint with confidence; otherwise report who it is tied with.
    level is per comparison (Bonferroni over the k-1 comparisons for the leader).
    """
    names = sorted(samples, key=lambda k: -median(samples[k]))
    lead = names[0]
    lvl = 1 - (1 - level) / max(1, len(names) - 1)
    tied = [k for k in names[1:] if compare(samples[lead], samples[k], boots, lvl, seed) <= 0]
    return (lead, []) if not tied else (None, [lead] + tied)
