#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Benchmark: llama.cpp baseline vs Triton-optimized vLLM (B) vs TRT-LLM (A) on champion gemma-4-31b"""
import argparse, json, time, statistics, asyncio, os
from pathlib import Path
from datetime import datetime
import httpx

PROMPT = ("سؤال: یک مقاله کوتاه درباره نقش هوش مصنوعی در پزشکی بنویس و در پایان خلاصه کن. "
          "چندین کاربرد شامل تشخیص بیماری، دارورسانی شخصی‌سازی شده، و جراحی رباتیک را شرح بده.")

ROOT = Path("/splunk-data/v1/Work_RAG-Server-Setup")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

async def bench_once(client, model, max_tokens=256):
    payload = {"model": model, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": max_tokens, "temperature": 0.3}
    t0 = time.monotonic()
    r = await client.post("http://127.0.0.1:9000/v1/chat/completions", json=payload)
    dt = time.monotonic() - t0
    if r.status_code != 200:
        return {"error": r.text[:300], "secs": dt, "status": r.status_code}
    j = r.json()
    txt = j["choices"][0]["message"]["content"] if j.get("choices") else ""
    # estimate tokens via whitespace (manager doesn't return usage for proxy)
    est_toks = len(txt.split())
    return {"secs": round(dt,3), "est_toks": est_toks, "tok_s": round(est_toks/dt,1) if dt else 0, "chars": len(txt), "latency_ms": int(dt*1000)}

async def bench_model(model, repeats=3, concurrency=1, max_tokens=256):
    timeout = httpx.Timeout(120.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as c:
        # warmup
        try:
            await bench_once(c, model, max_tokens=16)
        except: pass
        results=[]
        for r in range(repeats):
            t0=time.monotonic()
            if concurrency==1:
                res = await bench_once(c, model, max_tokens)
                results.append(res)
            else:
                tasks=[bench_once(c, model, max_tokens) for _ in range(concurrency)]
                batch=await asyncio.gather(*tasks)
                results.extend(batch)
            await asyncio.sleep(0.5)
        ok=[x for x in results if "error" not in x]
        errs=[x for x in results if "error" in x]
        if not ok:
            return {"model":model,"concurrency":concurrency,"errors":errs,"avg_tok_s":0}
        secs=[x["secs"] for x in ok]
        toks=[x["tok_s"] for x in ok]
        return {
            "model":model,
            "concurrency":concurrency,
            "repeats":repeats,
            "samples":len(ok),
            "avg_secs":round(statistics.mean(secs),3),
            "p50_ms":int(statistics.median(secs)*1000),
            "p95_ms":int(sorted(secs)[int(0.95*len(secs))-1]*1000) if len(secs)>1 else int(secs[0]*1000),
            "avg_tok_s":round(statistics.mean(toks),1),
            "max_tok_s":max(toks),
            "min_tok_s":min(toks),
            "errors":len(errs),
            "raw":ok[:3]
        }

async def main_async(models, repeats, concs, max_tokens):
    out={}
    for m in models:
        out[m]={}
        for c in concs:
            print(f"=== {m} conc={c} ===", flush=True)
            try:
                res=await bench_model(m, repeats=repeats, concurrency=c, max_tokens=max_tokens)
                print(f"  {res['avg_tok_s']} tok/s p50={res.get('p50_ms')}ms errs={res.get('errors')}", flush=True)
                out[m][f"conc_{c}"]=res
            except Exception as e:
                print(f"  ERROR {e}", flush=True)
                out[m][f"conc_{c}"]={"error":str(e)}
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--models", default="gemma-4-31b,gemma-4-31b-triton-vllm,gemma-4-31b-triton-trt")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--concurrency", default="1,4")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--out", default=None)
    args=ap.parse_args()
    models=[m.strip() for m in args.models.split(",")]
    concs=[int(x) for x in args.concurrency.split(",")]
    out_path=Path(args.out) if args.out else LOG_DIR / f"bench_compare_{datetime.now():%Y%m%d_%H%M%S}.json"
    res=asyncio.run(main_async(models, args.repeats, concs, args.max_tokens))
    meta={"ts":datetime.now().isoformat(),"prompt_preview":PROMPT[:80],"max_tokens":args.max_tokens,"manager":"http://127.0.0.1:9000","host":"ai-gpu1 H200"}
    final={"meta":meta,"results":res}
    # compute speedup vs baseline if present
    baseline = res.get("gemma-4-31b",{}).get("conc_1",{}).get("avg_tok_s")
    if baseline:
        for m in models:
            for ck,v in res.get(m,{}).items():
                if isinstance(v, dict) and v.get("avg_tok_s"):
                    v["speedup_vs_baseline"]=round(v["avg_tok_s"]/baseline,2) if baseline else None
    out_path.write_text(json.dumps(final, indent=2, ensure_ascii=False))
    print(f"\nwrote {out_path}")
    print(json.dumps(final, indent=2, ensure_ascii=False))

if __name__=="__main__":
    main()
