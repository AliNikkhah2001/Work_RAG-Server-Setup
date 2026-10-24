#!/usr/bin/env python3
"""Quantize gemma-4-31b (multimodal) to FP8 or NVFP4 with NVIDIA ModelOpt PTQ.

This produces a Hugging Face checkpoint that TensorRT-LLM's PyTorch backend
(`trtllm-serve --backend pytorch`) auto-detects as quantized via the
`hf_quant_config.json` + `config.json.quantization_config` that ModelOpt writes.

Why the workflow is shaped this way
-----------------------------------
* gemma-4 is a multimodal model (`Gemma4ForConditionalGeneration` = text LM +
  vision tower). ModelOpt's official FP8 PTQ path for VLMs quantizes ONLY the
  language model and keeps the vision encoder in BF16 (see ModelOpt
  `examples/hf_ptq`). We mirror that exactly:
    1. load the full VLM,
    2. pull the language-model lineage out of it,
    3. mark every non-language component as "quantization disabled" so it is
       exported as BF16 and listed in the checkpoint's `exclude_modules`,
    4. run FP8 PTQ + calibration on the language model only.
* Calibration is text-only: the gemma-4 checkpoint here has
  `hidden_size_per_layer_input=0`, so `Gemma4TextModel.forward(input_ids, ...)`
  needs nothing besides token ids. The vision tower never runs, which is
  consistent with its disabled quantizers.
* The checkpoint is exported with `modelopt.torch.export.export_hf_checkpoint`,
  the same exporter TRT-LLM expects. It writes `hf_quant_config.json` with the
  ModelOpt legacy shape (`producer.name == "modelopt"`, `quantization.quant_algo`)
  that `tensorrt_llm/_torch/model_config.py` reads.

Offline-safe by design: the model is a local path, calibration text is local
(built-in list or a file), and no Hub call is required.

Example
-------
    offline-prep/venv-modelopt/bin/python scripts/quantize_gemma4_fp8.py \
        --model offline-prep/models/huggingface/google_gemma-4-31b-it \
        --out   offline-prep/models/huggingface/google_gemma-4-31b-it-fp8 \
        --quant fp8 --calib-samples 32 --gpu 0
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, List

# Small local calibration set (Persian + English). Deliberately offline: no
# dataset download is needed and the same set works on every host. Credit /
# finance phrasing matches the platform's domain so activation ranges are
# representative for the RAG workload.
DEFAULT_CALIB_TEXTS: List[str] = [
    "اعتبارسنجی مشتریان یکی از مراحل اصلی در فرآیند اعطای تسهیلات بانکی است.",
    "برای دریافت وام، بانک ابتدا وضعیت اعتباری متقاضی را بررسی می‌کند.",
    "نرخ سود تسهیلات بر اساس نوع عقد و مدت بازپرداخت تعیین می‌شود.",
    "گزارش اعتباری نشان‌دهنده سابقه بازپرداخت اقساط و تعهدات مالی فرد است.",
    "مدل‌های یادگیری ماشین می‌توانند ریسک نکول را با دقت بیشتری پیش‌بینی کنند.",
    "داده‌های تراکنشی مشتریان برای تشخیص الگوهای مشکوک تحلیل می‌شوند.",
    "Chegini RAG platform answers credit questions using retrieval augmented generation.",
    "A credit score summarizes repayment history, debt ratio, and account activity.",
    "The model retrieves relevant documents before generating an answer with citations.",
    "Quantization reduces memory footprint while preserving most of the model quality.",
    "TensorRT-LLM serves the quantized checkpoint behind an OpenAI-compatible API.",
    "Calibration collects activation statistics to compute per-tensor FP8 scales.",
    "بازپرداخت به موقع اقساط باعث افزایش امتیاز اعتباری مشتری می‌شود.",
    "ضمانت‌نامه بانکی تعهدی است که بانک به درخواست مشتری صادر می‌کند.",
    "تحلیل جریان نقدی شرکت برای ارزیابی توان بازپرداخت ضروری است.",
    "تاریخچه معاملات و مانده حساب از عوامل موثر در تصمیم اعتباری هستند.",
]


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    root = Path(__file__).resolve().parent.parent
    default_model = root / "offline-prep/models/huggingface/google_gemma-4-31b-it"
    default_out = root / "offline-prep/models/huggingface/google_gemma-4-31b-it-fp8"

    parser = argparse.ArgumentParser(
        description="ModelOpt PTQ (FP8/NVFP4) for gemma-4-31b -> TRT-LLM checkpoint.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--model", default=str(default_model),
                        help="Local HF checkpoint directory to quantize.")
    parser.add_argument("--out", default=str(default_out),
                        help="Output directory for the quantized checkpoint.")
    parser.add_argument("--quant", choices=["fp8", "nvfp4"], default="fp8",
                        help="Target weight/activation format.")
    parser.add_argument("--calib-samples", type=int, default=32,
                        help="Number of calibration sequences to run.")
    parser.add_argument("--calib-dataset", default=None,
                        help="Optional text file (one sample per line). If omitted, "
                             "the built-in Persian/English calibration set is used.")
    parser.add_argument("--batch-size", type=int, default=4,
                        help="Calibration batch size.")
    parser.add_argument("--max-seq-len", type=int, default=512,
                        help="Maximum calibration sequence length.")
    parser.add_argument("--gpu", type=int, default=0,
                        help="CUDA device index used for loading and calibration.")
    parser.add_argument("--check", action="store_true",
                        help="Only load config/tokenizer and report versions (CPU, no weights).")
    return parser.parse_args(argv)


def load_calibration_texts(args: argparse.Namespace) -> List[str]:
    """Return calibration strings from the file override or the built-in list."""
    if args.calib_dataset:
        path = Path(args.calib_dataset)
        if not path.is_file():
            raise FileNotFoundError(f"--calib-dataset not found: {path}")
        texts = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
        if not texts:
            raise ValueError(f"--calib-dataset is empty: {path}")
        return texts
    return list(DEFAULT_CALIB_TEXTS)


def build_forward_loop(language_model, tokenizer, texts: List[str],
                       device: str, args: argparse.Namespace) -> Callable:
    """Create a calibration `forward_loop` callable for `mtq.quantize`.

    The loop tokenizes a bounded number of samples and runs them through the
    language model under `torch.no_grad()` so the inserted quantizers can
    collect activation statistics. It must accept the model as its argument
    because ModelOpt re-invokes it on the quantized replica.
    """
    import torch

    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    samples = texts[: args.calib_samples]

    def forward_loop(model) -> None:
        model.eval()
        with torch.no_grad():
            for start in range(0, len(samples), args.batch_size):
                batch_texts = samples[start:start + args.batch_size]
                batch = tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=args.max_seq_len,
                ).to(device)
                # `use_cache=False` avoids materializing a KV cache during calibration.
                model(**batch, use_cache=False)

    return forward_loop


def extract_language_model(full_model):
    """Pull the language-model submodule out of a VLM and disable quant elsewhere.

    Mirrors ModelOpt's `extract_and_prepare_language_model_from_vl`: the language
    model is quantized while every sibling module (vision tower, embeddings,
    projector) gets a disabled-quant config so it exports as BF16.
    Returns the language model (or the input model if it is not multimodal).
    """
    import modelopt.torch.quantization as mtq

    try:
        from modelopt.torch.export.model_utils import get_language_model_from_vl
    except Exception:  # ModelOpt without the VLM helper -> treat as text-only.
        return full_model, False

    lineage = get_language_model_from_vl(full_model)
    if lineage is None:
        return full_model, False

    language_model = lineage[-1]
    ancestors = lineage[:-1]
    disabled_cfg = {
        "quant_cfg": [{"quantizer_name": "*", "enable": False}],
        "algorithm": "max",
    }
    memo = set(ancestors) | {language_model}
    for ancestor in ancestors:
        for _, module in ancestor.named_children():
            if module not in memo:
                mtq.quantize(module, disabled_cfg, forward_loop=None)
                memo.add(module)
    return language_model, True


def copy_tokenizer_files(model_dir: Path, out_dir: Path) -> None:
    """Copy tokenizer/processor sidecar files so `trtllm-serve` can load them."""
    from transformers import AutoProcessor, AutoTokenizer

    try:
        AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=False) \
            .save_pretrained(str(out_dir))
    except Exception as exc:  # non-fatal: tokenizer may already be covered.
        print(f"[warn] tokenizer copy skipped: {exc}")

    try:
        AutoProcessor.from_pretrained(str(model_dir), trust_remote_code=False) \
            .save_pretrained(str(out_dir))
    except Exception as exc:
        print(f"[warn] processor copy skipped: {exc}")


def run_check(args: argparse.Namespace) -> int:
    """CPU-only feasibility check: imports, versions, model config load."""
    import torch
    import modelopt.torch.quantization as mtq  # noqa: F401  (import is the check)
    from transformers import AutoConfig, AutoTokenizer

    from modelopt.torch.opt import enable_huggingface_checkpointing

    enable_huggingface_checkpointing()
    print(f"torch          : {torch.__version__} (cuda_available={torch.cuda.is_available()})")
    try:
        import modelopt
        print(f"modelopt       : {getattr(modelopt, '__version__', 'unknown')}")
    except Exception as exc:
        print(f"modelopt       : import ok, version lookup failed: {exc}")
    import transformers
    print(f"transformers   : {transformers.__version__}")

    cfg = AutoConfig.from_pretrained(args.model)
    print(f"config loaded  : model_type={cfg.model_type} "
          f"architectures={getattr(cfg, 'architectures', None)}")
    AutoTokenizer.from_pretrained(args.model)
    print("tokenizer loaded: ok")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    if args.check:
        return run_check(args)

    # --- imports that require the isolated venv -------------------------------
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer, AutoConfig
    import modelopt.torch.quantization as mtq
    from modelopt.torch.opt import enable_huggingface_checkpointing
    from modelopt.torch.export import export_hf_checkpoint

    model_dir = Path(args.model)
    out_dir = Path(args.out)
    if not model_dir.is_dir():
        raise FileNotFoundError(f"--model directory not found: {model_dir}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for calibration; no GPU visible. "
                           "Use --check for a CPU-only feasibility test.")

    # ModelOpt needs HF checkpointing enabled so quantizer state round-trips
    # through the HF config/state files during export.
    enable_huggingface_checkpointing()

    device = f"cuda:{args.gpu}"
    torch.cuda.set_device(args.gpu)
    print(f"[1/5] loading {model_dir} in bfloat16 on {device} ...")
    model = AutoModelForImageTextToText.from_pretrained(
        str(model_dir),
        dtype=torch.bfloat16,
        device_map={"": args.gpu},
        low_cpu_mem_usage=True,
    )
    model.eval()
    model.config.use_cache = False

    print("[2/5] isolating the language model (vision tower stays BF16) ...")
    language_model, is_vlm = extract_language_model(model)
    print(f"      multimodal={is_vlm}, quantizing "
          f"{type(language_model).__name__}")

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    texts = load_calibration_texts(args)
    print(f"[3/5] calibrating with {min(args.calib_samples, len(texts))} "
          f"sample(s), batch={args.batch_size}, max_seq_len={args.max_seq_len}")
    forward_loop = build_forward_loop(language_model, tokenizer, texts, device, args)

    if args.quant == "fp8":
        quant_cfg = mtq.FP8_DEFAULT_CFG          # W8A8, per-tensor, static, "max"
    else:
        quant_cfg = mtq.NVFP4_DEFAULT_CFG        # W4A4, group 16, needs Blackwell
    if not hasattr(mtq, "NVFP4_DEFAULT_CFG") and args.quant == "nvfp4":
        raise RuntimeError("Installed ModelOpt has no NVFP4_DEFAULT_CFG; "
                           "upgrade nvidia-modelopt or use --quant fp8.")

    t0 = time.time()
    mtq.quantize(language_model, quant_cfg, forward_loop=forward_loop)
    print(f"      quantization + calibration done in {time.time() - t0:.1f}s")

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    print(f"[4/5] exporting ModelOpt HF checkpoint -> {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    # Export the FULL model for a VLM so the processor/config are preserved; the
    # disabled quantizers on the vision branch keep it BF16 in the export.
    export_hf_checkpoint(model, export_dir=str(out_dir))

    print("[5/5] copying tokenizer/processor files ...")
    copy_tokenizer_files(model_dir, out_dir)

    # Validate the artefacts TRT-LLM relies on for auto-detection.
    quant_file = out_dir / "hf_quant_config.json"
    if not quant_file.is_file():
        raise RuntimeError(f"export did not produce {quant_file}; TRT-LLM cannot "
                           "auto-detect the quantization.")
    quant = json.loads(quant_file.read_text())
    inner = quant.get("quantization", quant)
    print(f"      hf_quant_config: quant_algo={inner.get('quant_algo')} "
          f"kv_cache_quant_algo={inner.get('kv_cache_quant_algo')} "
          f"exclude_modules={len(inner.get('exclude_modules') or [])}")
    print("Done. Serve with scripts/serve_trtllm_fp8.sh")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # surface a clean message instead of a traceback wall
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
