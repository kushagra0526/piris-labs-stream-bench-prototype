# Streaming benchmark card

## Protocol
- **Output length:** 512 tokens (max_tokens), temperature 0
- **Runs:** 12 per endpoint per context, round-robin interleaved, 1 warm-up each
- **Sessions:** 1 (run more at other times of day and merge runs.jsonl)
- **Token count:** usage.completion_tokens (stream_options.include_usage)
- **Client:** Python http.client, timestamps at SSE event receipt
- **Endpoints:** steady (sim), volatile (sim), chunky (sim)
- **Note:** simulated local endpoints, clock sped up 10x and converted back

## Input context 10,000 tokens

| Endpoint | TTFT median (p90) | Decode tok/s median [95% CI] (p10–p90) | End-to-end tok/s | Peak decode (not a headline) |
|---|---|---|---|---|
| steady | 0.42 s (0.45) | **316** [312–336] (302–346) | 251 | 357 |
| volatile | 0.57 s (0.90) | **173** [140–205] (138–250) | 148 | 263 |
| chunky | 0.84 s (0.87) | **297** [280–307] (268–313) | 202 | 319 |

- Decode speed: **steady** is faster than every other endpoint (95% confidence).
- What a user waits for (end-to-end, including TTFT): **steady** is faster than every other endpoint (95% confidence).

## Input context 100,000 tokens

| Endpoint | TTFT median (p90) | Decode tok/s median [95% CI] (p10–p90) | End-to-end tok/s | Peak decode (not a headline) |
|---|---|---|---|---|
| steady | 3.44 s (3.69) | **321** [307–337] (302–342) | 102 | 347 |
| volatile | 3.90 s (4.07) | **216** [188–286] (118–303) | 83 | 310 |
| chunky | 7.17 s (7.39) | **303** [288–317] (268–341) | 58 | 353 |

- Decode speed: tie between steady, chunky.
- What a user waits for (end-to-end, including TTFT): **steady** is faster than every other endpoint (95% confidence).

Decode = tokens after the first event / time from first to last event. End-to-end = all output tokens / time from send to last token. Tokens come from `usage.completion_tokens`, never from counting events.
