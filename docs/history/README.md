# Execution History

Detailed, dated record of every installation and notable finding during this RAG server setup. This is the authoritative history — `.state.json`, logs, and reports are raw artifacts and frequently stale.

## Files

| File | Covers |
|------|--------|
| `001_2026-08-10_initial_offline_prep.md` | First automated prep run: docker pulls, wheel downloads, model downloads, clones, failures, report |
| `002_2026-08-11_manual_installs_and_docker.md` | Manual installs (vllm, flash-attn, llama-cpp, sglang) and docker healthchecks |
| `../findings.md` | Environment facts, gotchas, and operational quirks |

## Rules

- Add a new `NNN_YYYY-MM-DD_<topic>.md` per work day/session. Append to the day's file if one exists.
- Record exact commands run, versions, and outcomes (success/failure).
- Keep a 5-10 line "Current status" summary at the top of each file.
- When a file exceeds ~300 lines, move older detail into an archive section/file and summarize. Execution history must stay readable and current.
- Update this index when adding files.
