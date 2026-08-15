# Guide 01 — Hardware & Environment

> [Back to index](../README.md)

## Compute

| Component | Detail |
|---|---|
| Hostname / OS | `ai-gpu1`, Ubuntu 24.04 (VMware VM) |
| **GPU** | **2× NVIDIA H200 NVL**, 140.4 GiB each (**280.8 GiB total**); device `233B`, NVLink `NV18` interconnect |
| GPU interconnect | NVLink (18 links, bonded) — GPUs on one NUMA node, both off CPU 0-29 |
| VRAM free (idle) | ~281 GiB (vllm holds ~71 GiB on GPU-0 while serving the 7B) |
| **RAM** | **1,007 GB total, ~962 GB available**, single NUMA node 0, 30 cores pinned |
| **CPU** | Intel Xeon Platinum 8580 (Emerald Rapids), **30 vCPU** |
| Driver / CUDA | NVIDIA driver **580.173.02**, runtime **CUDA 13.0**, `nvcc` host CUDA 12.0 |
| Disk | `/` 48 G (22 G used, 49%); **`/splunk-data` 6.0 T (5.5 T free)** on `/dev/sdb1` |
| Network | `ens34` = `192.168.96.82/29`, `ens35` = `192.168.177.10/29`; docker bridges `172.17.0.1`, `172.18.0.1` |
| Firewall | ufw/iptables **inactive** — all ports open, services bind `0.0.0.0` |

## Outbound network

All outbound traffic must go through the corporate Squid proxy:

```
http://192.168.203.2:3128
```

Configured for shell, apt, git, docker daemon, pip, and HuggingFace by `proxy_setup.sh`.
When testing local HTTP from any shell, the `http_proxy` env var would route through squid and
return a 503 — use `curl --noproxy '*'`.

## Disk layout

| Mount | Device | Size | Used | Used for |
|---|---|---|---|---|
| `/` | `ubuntu--vg-ubuntu--lv` | 48 G | 22 G (49%) | OS; docker data-root now here but empty (see Guide 04) |
| `/splunk-data` | `/dev/sdb1` | 6.0 T | 166 G (3%) | all working data: models, wheels, images, this repo |

The docker + containerd data-roots were relocated **off** the root partition onto
`/splunk-data/v1/` (frees ~23 G; root went 100% → 49%). Stale `/ai-gpu1/v1/*` dirs removed.

## GPU fit quick math

- Weights that fit entirely in VRAM (281 GiB): anything ≤ ~250 GiB (Nemotron Ultra 253B Q4,
  MiniMax-M3 IQ4_XS, DeepSeek-V4-Flash, 72B).
- Anything larger (Kimi K3 594 G, GLM-5.2 755 G): **mmap + MoE-in-RAM** via llama.cpp
  `--n-cpu-moe` — 1 TB RAM makes this viable. See [Guide 06](06-model-runnability-fit.md).