"""Benchmark card: every protocol field a reader needs to re-run it, and medians with CIs as the headline."""
from .stats import median, median_ci, quantile, winner


def _row(name, ms):
    ttft = [m["ttft"] for m in ms]
    dec = [m["decode"] for m in ms if m["decode"]]
    e2e = [m["e2e"] for m in ms]
    lo, hi = median_ci(dec)
    return (f"| {name} | {median(ttft):.2f} s ({quantile(ttft, .9):.2f}) | **{median(dec):.0f}** [{lo:.0f}–{hi:.0f}] "
            f"({quantile(dec, .1):.0f}–{quantile(dec, .9):.0f}) | {median(e2e):.0f} | {max(dec):.0f} |")


def _verdict(res, key):
    w, tied = winner({k: [m[key] for m in v if m[key]] for k, v in res.items()})
    return f"**{w}** is faster than every other endpoint (95% confidence)" if w else "tie between " + ", ".join(tied)


def card(by_ctx, protocol):
    lines = ["# Streaming benchmark card", "", "## Protocol"]
    lines += [f"- **{k}:** {v}" for k, v in protocol.items()]
    for ctx, res in by_ctx.items():
        lines += ["", f"## Input context {ctx:,} tokens", "",
                  "| Endpoint | TTFT median (p90) | Decode tok/s median [95% CI] (p10–p90) | End-to-end tok/s | Peak decode (not a headline) |",
                  "|---|---|---|---|---|"]
        lines += [_row(k, v) for k, v in res.items()]
        lines += ["", f"- Decode speed: {_verdict(res, 'decode')}.",
                  f"- What a user waits for (end-to-end, including TTFT): {_verdict(res, 'e2e')}."]
    lines += ["", "Decode = tokens after the first event / time from first to last event. End-to-end = all output "
              "tokens / time from send to last token. Tokens come from `usage.completion_tokens`, never from counting events."]
    return "\n".join(lines) + "\n"
