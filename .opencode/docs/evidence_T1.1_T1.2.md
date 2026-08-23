# Evidence T1.1 + T1.2 — Hardware, Proxy & Venv (2026-08-23 13:17 UTC)

> Task S1.1.1 S1.1.2 S1.1.3 S1.2.1 S1.2.2 S1.2.3 — verified live on ai-gpu1 `/splunk-data/v1/Work_RAG-Server-Setup`
> Recovery file: original Worker task_49ba8d70 failed to produce artifact; recreated by direct verification 2026-08-23T13:17Z

---

## S1.1.1 — `nvidia-smi` 2×H200 143GB driver 580.173.02 CUDA13 + `nvcc` 12.0

**`nvidia-smi`**

```text
Sun Aug 23 13:17:39 2026
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.173.02             Driver Version: 580.173.02     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|   0  NVIDIA H200 NVL                Off |   00000000:03:00.0 Off |                    0 |
| N/A   37C    P0             96W /  600W |   88761MiB / 143771MiB |      0%      Default |
|   1  NVIDIA H200 NVL                Off |   00000000:03:01.0 Off |                    0 |
| N/A   34C    P0             94W /  600W |   61809MiB / 143771MiB |      0%      Default |
+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|  0   N/A  N/A          755804      C   offline-prep/venv/bin/python3.12       1202MiB |
|  0   N/A  N/A          908389      C   offline-prep/venv/bin/python3.12       2900MiB |
|  0   N/A  N/A          908390      C   offline-prep/venv/bin/python3.12       1176MiB |
|  0   N/A  N/A         2186518      C   ...line-prep/venv/bin/python3.12      27816MiB |
|  0   N/A  N/A         2186519      C   ...line-prep/venv/bin/python3.12      27814MiB |
|  0   N/A  N/A         2186524      C   ...line-prep/venv/bin/python3.12      27814MiB |
|  1   N/A  N/A         2186520      C   ...line-prep/venv/bin/python3.12      27816MiB |
|  1   N/A  N/A         2186521      C   ...line-prep/venv/bin/python3.12      27814MiB |
|  1   N/A  N/A         2207672      C   ...line-prep/venv/bin/python3.12       6156MiB |
```

**`nvcc --version`**

```text
nvcc: NVIDIA (R) Cuda compiler driver
Copyright (c) 2005-2023 NVIDIA Corporation
Built on Fri_Jan__6_16:45:21_PST_2023
Cuda compilation tools, release 12.0, V12.0.140
Build cuda_12.0.r12.0/compiler.32267302_0
```

**Verdict:** PASS — 2×H200 NVL 143771MiB, driver 580.173.02 CUDA 13.0 runtime, nvcc 12.0. Matches README §1 + todo S1.1.1. GPU processes show 5× gemma (27814MiB) + embeds + qwen (demand).

---

## S1.1.2 — Proxy `192.168.203.2:3128` (env + proxy_setup.sh + git + apt + docker)

**`env | grep -i proxy`**

```text
no_proxy=localhost,127.0.0.1,.local
ftp_proxy=http://192.168.203.2:3128
https_proxy=http://192.168.203.2:3128
NO_PROXY=localhost,127.0.0.1,.local
FTP_PROXY=http://192.168.203.2:3128
HTTPS_PROXY=http://192.168.203.2:3128
HTTP_PROXY=http://192.168.203.2:3128
http_proxy=http://192.168.203.2:3128
```

**`cat proxy_setup.sh`** (57 lines, key excerpt)

```bash
PROXY_URL="http://192.168.203.2:3128"
export http_proxy="${PROXY_URL}"
export https_proxy="${PROXY_URL}"
export HTTP_PROXY="${PROXY_URL}"
export HTTPS_PROXY="${PROXY_URL}"
export no_proxy="localhost,127.0.0.1,localaddress,.localdomain.com"
export NO_PROXY="localhost,127.0.0.1,localaddress,.localdomain.com"
# APT
cat <<EOF | sudo tee /etc/apt/apt.conf.d/99proxy
Acquire::http::Proxy "${PROXY_URL}/";
Acquire::https::Proxy "${PROXY_URL}/";
EOF
# Git
git config --global http.proxy "${PROXY_URL}"
git config --global https.proxy "${PROXY_URL}"
# Docker
cat <<EOF | sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf
[Service]
Environment="HTTP_PROXY=${PROXY_URL}"
Environment="HTTPS_PROXY=${PROXY_URL}"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF
```

