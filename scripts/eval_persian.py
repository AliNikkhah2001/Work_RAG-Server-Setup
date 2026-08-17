#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive Persian LLM evaluation over GGUF models via llama.cpp.

Tasks (all Persian; chat-completion prompting; text normalized for scoring):
  fa_arc          : Persian ARC-Easy multiple choice      -> exact letter
  fa_mc           : Parsinlu multiple-choice (ParsBench)  -> exact option number
  fa_math         : Parsinlu math (ParsBench)             -> numeric/date Jaccard
  fa_sentiment    : Parsinlu sentiment (ParsBench)        -> positive/negative
  fa_entail       : Parsinlu entailment (ParsBench)       -> entail/neutral/contradict
  fa_conjnli      : Persian ConjNLI entailment            -> entail/neutral/contradict
  fa_ner          : Persian NER (ParsBench)               -> token-label Jaccard
  fa_rc           : Parsinlu reading comprehension        -> answer Jaccard

Usage:
  HF_HUB_OFFLINE=1 python scripts/eval_persian.py \
      --model <path.gguf> [--tasks fa_arc,fa_mc,...] [--limit N] [--chat] \
      [--out logs/evalp_<name>.json]
Results include per-example input/output for report generation.
"""
import argparse
import json
import re
import time
from pathlib import Path

from llama_cpp import Llama

from persian_norm import normalize, jaccard

OUT_DIR = Path(__file__).resolve().parent.parent / "logs"
LLM_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

OPTION_RE = re.compile(r"[0-9۰-۹]+")


def build_loader():
    from datasets import load_dataset

    def get(name, cfg=None, split="train"):
        return load_dataset(name, cfg, split=split)

    return get


def _rows(get, name, cfg=None, split="train", limit=None):
    d = get(name, cfg, split=split)
    rows = list(d)
    return rows[:limit] if limit else rows


def load_fa_arc(get, limit):
    rows = []
    for ex in _rows(get, "MatinaAI/persian_arc", "ARC-Easy", "test", limit):
        rows.append({"kind": "mc", "prompt": mc_q(ex["question_fa"], ex["choices"]["text_fa"]),
                     "gold": ex["answerKey"], "gold_norm": normalize(ex["answerKey"])})
    return rows


def load_fa_mc(get, limit):
    rows = []
    for ex in _rows(get, "ParsBench/parsinlu-multiple-choice-alpaca-style", limit=limit):
        gold = ex["output"]
        m = OPTION_RE.search(gold)
        gold_opt = m.group(0) if m else None
        rows.append({"kind": "mc", "prompt": f"{ex['instruction']}\n{ex['input']}",
                     "gold": gold_opt, "gold_norm": normalize(gold), "raw_gold": gold})
    return rows


def load_fa_math(get, limit):
    rows = []
    for ex in _rows(get, "ParsBench/persian-math-alpaca-style", limit=limit):
        rows.append({"kind": "open", "prompt": f"{ex['instruction']}\n{ex['input']}",
                     "gold": ex["output"], "gold_norm": normalize(ex["output"])})
    return rows


def load_fa_sentiment(get, limit):
    rows = []
    for ex in _rows(get, "ParsBench/parsinlu-sentiment-analysis-alpaca-style", limit=limit):
        g = normalize(ex["output"])
        label = "positive" if "positive" in g or "مثبت" in g else ("negative" if "negative" in g or "منفی" in g else None)
        rows.append({"kind": "label", "prompt": f"{ex['instruction']}\n{ex['input']}",
                     "gold": label, "gold_norm": g, "raw_gold": ex["output"]})
    return rows


def load_fa_entail(get, limit, name="ParsBench/parsinlu-entailment-alpaca-style"):
    rows = []
    for ex in _rows(get, name, limit=limit):
        g = normalize(ex["output"])
        label = None
        # ParsBench labels appear as letter codes: c (contradiction), e (entailment), n (neutral)
        for key, word in (("c", "تضاد"), ("e", "استلزام"), ("n", "خنثی"),
                          ("contradict", "ناسازگار")):
            if key in g or word in g:
                label = {"c": "contradiction", "e": "entailment", "n": "neutral"}.get(key, key)
                break
        rows.append({"kind": "label", "prompt": f"{ex['instruction']}\n{ex['input']}",
                     "gold": label, "gold_norm": g, "raw_gold": ex["output"]})
    return rows


def load_fa_conjnli(get, limit):
    return load_fa_entail(get, limit, name="ParsBench/persian-conjnli-entailment-alpaca-style")


def load_fa_ner(get, limit):
    rows = []
    for ex in _rows(get, "ParsBench/persian-ner-alpaca-style", limit=limit):
        g = normalize(ex["output"])
        rows.append({"kind": "ner", "prompt": f"{ex['instruction']}\n{ex['input']}",
                     "gold": ex["output"], "gold_norm": g})
    return rows


def load_fa_rc(get, limit):
    rows = []
    for ex in _rows(get, "community-datasets/parsinlu_reading_comprehension", split="test", limit=limit):
        ans = ex["answers"]
        if isinstance(ans, dict):
            ans = " ".join(ans.get("answer_text") or [])
        rows.append({"kind": "open", "prompt": f"متن: {ex['context']}\n\nسؤال: {ex['question']}\nپاسخ:",
                     "gold": ans, "gold_norm": normalize(ans)})
    return rows


def mc_q(q, choices):
    opts = "\n".join(f"{LLM_LETTERS[i]}) {c}" for i, c in enumerate(choices))
    return f"سؤال: {q}\nگزینه‌ها:\n{opts}\nفقط حرف گزینه درست را بگو:"


def strip_think(text):
    """Strip Qwen3-style <think>...</think> reasoning blocks. The final
    answer is almost always the content after the closing </think> tag;
    when present we return only that tail."""
    if not text:
        return text
    # remove full think blocks
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # if a lone closing tag exists (unbalanced), keep everything after it
    if "</think>" in text and "<think>" not in text:
        t = text.split("</think>", 1)[1]
    return t.strip()


def extract_letter(text):
    m = re.search(r"\b([A-J])\b", text.upper())
    return m.group(1) if m else None


def extract_option_number(text):
    m = re.search(r"[0-9۰-۹]+", text)
    return m.group(0) if m else None


def extract_label(text):
    t = normalize(text)
    if "مثبت" in t or "positive" in t:
        return "positive"
    if "منفی" in t or "negative" in t:
        return "negative"
    if "استلزام" in t or "entail" in t or "e )" in t or "برچسب e" in t:
        return "entailment"
    if "تضاد" in t or "تناقض" in t or "contradict" in t or "ناسازگار" in t or "c )" in t or "برچسب c" in t:
        return "contradiction"
    if "خنثی" in t or "neutral" in t or "n )" in t or "برچسب n" in t:
        return "neutral"
    return None


def score(name, ex, text):
    kind = ex["kind"]
    if kind == "mc":
        if ex.get("gold"):
            pred = extract_letter(text) or extract_option_number(text)
            return (pred is not None and normalize(str(pred)) == normalize(str(ex["gold"]))), pred
        j = jaccard(ex["gold_norm"], text)
        return j >= 0.5, j
    if kind == "label":
        pred = extract_label(text)
        g = normalize(ex.get("gold") or ex["gold_norm"])
        if pred is None or not g:
            return False, pred
        return normalize(pred) in g or g in normalize(pred), pred
    if kind == "ner":
        j = jaccard(ex["gold_norm"], text)
        return j >= 0.2, round(j, 3)
    if kind == "open":
        # math / reading-comprehension: look for final-answer markers first
        gold_n = normalize(ex["gold_norm"])
        # numeric gold -> extract last number from output
        if re.fullmatch(r"-?\d[\d,]*\.?\d*", gold_n or ""):
            nums = re.findall(r"-?\d[\d,]*\.?\d*", text)
            if nums:
                last = nums[-1].replace(",", "")
                return last == gold_n.replace(",", ""), last
        for marker in ("پاسخ نهایی", "پاسخ نهایی:", "پاسخ:", "جواب:", "نتیجه نهایی"):
            idx = text.find(marker)
            if idx != -1:
                tail = text[idx + len(marker):]
                j = jaccard(ex["gold_norm"], tail)
                if j >= 0.3:
                    return True, round(j, 3)
        j = jaccard(ex["gold_norm"], text)
        return j >= 0.3, round(j, 3)
    return False, None


def run_task(llm, name, rows, max_tokens, temperature, chat, n_shots=0, fewshot_fn=None,
             prompt_style="vanilla"):
    correct = 0
    n = 0
    t0 = time.time()
    total_tokens = 0
    per_ex = []
    for ex in rows:
        prompt = ex["prompt"]
        if prompt_style == "improved":
            prompt = improved_prompt(name, prompt)
        if n_shots and fewshot_fn:
            prompt = fewshot_fn(ex, n_shots) + "\n\n" + prompt
        if chat:
            out = llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens, temperature=temperature)
            text = (out["choices"][0]["message"]["content"] or "").strip()
        else:
            out = llm(prompt, max_tokens=max_tokens, temperature=temperature)
            text = out["choices"][0]["text"].strip()
        text = strip_think(text)
        total_tokens += out["usage"]["completion_tokens"] if "usage" in out else 0
        hit, pred = score(name, ex, text)
        if hit:
            correct += 1
        n += 1
        per_ex.append({"prompt": prompt[:400], "gold": ex.get("raw_gold", ex["gold_norm"])[:200],
                       "pred": str(pred)[:80], "output": text[:300], "hit": bool(hit)})
    secs = time.time() - t0
    tok_sec = round(total_tokens / secs, 1) if secs and total_tokens else None
    return {"task": name, "n": n, "correct": correct,
            "acc": round(correct / n, 4) if n else None,
            "secs": round(secs, 1), "tok_sec": tok_sec, "samples": per_ex}


LOADERS = {
    "fa_arc": load_fa_arc,
    "fa_mc": load_fa_mc,
    "fa_math": load_fa_math,
    "fa_sentiment": load_fa_sentiment,
    "fa_entail": load_fa_entail,
    "fa_conjnli": load_fa_conjnli,
    "fa_ner": load_fa_ner,
    "fa_rc": load_fa_rc,
}


def make_fewshot(rows_by_task, n_shots):
    """Return a builder that prepends n_shots correct exemplars of the same
    task (with the gold answer appended) to each prompt."""
    shots = {}
    for t, rows in rows_by_task.items():
        pool = []
        for ex in rows:
            gold = ex.get("raw_gold", ex["gold_norm"])
            pool.append(ex["prompt"] + "\n" + str(gold))
        shots[t] = pool[:n_shots]

    def builder(ex, k):
        t = ex.get("_task", "")
        return "\n\n".join(shots.get(t, [])[:k])

    return builder


# ---------------------------------------------------------------------------
# Improved-prompting templates (4-component framework: ROLE + CONTEXT +
# CONSTRAINTS + OUTPUT FORMAT), written in Persian, deliberately short (~50-80
# tokens each so the eval stays fast). Built from the failure patterns seen in
# the sample-questions walkthrough: models emit prose/thinking-blocks/wrong
# format, so each template pins the exact output shape the scorer expects.
# ---------------------------------------------------------------------------
IMPROVED_TEMPLATES = {
    "fa_arc": (
        "شما یک کارشناس علوم پایه هستید. به یک سؤال چندگزینه‌ای پاسخ می‌دهید.\n"
        "قوانین:\n"
        "- فقط حرف گزینهٔ درست را بنویسید (A، B، C یا D).\n"
        "- هیچ توضیح، جمله یا علامتی اضافه نکنید.\n"
        "- اگر مطمئن نیستید، بهترین حدس را بزنید.\n"
        "فرمت خروجی: فقط یک حرف انگلیسی بزرگ، در یک خط.\n"
    ),
    "fa_mc": (
        "شما یک آزمون‌دهندهٔ دقیق هستید. پاسخ را از بین گزینه‌های داده‌شده انتخاب می‌کنید.\n"
        "قوانین:\n"
        "- فقط عدد گزینهٔ درست را بنویسید (1، 2، 3 یا 4).\n"
        "- جمله، توضیح یا حرف گزینه را ننویسید.\n"
        "فرمت خروجی: فقط یک عدد، در یک خط.\n"
    ),
    "fa_math": (
        "شما یک متخصص ریاضی هستید. مسئله را قدم‌به‌قدم حل می‌کنید.\n"
        "قوانین:\n"
        "- راه‌حل را به فارسی بنویسید؛ اعداد را با ارقام انگلیسی بنویسید.\n"
        "- در پایان، پاسخ نهایی را در یک بخش جدا بنویسید.\n"
        "- بعد از پاسخ نهایی هیچ عدد دیگری ننویسید.\n"
        "فرمت خروجی:\n"
        "[راه حل] …\n"
        "[پاسخ نهایی] عدد\n"
    ),
    "fa_sentiment": (
        "شما یک تحلیلگر احساسات هستید.\n"
        "قوانین:\n"
        "- فقط یکی از برچسب‌ها را بنویسید: مثبت، منفی، خنثی، یا سایر.\n"
        "- توضیح، نقل‌قول یا بازنویسی جمله ننویسید.\n"
        "فرمت خروجی: فقط برچسب به فارسی، در یک خط.\n"
    ),
    "fa_entail": (
        "شما یک متخصص استنتاج زبان طبیعی هستید. رابطهٔ فرضیه با پیش‌فرض را مشخص می‌کنید.\n"
        "قوانین:\n"
        "- فقط یکی از برچسب‌ها را بنویسید: استلزام، تناقض، یا خنثی.\n"
        "- توضیح اضافه نکنید.\n"
        "فرمت خروجی: فقط برچسب، در یک خط.\n"
    ),
    "fa_ner": (
        "شما یک متخصص برچسب‌گذاری موجودیت اسمی هستید.\n"
        "قوانین:\n"
        "- هر توکن ورودی را با برچسب مناسب علامت بزنید: per، loc، org، product، event، facility یا o.\n"
        "- برچسب‌ها کوچک باشند و فقط لیست تاپل‌ها را بنویسید.\n"
        "- مقدمه یا توضیح ننویسید.\n"
        "فرمت خروجی: [('کلمه', 'برچسب'), ...]\n"
    ),
    "fa_rc": (
        "شما یک پاسخ‌گوی دقیق هستید. پاسخ را مستقیم از متن استخراج می‌کنید.\n"
        "قوانین:\n"
        "- فقط پاسخ کوتاه (همان عبارت موجود در متن) را بنویسید.\n"
        "- توضیح یا بازنویسی ننویسید.\n"
        "فرمت خروجی: فقط پاسخ کوتاه، در یک خط.\n"
    ),
}


def improved_prompt(task, base):
    """Wrap a raw task prompt with the improved 4-component Persian template."""
    tpl = IMPROVED_TEMPLATES.get(task)
    return (tpl + "\n" + base) if tpl else base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", default="fa_arc,fa_mc,fa_math,fa_sentiment,fa_entail,fa_ner,fa_rc")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--n-gpu-layers", type=int, default=-1)
    ap.add_argument("--max-tokens", type=int, default=160)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--n-shots", type=int, default=0,
                    help="prepend N correct in-task exemplars to each prompt")
    ap.add_argument("--prompt-style", default="vanilla", choices=["vanilla", "improved"],
                    help="vanilla = dataset prompt only; improved = 4-component Persian template")
    args = ap.parse_args()

    get = build_loader()
    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    rows_by_task = {t: LOADERS[t](get, args.limit) for t in tasks}
    for t, r in rows_by_task.items():
        print(f"loaded {t}: {len(r)} rows")
        for ex in r:
            ex["_task"] = t
    fewshot_fn = make_fewshot(rows_by_task, args.n_shots) if args.n_shots else None

    t0 = time.time()
    llm = Llama(model_path=args.model, n_ctx=8192, n_gpu_layers=args.n_gpu_layers, verbose=False)
    print(f"model loaded in {time.time()-t0:.1f}s")

    results = []
    for t in tasks:
        print(f"\n=== {t} ({args.prompt_style}) ===")
        r = run_task(llm, t, rows_by_task[t], args.max_tokens, args.temperature, args.chat,
                     n_shots=args.n_shots, fewshot_fn=fewshot_fn,
                     prompt_style=args.prompt_style)
        print(f"acc={r['acc']}  ({r['correct']}/{r['n']})  {r['secs']}s  {r.get('tok_sec')} tok/s")
        results.append(r)

    scored = [r["acc"] for r in results if r["acc"] is not None]
    out = {"model": args.model, "results": results,
           "prompt_style": args.prompt_style, "n_shots": args.n_shots,
           "overall_mean": round(sum(scored) / len(scored), 4) if scored else None}
    name = args.out or f"evalp_{Path(args.model).stem}.json"
    if args.out is None:
        stem = Path(args.model).stem
        name = f"evalp_{stem}"
        if args.prompt_style == "improved":
            name += "_improved"
        if args.n_shots:
            name += f"_{args.n_shots}shot"
        name += ".json"
    p = OUT_DIR / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {p}")
    print(f"overall mean acc = {out['overall_mean']}")


if __name__ == "__main__":
    main()