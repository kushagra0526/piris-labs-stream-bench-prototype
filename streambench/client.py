"""Streaming client for OpenAI-compatible /chat/completions. stdlib only.

Times every SSE event from just before the request is sent. Token count comes from the final `usage`
chunk (requested with stream_options.include_usage), never from counting events.
"""
import http.client
import json
import os
import time
from urllib.parse import urlparse


def stream_once(url, model, prompt, max_tokens, api_key=None, timeout=300):
    u = urlparse(url)
    conn = (http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection)(
        u.hostname, u.port, timeout=timeout)
    body = json.dumps({
        "model": model, "stream": True, "max_tokens": max_tokens, "temperature": 0,
        "stream_options": {"include_usage": True},
        "messages": [{"role": "user", "content": prompt}],
    })
    headers = {"Content-Type": "application/json"}
    key = api_key or os.environ.get("STREAMBENCH_API_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    t0 = time.perf_counter()
    conn.request("POST", u.path or "/v1/chat/completions", body, headers)
    resp = conn.getresponse()
    if resp.status != 200:
        raise RuntimeError(f"HTTP {resp.status}: {resp.read()[:200]!r}")
    events, usage = [], None
    for raw in resp:
        line = raw.strip()
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            break
        now = time.perf_counter() - t0
        obj = json.loads(data)
        if obj.get("usage"):
            usage = obj["usage"].get("completion_tokens")
        for ch in obj.get("choices") or []:
            text = (ch.get("delta") or {}).get("content")
            if text:
                events.append((now, text))
    t_end = time.perf_counter() - t0
    conn.close()
    if usage is None:
        raise RuntimeError("endpoint sent no usage; token count would be a guess")
    return events, usage, t_end