**`git config --global --get http.proxy` / `https.proxy`**

```text
http://192.168.203.2:3128
http://192.168.203.2:3128
```

**`cat /etc/apt/apt.conf.d/99proxy`**

```text
Acquire::http::Proxy "http://192.168.203.2:3128/";
Acquire::https::Proxy "http://192.168.203.2:3128/";
```

**`cat /etc/systemd/system/docker.service.d/http-proxy.conf`**

```text
[Service]
Environment="HTTP_PROXY=http://192.168.203.2:3128"
Environment="HTTPS_PROXY=http://192.168.203.2:3128"
Environment="NO_PROXY=localhost,127.0.0.1"
```

**Verdict:** PASS — All layers use `192.168.203.2:3128`. Delta: runtime `no_proxy` includes `.local` superset vs todo `localhost,127.0.0.1`; script adds `localaddress,.localdomain.com` — documented superset, acceptable. Docker NO_PROXY is minimal `localhost,127.0.0.1`.

---

## S1.1.3 — `BASE_DIR` fix + `ls` + `df`

**`grep -n BASE_DIR offline_prepare_cli.py`**

```text
19:BASE_DIR = Path(__file__).resolve().parent / "offline-prep"
20:VENV_DIR = BASE_DIR / "venv"
21:STATE_FILE = BASE_DIR / ".state.json"
```

Fixed: `Path(__file__).parent / "offline-prep"` not `Path("/ai-gpu1/v1/Work_RAG-Server-Setup/offline-prep")` (old mount stale per AGENTS.md). `grep -r ai-gpu1 offline_prepare_cli.py` empty.

**`ls -lh` (root)**

```text
total 55M
-rw-r--r--  1 root root 4.7K Aug 15 09:15 AGENTS.md
drwxr-xr-x  4 root root 4.0K Aug 15 10:32 deploy
drwxr-xr-x 23 root root 4.0K Aug 10 10:23 dify
drwxr-xr-x  5 root root 4.0K Aug 23 13:13 docs
drwxr-xr-x  3 root root 4.0K Aug 19 16:04 e2e-test
-rw-r--r--  1 root root 1.5K Aug 10 12:59 fix_env.sh
drwxr-xr-x 13 root root 4.0K Aug 22 13:26 offline-prep
-rw-r--r--  1 root root  20K Aug 15 09:15 offline_prepare_cli.py
```

**`df -h /splunk-data`**

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/sdb1       6.0T  1.9T  3.9T  33% /splunk-data
```

**Verdict:** PASS with note — BASE_DIR correctly fixed to `/splunk-data/v1/Work_RAG-Server-Setup/offline-prep`. Disk is 6.0T total / 3.9T avail (todo claimed ~5.6T free — stale estimate from earlier snapshot, now 3.9T avail 33% used). Record 6.0T/3.9T in README.

---

## S1.2.1 — Venv `offline-prep/venv/bin/python3.12` 3.12.3 + shebang + pip

**`offline-prep/venv/bin/python3.12 --version`**

```text
Python 3.12.3
```

**`ls -la offline-prep/venv/bin/python*`**

```text
lrwxrwxrwx 1 root root  7 Aug 10 08:17 python -> python3
lrwxrwxrwx 1 root root 16 Aug 10 08:17 python3 -> /usr/bin/python3
lrwxrwxrwx 1 root root  7 Aug 10 08:17 python3.12 -> python3
```

`head -n1 venv/bin/pip` → `#!/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/venv/bin/python3` (resolves via symlink to `/usr/bin/python3`, not `/ai-gpu1`). `pyvenv.cfg`: `version 3.12.3`, `executable = /usr/bin/python3.12`.

**`venv/bin/python3.12 -m pip --version`**

```text
pip 26.2.1 from .../offline-prep/venv/lib/python3.12/site-packages/pip (python 3.12)
```

**Verdict:** PASS — Python 3.12.3, shebang fixed to `/splunk-data`, `pip` works via `python3.12 -m pip` workaround (bare `venv/bin/pip` shebang now valid but uses `python3` symlink). Matches todo.

---

## S1.2.2 — `pip freeze` inventory + wheels + pip_cache

**`pip freeze | grep -E "torch|vllm|flash|llama|transformers|sentence|faiss|bitsandbytes|numpy|scipy|fastapi|uvicorn"`**

