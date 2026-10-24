#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A/B benchmark: llama.cpp (GGUF) vs TensorRT-LLM for champion gemma-4-31b.

Hits each OpenAI-compatible endpoint DIRECTLY (bypasses the `:9000` manager so
the two backends are compared under identical prompts/concurrency in one run;
the manager's Triton-promotion would otherwise reroute all gemma traffic to a
single backend, defeating the comparison).

Token accounting: to keep the two backends comparable we re-encode every
generated output with the **same** gemma tokenizer (`--tokenizer`, default the
HF model dir) and use that real subword count for tok/s on both sides. This
matters because llama.cpp's placeholder `:18000` returns no `usage` and often
stops early, while TensorRT-LLM emits the full `max_tokens` and reports usage.

Usage:
  python3 bench_trtllm_vs_llamacpp.py \
      --target llama_cpp=http://127.0.0.1:18000#local-llm \
      --target trtllm=http://127.0.0.1:8010#google_gemma-4-31b-it \
      --repeats 3 --concurrency 1,4 --max-tokens 256
"""
import argparse
import json
import time
import statistics
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

# A long-form Persian prompt so decode dominates and both servers run ~max_tokens.
PROMPT = ("سؤال: یک مقاله کوتاه درباره نقش هوش مصنوعی در پزشکی بنویس و در پایان خلاصه کن. "
          "چندین کاربرد شامل تشخیص بیماری، دارورسانی شخصی‌سازی شده، و جراحی رباتیک را شرح بده.")

ROOT = Path("/splunk-data/v1/Work_RAG-Server-Setup")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def count_tokens(tokenizer, text, fallback_words):
    """Real gemma subword count when a tokenizer is available, else word proxy."""
    if tokenizer is not None and text:
        try:
            return len(tokenizer.encode(text, add_special_tokens=False))
        except Exception:  # noqa: BLE001
            pass
    return fallback_words


def one_request(base_url, model, max_tokens, temperature, timeout, tokenizer=None):
    """Fire a single non-streaming chat completion; return latency + token info."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions", data=data,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}",
                "secs": round(time.monotonic() - t0, 3)}
    except Exception as e:  # noqa: BLE001 - surface any transport error as data
        return {"error": str(e)[:200], "secs": round(time.monotonic() - t0, 3)}
    dt = time.monotonic() - t0
    choice = (body.get("choices") or [{}])[0]
    txt = (choice.get("message") or {}).get("content") or ""
    usage = body.get("usage") or {}
    ct = usage.get("completion_tokens")
    server_tokens = ct if ct is not None else None
    toks = count_tokens(tokenizer, txt, len(txt.split()))
    return {
        "secs": round(dt, 3),
        "tokens": toks,
        "server_tokens": server_tokens,
        "usage_based": server_tokens is not None,
        "tok_s": round(toks / dt, 1) if dt > 0 else 0.0,
        "finish": choice.get("finish_reason"),
        "chars": len(txt),
    }


