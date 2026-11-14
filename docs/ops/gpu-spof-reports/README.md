# GPU SPOF recovery reports

Generated on the **production GPU host** by:

```bash
# from umbrella clone on the GPU server
bash scripts/gpu_spof_full_recover.sh
# or
bash components/server-setup/scripts/gpu_spof_recover_report.sh
```

Each subdirectory is one run (`UTC timestamp + hostname`). Open that run’s `REPORT.md` for status, health matrix, ingest counts, error signatures, E2E QA, and screenshots.

The script pushes a branch `ops/gpu-spof-<run_id>` (and opens a PR when `gh` is available) so you can inspect evidence from GitHub without SSH.
- [20261114T092101Z-Ali-Nikkhah-4](./20261114T092101Z-Ali-Nikkhah-4/REPORT.md) — **HEALTHY** — QA 2/2 — sigs 0
