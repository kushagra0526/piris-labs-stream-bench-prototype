"""Per-request metrics from what a streaming client actually sees: event times, event text, usage."""


def measure(events, usage_tokens, t_end=None):
    """events: [(seconds after send, text)] for content events; usage_tokens: usage.completion_tokens.

    decode = tokens after the first event / (last event - first event). The first event may hold several
    tokens (coalescing), so its token share is estimated from its share of the characters.
    """
    if not events:
        return None
    n = usage_tokens
    t_first, t_last = events[0][0], events[-1][0]
    chars = sum(len(x) for _, x in events) or 1
    after = n * (1 - len(events[0][1]) / chars)
    span = t_last - t_first
    return {
        "ttft": t_first,
        "decode": after / span if span > 0 else None,
        "e2e": n / (t_end if t_end is not None else t_last),
        "tokens": n,
        "events": len(events),
    }


def naive_event_rate(events):
    """What a client gets if it counts SSE events as tokens (common in quick scripts)."""
    span = events[-1][0] - events[0][0]
    return (len(events) - 1) / span if span > 0 else None
