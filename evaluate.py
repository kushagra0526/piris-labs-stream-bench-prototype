"""Score benchmark protocols on simulated providers with known truth.

python evaluate.py dev       # seeds 0..99 (used while building)
python evaluate.py heldout   # seeds in heldout/seeds.json (frozen in git before the first run)

Per world: 3 providers whose true median decode speeds sit within about +-20% of each other, with different
volatility, stalls, chunk coalescing and shared-load drift. Output length 512 (the playground default).
"""
import json
import random
import sys

from streambench.protocol import run_virtual
from streambench.sim import Profile, truth
from streambench.stats import median, winner

OUT = 512
CTXS = (10_000, 100_000)


def world(seed):
    rng = random.Random(seed)
    base = rng.uniform(200, 450)
    ps = []
    for i in range(3):
        ps.append(Profile(
            name="ABC"[i], decode=base * rng.uniform(0.8, 1.2), prefill=rng.uniform(8000, 40000),
            rtt=rng.uniform(0.03, 0.25), req_sigma=rng.uniform(0.04, 0.35), tok_sigma=rng.uniform(0.15, 0.4),
            stall_p=rng.choice([0, 0, 0.002, 0.01]), stall_s=rng.uniform(0.05, 0.4),
            chunk=rng.choice([1, 1, 2, 4, 8, 16]), load_amp=rng.choice([0, 0, 0.2, 0.5]),
            phase=rng.uniform(0, 6.283)))
    return ps


def true_top(tr, key):
    """Names within 3% of the best true median (any of them counts as a right answer)."""
    best = max(v[key] for v in tr.values())
    return {k for k, v in tr.items() if v[key] >= 0.97 * best}


def run(seeds):
    from multiprocessing import Pool
    with Pool() as pool:
        parts = pool.map(run_one, seeds)
    agg = parts[0]
    for p in parts[1:]:
        for k, v in p.items():
            if k in ("peak5", "median5", "harness"):          # counters: add element-wise
                agg[k] = [x + y for x, y in zip(agg[k], v)]
            elif isinstance(v, dict):                          # lists of per-provider values
                for kk in v:
                    agg[k][kk] += v[kk]
            else:                                              # ints and lists
                agg[k] += v
    return agg


def run_one(seed):
    agg = {"worlds": 0, "peak5": [0, 0], "median5": [0, 0], "harness": [0, 0, 0],
           "over": {"peak5": [], "peak30": [], "median5": [], "harness30": []},
           "naive_err": [], "harness_err": [], "e2e_flip": 0, "ttft100": [], "e2e_vs_decode100": []}
    if True:  # one world (kept indented as before)
        ps = world(seed)
        tr = {c: {p.name: truth(p, c, OUT, n=600, seed=seed * 7 + c) for p in ps} for c in CTXS}
        rng = random.Random(seed + 1)
        quick = run_virtual(ps, CTXS[0], OUT, 5, rng, sessions=1)
        full = run_virtual(ps, CTXS[0], OUT, 30, rng, sessions=3)
        top = true_top(tr[CTXS[0]], "decode")
        agg["worlds"] += 1

        def score(key, name):
            agg[key][0] += name not in top
            agg[key][1] += 1
        score("peak5", max(quick, key=lambda k: max(m["decode"] for m in quick[k])))
        score("median5", max(quick, key=lambda k: median([m["decode"] for m in quick[k]])))
        w, _ = winner({k: [m["decode"] for m in v] for k, v in full.items()}, boots=600)
        agg["harness"][0] += w is not None and w not in top
        agg["harness"][1] += w is None
        agg["harness"][2] += 1

        for p in ps:
            t = tr[CTXS[0]][p.name]["decode"]
            q = [m["decode"] for m in quick[p.name]]
            f = [m["decode"] for m in full[p.name]]
            agg["over"]["peak5"].append(max(q) / t - 1)
            agg["over"]["median5"].append(median(q) / t - 1)
            agg["over"]["peak30"].append(max(f) / t - 1)
            agg["over"]["harness30"].append(median(f) / t - 1)
            if p.chunk > 1:
                agg["naive_err"].append(median([m["naive"] for m in full[p.name]]) / t - 1)
                agg["harness_err"].append(median(f) / t - 1)
            t100 = tr[CTXS[1]][p.name]
            agg["ttft100"].append(t100["ttft"])
            agg["e2e_vs_decode100"].append(t100["e2e"] / t100["decode"] - 1)
        d100 = max(tr[CTXS[1]], key=lambda k: tr[CTXS[1]][k]["decode"])
        agg["e2e_flip"] += d100 not in true_top(tr[CTXS[1]], "e2e")
    return agg


def report(a):
    n = a["worlds"]
    mean = lambda xs: sum(xs) / len(xs)
    r = {
        "worlds": n,
        "wrong_winner": {"peak_of_5": a["peak5"][0], "median_of_5": a["median5"][0],
                         "harness_30_runs_3_sessions": a["harness"][0]},
        "harness_says_tie": a["harness"][1],
        "overstatement_vs_true_median_pct": {k: round(100 * mean(v), 1) for k, v in a["over"].items()},
        "peak5_overstates_by_more_than_15pct_share": round(sum(x > .15 for x in a["over"]["peak5"]) / len(a["over"]["peak5"]), 3),
        "coalesced_endpoints": len(a["naive_err"]),
        "count_events_as_tokens_error_pct": round(100 * median(a["naive_err"]), 1),
        "harness_error_on_coalesced_pct": round(100 * median(a["harness_err"]), 1),
        "ttft_at_100k_median_s": round(median(a["ttft100"]), 2),
        "e2e_below_decode_at_100k_median_pct": round(-100 * median(a["e2e_vs_decode100"]), 1),
        "fastest_decode_not_fastest_for_user_at_100k": a["e2e_flip"],
    }
    return r


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "dev"
    seeds = list(range(100)) if split == "dev" else json.load(open("heldout/seeds.json"))["seeds"]
    res = report(run(seeds))
    print(json.dumps(res, indent=2))
    json.dump(res, open(f"out/{split}.json", "w"), indent=2)
