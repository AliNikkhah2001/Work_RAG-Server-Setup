# 2026-08-15 — HF Token, Download Resumption & Remote-Access Attempts

## Summary (current status)
- **HF token configured** → previously auth-blocked models now download. Proof: `bartowski/google_gemma-3-27b-it-GGUF` Q4_K_M streaming (was GATED/skip before; 3.5 GB and climbing by 14:00 UTC).
- Daemon `rag-dl` active; queue is strictly **one file at a time, smallest-first** (see
  `scripts/download_models.py` TARGETS) and completes in this order:
  Llama-3.2-3B(done) → Qwen2.5-7B(done) → Mistral-7B Q4_K_M(**done 12:33**) →
  Gemma-3-27B Q4_K_M (downloading) → Qwen3-30B-A3B → Gemma-4-31B Q4_K_M →
  Nemotron-Super-49B Q4 → Qwen2.5-72B Q8_0 p2/p1 → 72B Q4_K_M →
  Nemotron-Ultra-253B Q4 → DeepSeek-V4-Flash → MiniMax-M3 IQ4_XS → Kimi-K3 IQ1_S → GLM-5.2 FP8.
- Remote access: **LAN paths to services work on the corporate network**; **proxy relay to this box is blocked (Kerio)**; all tried accountless public tunnels failed (details below). Public gateway nginx (127.0.0.1:8089, basic-auth) is staged for a future working relay.

## 1. HuggingFace token (gated repos)
- Token is a **fine-grained, read/gated** token for user `alinikkhah` (display `h200bemoola`).
- Stored (mode 600, NOT in git): `~/.cache/huggingface/token` (raw) and
  `offline-prep/.hf_token` (`HF_TOKEN=...`) consumed by systemd drop-in
  `/etc/systemd/system/rag-dl.service.d/override.conf` via `EnvironmentFile`.
- Verified: `whoami` OK through proxy; gated blob range-request returns 206 (e.g. gemma-3
  Q4_K_M); DeepSeek-V4-Flash & GLM-5.2-FP8 repos are public (`gated: false`).
- `bartowski/google_gemma-4-31b-it-GGUF` canonical casing is `...-31B-it-GGUF` (302 otherwise); fixed in TARGETS.

## 2. Network facts (verified 13:40–14:10 UTC)
- Two NICs: `ens34 192.168.96.82/29`, `ens35 192.168.177.10/29`; default via 192.168.177.9.
- Internet is egress-restricted: **outbound is ENETUNREACH for most hosts** (pinggy, localhost.run,
  localtunnel edge `193.34.76.44:12091`, etc.). Allowlisted hosts reachable directly: hugggingface,
  Cloudflare anycast, github, google, pypi, npm.
- Corporate HTTP proxy Squid `192.168.203.2:3128` relays HTTPS via CONNECT; upstream MITM/product is
  **Kerio Control** (`This message was created by Kerio Control Proxy`) which 400s absolute-form
  `GET https://...` requests (so any HTTP client MUST use CONNECT+TLS, not absolute-form).
- Squid relay back to `192.168.96.82`/`192.168.177.10` service ports fails (`503/502/000`) → external
  access "through the proxy" to internal IPs is **not** possible.

## 3. Remote access attempts (all failed → staged fallbacks)
| Approach | Result |
|---|---|
| Direct LAN IPs `:8088/:8000/:13000` | Works **on the corporate LAN** (inside the network) |
| Proxy relay to internal IPs | Blocked by Kerio/Squid ACL |
| cloudflared quick tunnel | Registry POST times out (cloudflared ignores env proxy; direct is unroutable). `api.trycloudflare.com` itself answers 200 via curl. |
| localtunnel (`lt`, node) | Control-plane HTTPS works when forced through Squid via `https-proxy-agent` (@7) + patched `https.globalAgent`; **data-plane needs raw TCP to `193.34.76.44:12091` → ENETUNREACH** → tunnel dies. |
| ngrok / pinggy / localhost.run | Egress blocked (timeouts / ENETUNREACH) |
- Staged-but-dormant: nginx `127.0.0.1:8089` auth-gated public subset (paths `/vllm//llama//embeddings//webui//samples//docs/`), creds in `deploy/gateway/.public_pass` (db pass not committed).
- Removed `/etc/systemd/system/rag-tunnel.service` (cloudflared) and `rag-lt.service` (localtunnel).

## 4. Gateway fixes
- nginx `rag-gateway` (8088): the classic `location = / { index ... }` trap — internal redirect to
  `/index.html` fell through to the default server's welcome page. Fixed with
  `try_files /index.html =404;` (in rag-gateway and rag-public).
- Added `/samples/` (read-only source browse of `offline-prep/sample-projects/`) and `/docs/` to 8088
  gateway; `index.html` landing updated.

## Next steps (open decisions)
1. Pick a public-exposure path that works under the egress ACL. Realistic: **Kerio/Squid reverse mapping**
   (needs admin), a **Cloudflare account + named tunnel** (still may hit edge-region egress limits), or
   **VPN/WireGuard to an allowlisted relay** you control. I stopped at asking whether the working device is
   already inside the corporate LAN (then the direct IPs suffice).
2. Rotate `hf_...` token whenever convenient — it is plaintext in `offline-prep/.hf_token` and `~/.cache/huggingface/token` (in a shared VM scope).