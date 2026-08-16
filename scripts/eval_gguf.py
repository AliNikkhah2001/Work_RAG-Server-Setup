#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evaluate GGUF models (llama.cpp) on conventional + Persian tasks.

Tasks:
  mmlu_3subj  : English multiple-choice (abstract_algebra, computer_security,
                high_school_mathematics) — exact-letter match
  gsm8k       : English arithmetic reasoning — final-answer extraction
  fa_arc      : Persian ARC-Easy multiple-choice — exact-letter match
  fa_rc       : Persian reading comprehension — answer containment

Usage:
  python scripts/eval_gguf.py --model <path.gguf> --tasks mmlu_3subj,gsm8k \
      [--limit N] [--n-gpu-layers -1] [--out logs/eval_<name>.json]
"""
import argparse
import json
import random
import re
import time
from pathlib import Path

from llama_cpp import Llama

CACHE = Path(__file__).resolve().parent.parent / "offline-prep" / "datasets"
OUT_DIR = Path(__file__).resolve().parent.parent / "logs"


def build_loader():
    from datasets import load_dataset
    cache = load_dataset  # noqa: placeholder

    def get(name, cfg=None, split="test"):
        return load_dataset(name, cfg, split=split)

    return get


def load_mmlu(get, limit):
    rows = []
    for subj in ["abstract_algebra", "computer_security", "high_school_mathematics"]:
        d = get("cais/mmlu", subj, split="test")
        for ex in d:
            rows.append({"subj": subj, "q": ex["question"],
                         "choices": ex["choices"], "answer": ex["answer"]})
    if limit:
        rows = rows[:limit]
    return rows


def load_gsm8k(get, limit):
    d = get("openai/gsm8k", "main", split="test")
    rows = [{"q": ex["question"], "answer": ex["answer"]} for ex in d]
    return rows[:limit] if limit else rows


def load_fa_arc(get, limit):
    d = get("MatinaAI/persian_arc", "ARC-Easy", split="test")
    rows = []
    for ex in d:
        rows.append({"q": ex["question_fa"], "choices": ex["choices"]["text_fa"],
                     "labels": ex["choices"]["label"], "answer": ex["answerKey"]})
    return rows[:limit] if limit else rows


def load_fa_rc(get, limit):
    d = get("community-datasets/parsinlu_reading_comprehension", split="test")
    rows = []
    for ex in d:
        ans = ex["answers"]
        if isinstance(ans, dict):
            ans = " ".join(ans.get("answer_text") or [])
        rows.append({"q": ex["question"], "ctx": ex["context"], "answer": ans})
    return rows[:limit] if limit else rows


MC_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def mc_prompt(q, choices):
    opts = "\n".join(f"{MC_LETTERS[i]}) {c}" for i, c in enumerate(choices))
    return f"Question: {q}\nOptions:\n{opts}\nAnswer with the single letter of the correct option:"


def extract_letter(text):
    m = re.search(r"\b([A-J])\b", text.upper())
    return m.group(1) if m else None


def gsm8k_answer(ex):
    return ex["answer"].split("####")[-1].strip()


def run_task(llm, name, rows, max_tokens, temperature, chat=False):
    correct = 0
    n = 0
    start = time.time()
    results = []
    for ex in rows:
        if name == "mmlu_3subj":
            prompt = mc_prompt(ex["q"], ex["choices"])
            gold = MC_LETTERS[ex["answer"]]
        elif name == "fa_arc":
            prompt = mc_prompt(ex["q"], ex["choices"])
            gold = ex["answer"]
        elif name == "gsm8k":
            prompt = f"Question: {ex['q']}\nSolve step by step. End with '#### <final answer number>'."
            gold = gsm8k_answer(ex)
        elif name == "fa_rc":
            prompt = f"متن: {ex['ctx']}\n\nسؤال: {ex['q']}\nپاسخ:"
            gold = ex["answer"]
        else:
            raise ValueError(name)

        if chat:
            out = llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens, temperature=temperature)
            text = out["choices"][0]["message"]["content"].strip()
        else:
            out = llm(prompt, max_tokens=max_tokens, temperature=temperature)
            text = out["choices"][0]["text"].strip()

        if name in ("mmlu_3subj", "fa_arc"):
            pred = extract_letter(text)
            hit = pred == gold
        elif name == "gsm8k":
            m = re.findall(r"####\s*([-\d,]+\.?\d*)", text)
            if m:
                pred = m[0].replace(",", "")
            else:
                nums = re.findall(r"\b(-?\d[\d,]*(?:\.\d+)?)\b", text)
                pred = nums[-1].replace(",", "") if nums else None
            goldn = gold.replace(",", "")
            hit = pred == goldn
        else:  # fa_rc
            gold_lo = gold.lower()
            pred = text
            hit = gold_lo in pred.lower() or (len(gold) > 8 and any(g.lower() in pred.lower() for g in [gold]))

        if hit:
            correct += 1
        n += 1
        results.append({"pred": pred, "gold": gold, "hit": bool(hit),
                        "out": text[:120]})

    return {"task": name, "n": n, "correct": correct,
            "acc": round(correct / n, 4) if n else None,
            "secs": round(time.time() - start, 1), "results": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", default="mmlu_3subj,gsm8k,fa_arc,fa_rc")
    ap.add_argument("--limit", type=int, default=100, help="max rows per task (0=all)")
    ap.add_argument("--n-gpu-layers", type=int, default=-1)
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--chat", action="store_true", help="use chat completions (needed for thinking-channel models like Gemma-4)")
    args = ap.parse_args()

    get = build_loader()
    loaders = {"mmlu_3subj": load_mmlu, "gsm8k": load_gsm8k,
               "fa_arc": load_fa_arc, "fa_rc": load_fa_rc}

    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    rows_by_task = {t: loaders[t](get, args.limit) for t in tasks}
    for t, r in rows_by_task.items():
        print(f"loaded {t}: {len(r)} rows")

    t0 = time.time()
    llm = Llama(model_path=args.model, n_ctx=8192, n_gpu_layers=args.n_gpu_layers, verbose=False)
    print(f"model loaded in {time.time()-t0:.1f}s")

    results = []
    for t in tasks:
        print(f"\n=== {t} ===")
        r = run_task(llm, t, rows_by_task[t], args.max_tokens, args.temperature, chat=args.chat)
        print(f"acc={r['acc']}  ({r['correct']}/{r['n']})  {r['secs']}s")
        results.append(r)

    out = {"model": args.model, "results": results,
           "overall_mean": round(sum(r["acc"] or 0 for r in results) / len(results), 4)}
    name = args.out or f"eval_{Path(args.model).stem}.json"
    out_path = OUT_DIR / name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {out_path}")
    print(f"overall mean acc = {out['overall_mean']}")


if __name__ == "__main__":
    main()