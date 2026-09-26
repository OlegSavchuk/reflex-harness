"""Smoke test: Atlas, coding model, Jev, Voyage. Never prints secrets."""
import os
import time

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
OR = "https://openrouter.ai/api"
results = []


def check(name):
    def wrap(fn):
        t = time.time()
        try:
            detail = fn()
            results.append((name, "PASS", detail))
        except Exception as e:
            results.append((name, "FAIL", f"{type(e).__name__}: {str(e)[:180]}"))
        results[-1] = results[-1] + (f"{(time.time() - t) * 1000:.0f}ms",)
        return fn
    return wrap


def or_headers():
    return {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json"}


@check("Atlas")
def _():
    c = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=8000)
    v = c.server_info()["version"]
    col = c[os.environ.get("MONGODB_DB", "reflex")]["_smoke"]
    _id = col.insert_one({"t": time.time()}).inserted_id
    assert col.find_one({"_id": _id})
    col.delete_one({"_id": _id})
    return f"MongoDB {v}, read/write ok"


@check("Coding model")
def _():
    r = requests.post(f"{OR}/v1/chat/completions", headers=or_headers(), timeout=30, json={
        "model": os.environ["CODING_MODEL"],
        "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
        "max_tokens": 10, "temperature": 0, "usage": {"include": True}})
    r.raise_for_status()
    j = r.json()
    u = j.get("usage", {})
    return (f"{j.get('model')} said {j['choices'][0]['message']['content']!r}, "
            f"tokens {u.get('prompt_tokens')}/{u.get('completion_tokens')}, cost {u.get('cost')}")


@check("Jev")
def _():
    r = requests.post(f"{OR}/alpha/decisions", headers=or_headers(), timeout=30, json={
        "model": os.environ.get("JEV_MODEL", "typesafe/jev-1.13"),
        "state": {"attempt_1": "Rounded total to 2 decimals in calculate_total. Test still fails.",
                  "attempt_2": "Rounded total to 3 decimals in calculate_total. Same test fails."},
        "questions": {"repeating": {
            "type": "noul",
            "instructions": "Is attempt_2 the same strategy as attempt_1?",
            "criteria": {"true": "Same code, same idea, no new information.",
                         "false": "Different location or new information."}}}})
    r.raise_for_status()
    j = r.json()
    p = j["answers"]["repeating"]["noul"]
    return f"{j.get('model')} p(repeating)={p}, cost {j.get('usage', {}).get('cost')}"


@check("Voyage")
def _():
    base = os.environ.get("VOYAGE_BASE_URL", "https://ai.mongodb.com/v1")
    r = requests.post(f"{base}/embeddings", timeout=30,
                      headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
                      json={"input": ["shared function breaks second caller"], "model": "voyage-4"})
    r.raise_for_status()
    j = r.json()
    return f"voyage-4 dims={len(j['data'][0]['embedding'])}, tokens {j.get('usage', {}).get('total_tokens')}"


w = max(len(n) for n, *_ in results)
for name, status, detail, ms in results:
    print(f"{'✔' if status == 'PASS' else '✘'} {name:<{w}}  {status}  {ms:>6}  {detail}")
print(f"\n{sum(s == 'PASS' for _, s, *_ in results)}/{len(results)} passed")