def bench_target(name, base_url, model, repeats, concurrency, max_tokens,
                 temperature, timeout, tokenizer=None):
    """Run `repeats` batches of `concurrency` parallel requests; aggregate."""
    # Warmup (compile/JIT/caches) so the first measured batch is representative.
    try:
        one_request(base_url, model, 16, temperature, timeout, tokenizer)
    except Exception:  # noqa: BLE001
        pass

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for _ in range(repeats):
            t0 = time.monotonic()
            batch = list(pool.map(
                lambda _: one_request(base_url, model, max_tokens, temperature,
                                      timeout, tokenizer),
                range(concurrency)))
            wall = time.monotonic() - t0
            ok = [x for x in batch if "error" not in x]
            agg_tps = (sum(x["tokens"] for x in ok) / wall) if (ok and wall > 0) else 0.0
            results.append({"wall": round(wall, 3), "batch": batch,
                            "agg_tok_s": round(agg_tps, 1)})

    flat = [x for r in results for x in r["batch"] if "error" not in x]
    errs = [x for r in results for x in r["batch"] if "error" in x]
    if not flat:
        return {"target": name, "url": base_url, "concurrency": concurrency,
                "errors": errs[:3], "agg_tok_s": 0.0}
    lat = [x["secs"] for x in flat]
    per_req_tps = [x["tok_s"] for x in flat]
    agg = [r["agg_tok_s"] for r in results]
    return {
        "target": name,
        "url": base_url,
        "model": model,
        "concurrency": concurrency,
        "repeats": repeats,
        "samples": len(flat),
        "usage_based": all(x["usage_based"] for x in flat),
        "agg_tok_s_mean": round(statistics.mean(agg), 1),
        "agg_tok_s_max": round(max(agg), 1),
        "per_req_tok_s_mean": round(statistics.mean(per_req_tps), 1),
        "lat_p50_ms": int(statistics.median(lat) * 1000),
        "lat_p95_ms": int(sorted(lat)[min(len(lat) - 1, int(0.95 * len(lat)))] * 1000),
        "avg_completion_tokens": round(statistics.mean([x["tokens"] for x in flat]), 1),
        "error_count": len(errs),
    }


def parse_target(spec):
    """Parse `name=url#model` -> (name, url, model). model defaults to name."""
    name, rhs = spec.split("=", 1)
    if "#" in rhs:
        url, model = rhs.split("#", 1)
    else:
        url, model = rhs, name
    return name, url.rstrip("/"), model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", action="append", required=True,
                    help="name=base_url#model (repeatable)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--concurrency", default="1,4")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--tokenizer", default=str(
        ROOT / "offline-prep/models/huggingface/google_gemma-4-31b-it"),
        help="HF dir for the shared tokenizer (real subword counts); '' disables")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    tokenizer = None
    if args.tokenizer:
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                args.tokenizer, trust_remote_code=True)
            print(f"tokenizer: {args.tokenizer} (vocab={tokenizer.vocab_size})",
                  flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"tokenizer load failed ({e}); falling back to word counts",
                  flush=True)

    targets = [parse_target(t) for t in args.target]
    concs = [int(x) for x in args.concurrency.split(",")]

    results = {}
    for name, url, model in targets:
        results[name] = {}
        for conc in concs:
            print(f"=== {name} ({url}) conc={conc} ===", flush=True)
            res = bench_target(name, url, model, args.repeats, conc,
                               args.max_tokens, args.temperature, args.timeout,
                               tokenizer)
            results[name][f"conc_{conc}"] = res
            if res.get("agg_tok_s_mean"):
                print(f"  agg={res['agg_tok_s_mean']} tok/s  per_req={res['per_req_tok_s_mean']}"
                      f"  p50={res['lat_p50_ms']}ms  tokens={res['avg_completion_tokens']}"
                      f"  usage={res['usage_based']}  errs={res['error_count']}", flush=True)
            else:
                print(f"  FAILED: {res.get('errors', res.get('error_count'))}", flush=True)

    # Speedup of each non-baseline target vs the first target, per concurrency.
    baseline_name = targets[0][0]
    for conc in concs:
        base = results[baseline_name][f"conc_{conc}"].get("agg_tok_s_mean") or 0
        if base:
            for name, _, _ in targets:
                v = results[name][f"conc_{conc}"]
                if v.get("agg_tok_s_mean"):
                    v["speedup_vs_" + baseline_name] = round(v["agg_tok_s_mean"] / base, 2)

    out = {
        "meta": {
            "ts": datetime.now().isoformat(),
            "prompt_preview": PROMPT[:80],
            "max_tokens": args.max_tokens,
            "repeats": args.repeats,
            "host": "ai-gpu1 H200 (llama.cpp GPU0 / TRT-LLM GPU1)",
        },
        "results": results,
    }
    out_path = Path(args.out) if args.out else LOG_DIR / f"bench_trtllm_vs_llamacpp_{datetime.now():%Y%m%d_%H%M%S}.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