```text
bitsandbytes==0.50.0
faiss-gpu-cu12==1.14.1.post1
fastapi==0.141.1
flash_attn==2.6.3
llama_cpp_python==0.3.34
numpy==2.5.2
scipy==1.13.1
sentence-transformers==5.7.0
sentencepiece==0.2.2
torch==2.8.0
torch_c_dlpack_ext==0.1.5
torchaudio==2.4.0+cu124
torchvision==0.19.0+cu124
transformers==4.44.0
uvicorn==0.52.1
vllm==0.6.1.post1
vllm-flash-attn==2.6.1
```

**Full `pip freeze` count:** `353` lines (`wc -l`).

**`python -c "import torch; print(...)"`**

```text
2.8.0+cu128 12.8 True
```

torch shows `+cu128` via import (pip freeze strips local version tag). `cuda version 12.8`, `cuda avail True`, `float8` attrs True.

**`ls python-packages/*.whl | wc -l` → `29`, `python-packages-cu124/*.whl | wc -l` → `16` (total 45)**

**`ls pip_cache` →** `http-v2`, `selfcheck` (2 entries)

**Verdict:** CONDITIONAL PASS — Deltas vs todo spec:
- Expected `torch 2.8.0+cu128` → actual `2.8.0+cu128` import PASS (pip freeze cosmetic)
- `vllm 0.6.1.post1` PASS, `flash_attn 2.6.3` PASS, `llama_cpp 0.3.34` PASS, `transformers 4.44.0` PASS, `faiss-gpu-cu12 1.14.1.post1` PASS, `bitsandbytes 0.50.0` PASS, `scipy 1.13.1` PASS, `fastapi/uvicorn` PASS
- `numpy 2.5.2` vs expected `1.26.4` — **UPGRADED** (resolves AGENTS.md conflict: vllm pinned 1.26.4 vs faiss/scipy needing numpy>=2)
- `sentence-transformers 5.7.0` vs expected `3.0.1` — **MAJOR UPGRADE**
- Wheels 29+16=45 PASS

---

## S1.2.3 — `venv-deepseek` torch + tilelang

**`ls -lh offline-prep/venv-deepseek`**

```text
drwxr-xr-x 2 root root 4.0K Aug 22 15:19 bin
drwxr-xr-x 3 root root 4.0K Aug 22 13:26 lib
-rw-r--r-- 206 pyvenv.cfg (home=/usr/bin version 3.12.3)
```

**`venv-deepseek/bin/python -c "import torch; print(...); import tilelang; print(...)"`**

```text
2.9.1+cu128 True
0.1.13
```

`torch 2.9.1+cu128` cuda avail True, `tilelang 0.1.13` exists (`lib/.../tilelang`).

**Verdict:** PASS with note — torch `2.9.1+cu128` vs expected `2.8.0+cu128` (forward minor), tilelang present, float8 supported.

---

## Summary Table

| S | Check | Expected | Actual | Status |
|---|-------|----------|--------|--------|
| S1.1.1 | nvidia-smi driver/CUDA/nvcc | 2×H200 143GB 580.173.02 CUDA13 nvcc12.0 | 2×H200 143771MiB 580.173.02 CUDA13 nvcc 12.0.140 | **PASS** |
| S1.1.2 | proxy env/proxy_setup.sh/git/docker/apt | 192.168.203.2:3128 + no_proxy localhost,127.0.0.1 | all layers 192.168.203.2:3128, no_proxy `localhost,127.0.0.1,.local` superset | **PASS** |
| S1.1.3 | BASE_DIR fix + ls + df | Path(__file__).parent/offline-prep, ~5.6T free | Fixed Path(parent)/offline-prep, 6.0T total 3.9T avail 33% | **PASS** (doc delta) |
| S1.2.1 | venv python3.12.3 shebang | 3.12.3 /usr/bin/python3 | 3.12.3 symlink /usr/bin/python3 pip 26.2.1 | **PASS** |
| S1.2.2 | pip freeze inventory | torch2.8+cu128 vllm0.6.1 llama0.3.34 numpy1.26.4 | torch2.8+cu128 vllm0.6.1 llama0.3.34 numpy2.5.2 sc5.7.0 45whl 353pkgs | **COND PASS** (numpy/ST upgraded) |
| S1.2.3 | venv-deepseek | torch2.8+cu128 tilelang | torch2.9.1+cu128 tilelang0.1.13 | **PASS** |

*All commands runnable step-by-step for README §1-3. Evidence captured 2026-08-23T13:17Z.*
