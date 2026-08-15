# Guide 07 — The `rag-dl` Download Daemon

> [Back to index](../README.md)

Downloads run as a **systemd service** so they survive crashes, interrupts, and reboots —
no tmux babysitting required.

## Status & common ops

```bash
systemctl status rag-dl          # service state + current log tail
systemctl is-active rag-dl       # expect: active
journalctl -u rag-dl --no-pager -n 50
tail -f offline-prep/logs/dl_daemon.out      # unlimited retries/resumes
systemctl restart rag-dl         # restart the stream (safe: resumes partials)
systemctl stop rag-dl            # pause downloads (safe anytime)
```

## How it works

- Runner: `scripts/download_models.py --daemon` — concatenates all `TARGETS` sequentially.
- **`--daemon` semantics:** infinite attempts per target + automatic **resume** of
  `.incomplete` chunks (huggingface_hub range-requests), a re-verify pass over the whole catalog
  after everything completes, and **auth-block detection** — gated repos (e.g.
  `bartowski/google_gemma-3-27b-it-GGUF`) log `AUTH-BLOCKED` and are skipped instead of spinning.
- `Restart=always` + `RestartSec=20`: if the python process is ever killed (OOM, reboot, oops),
  systemd relaunches it and it resumes from disk.
- Environment baked into the unit: `http(s)_proxy=http://192.168.203.2:3128`,
  `HF_HUB_DISABLE_XET=1` (proxy can't do XET), `HF_HUB_ENABLE_HF_TRANSFER=0`.
- Unit file: `/etc/systemd/system/rag-dl.service` (enabled at boot).

## Adding a model to the queue

Edit `TARGETS` in `scripts/download_models.py`:

```python
("Qwen/Qwen3-32B-GGUF", ["Qwen3-32B-Q4_K_M.gguf"]),
```

…then `systemctl restart rag-dl`. New entries pick up on the next pass; partials are reused.

## Add `HF_TOKEN` when a gated repo is required

```bash
huggingface-cli login            # stores token; daemon picks it up on next pass
# or:  environment=HF_TOKEN=hf_...  in /etc/systemd/system/rag-dl.service
```

## Bandwidth reality

The upstream Squid proxy sustains ≈230 KB/s. A single sequential stream is intentional — concurrent
streams multiply retry failures. Expect: 72B ≈ 2 weeks; the full ~2 TB catalog ≈ months. Watch
`scripts/progress_report.py --watch` for per-model bars; count `*.incomplete` not `*.gguf` for
in-flight reality.

## Cleanup tip

Stale 0-byte `*.incomplete` chunk files accumulate after retries. Periodically:

```bash
find offline-prep/models/huggingface -path "*/.cache/huggingface/download" -name "*.incomplete" -size 0 -delete
```