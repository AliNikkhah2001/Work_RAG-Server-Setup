# Mission: Run 4 RAG Projects End-to-End, Benchmark, Compare, Report & Push

Repo: /splunk-data/v1/Work_RAG-Server-Setup (remote: github.com/AliNikkhah2001/Work_RAG-Server-Setup)

## M1: Environment Recon & Prep | status: in_progress
### T1.1: Verify local LLM (gemma-4-31b @8080) + embedding (e5-small @8001) | agent:Worker
- [ ] S1.1.1: Test LLM chat completion API works | size:S
- [ ] S1.1.2: Test embeddings API works | size:S

### T1.2: Prepare common RAG test corpus + Q&A set | agent:Worker
- [ ] S1.2.1: Create test documents (tech/multi-topic corpus) | size:M
- [ ] S1.2.2: Create 10 Q&A pairs with ground truth | size:M
- [ ] S1.2.3: Install playwright browser automation (background) | size:M

## M2: LightRAG E2E Test | status: in_progress
### T2.1: LightRAG (already running @9621) | agent:Worker
- [ ] S2.1.1: Verify /health & ingest test docs | size:S
- [ ] S2.1.2: Run 10 retrieval+generation queries, measure latency | size:M
- [ ] S2.1.3: Verify answers grounded in corpus (faithfulness) | size:M
- [ ] S2.1.4: Verify frontend/API availability | size:S

## M3: Dify E2E Test | status: pending
### T3.1: Start Dify (docker images present) | agent:Worker
- [ ] S3.1.1: Start docker compose (dify/docker) | size:L
- [ ] S3.1.2: Configure local LLM + embedding via API | size:M
- [ ] S3.1.3: Create knowledge base + upload corpus | size:M
- [ ] S3.1.4: Run 10 RAG queries, measure retrieval+generation | size:M
- [ ] S3.1.5: Verify frontend (web UI) loads | size:S

## M4: AnythingLLM E2E Test | status: pending
### T4.1: AnythingLLM (node_modules present) | agent:Worker
- [ ] S4.1.1: Start server (yarn/prod) | size:M
- [ ] S4.1.2: Configure local LLM + embedding | size:M
- [ ] S4.1.3: Create workspace + upload corpus | size:M
- [ ] S4.1.4: Run 10 RAG queries, measure | size:M
- [ ] S4.1.5: Verify frontend loads | size:S

## M5: RAGFlow E2E Test | status: pending
### T5.1: RAGFlow (no venv - assess feasibility) | agent:Worker
- [ ] S5.1.1: Attempt venv + requirements install (background) | size:L
- [ ] S5.1.2: If runnable: start server, ingest, query, verify | size:L
- [ ] S5.1.3: If not runnable: document blocker with evidence | size:S

## M6: Benchmarks & Datasets | status: pending
### T6.1: Identify + fetch RAG datasets/benchmarks | agent:Planner
- [ ] S6.1.1: Research available RAG benchmarks (CRAG, RGB, MS MARCO, FiQA, MultiHop, Persian) | size:M
- [ ] S6.1.2: Download/use available eval sets (local first) | size:M
- [ ] S6.1.3: Run standardized eval on each project (retrieval metrics: hit-rate/MRR; gen: faithfulness) | size:L

## M7: Comparison & Report | status: pending
### T7.1: Cross-project comparison | agent:Worker
- [ ] S7.1.1: Collect metrics (retrieval, gen quality, latency, resources, setup) | size:M
- [ ] S7.1.2: Generate comparison tables + charts | size:M

### T7.2: GitHub README report + push | agent:Worker
- [ ] S7.2.1: Write comprehensive README (RAG-E2E-Benchmark) | size:L
- [ ] S7.2.2: Commit + push to dedicated branch (rag-e2e-benchmark) | size:M

## M8: Final Verification | status: pending
### T8.1: Reviewer full verification | agent:Reviewer
- [ ] S8.1.1: Verify all projects tested with evidence | size:M
- [ ] S8.1.2: Verify report exists + branch pushed | size:S
