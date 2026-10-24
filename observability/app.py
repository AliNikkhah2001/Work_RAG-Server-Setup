from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import httpx, os, pathlib, sys
# add manager path for registry
sys.path.insert(0, "/splunk-data/v1/Work_RAG-Server-Setup")
try:
    from llm_inference_manager.app import MODEL_REGISTRY
except:
    MODEL_REGISTRY = {}

app = FastAPI(title="Observability :16333", version="1.0")

MANAGER = os.getenv("MANAGER_URL", "http://127.0.0.1:9000")
PROM = os.getenv("PROM_URL", "http://127.0.0.1:19090")
JAEGER = os.getenv("JAEGER_URL", "http://127.0.0.1:16686")
GRAFANA = os.getenv("GRAFANA_URL", "http://127.0.0.1:13001")

HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Observability :16333 — Ratings & Traces</title>
<style>
:root{--bg:#0f1419;--panel:#161b22;--border:#21262d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--ok:#3fb950;--warn:#d29922;--err:#f85149}
*{box-sizing:border-box}body{margin:0;font-family:system-ui;background:var(--bg);color:var(--text)}
header{position:sticky;top:0;background:#010409;border-bottom:1px solid var(--border);padding:10px 18px;display:flex;gap:12px;align-items:center}
.badge{padding:3px 8px;border-radius:999px;border:1px solid var(--border);font-size:12px}
.ok{color:var(--ok);border-color:var(--ok)} .err{color:var(--err)} .warn{color:var(--warn)}
.tabs{display:flex;gap:6px;padding:12px 18px;background:var(--panel);border-bottom:1px solid var(--border);overflow:auto}
.tab{padding:8px 14px;border-radius:8px;border:1px solid var(--border);background:#1c2128;cursor:pointer;color:var(--text)} .tab.active{background:var(--accent);color:#010409}
.wrap{padding:18px;max-width:1400px;margin:0 auto}
.card{background:#1c2128;border:1px solid var(--border);border-radius:12px;padding:14px;margin-top:14px}
.muted{color:var(--muted);font-size:12px} code{background:#0d1117;padding:2px 6px;border-radius:6px;border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;font-size:13px} th,td{padding:7px 8px;border-bottom:1px solid var(--border);text-align:left} th{color:var(--muted)}
.kv{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px dashed var(--border)}
.log{background:#010409;border:1px solid var(--border);border-radius:8px;padding:10px;font-family:monospace;font-size:12px;white-space:pre-wrap;max-height:320px;overflow:auto}
</style></head><body>
<header><h1 style="margin:0;font-size:18px">📊 Observability :16333</h1><span id="health" class="badge">checking…</span><span class="muted">Manager <a href="http://192.168.96.82:9000" target="_blank" style="color:var(--accent)">:9000</a> · <a href="http://192.168.96.82:13001" target="_blank" style="color:var(--accent)">Grafana :13001</a> · <a href="http://192.168.96.82:16686" target="_blank" style="color:var(--accent)">Jaeger :16686</a></span><span id="panelsHealth" class="badge" style="margin-left:auto">panels: checking…</span></header>
<div class="tabs">
<button class="tab active" data-t="ratings" onclick="switchTab('ratings')">Ratings (benchmark)</button>
<button class="tab" data-t="hist" onclick="switchTab('hist')">Histograms & %</button>
<button class="tab" data-t="times" onclick="switchTab('times')">Over time</button>
<button class="tab" data-t="summary" onclick="switchTab('summary')">Summary pie</button>
<button class="tab" data-t="panels" onclick="switchTab('panels')">Panels & Prometheus</button>
<button class="tab" data-t="traces" onclick="switchTab('traces')">Traces (OTEL/Jaeger)</button>
</div>
<div class="wrap">
<div id="tab-ratings"><div class="card"><h3>Model Ratings — benchmark_mean (11 models)</h3><div id="ratingsTbl" class="muted">loading…</div><div class="muted">Source <code>MODEL_REGISTRY benchmark_mean</code> · Higher = better Persian eval · Champion <code>gemma-4-31b 0.663</code></div></div><div class="grid" style="display:grid;gap:14px;grid-template-columns:1fr 1fr;margin-top:14px"><div class="card"><h3>Ratings bar (benchmark_mean)</h3><svg id="ratingsSvg" width="100%" height="220" style="background:#0d1117;border:1px solid var(--border);border-radius:8px"></svg></div><div class="card"><h3>Notes</h3><div class="muted">Ratings from <code>offline-prep/models</code> eval logs <code>logs/evalp*.json</code> · Quant <code>Q4_K_M</code> · Context 8192 · Size GB · See <code>/api/ratings</code></div></div></div></div>
<div id="tab-hist" style="display:none"><div class="card"><h3>Latency Histograms — per-sample & cumulative %</h3><div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0"><button class="tab" onclick="loadHist(24)">24h</button><button class="tab" onclick="loadHist(168)">7d</button><button class="tab" onclick="loadHist(720)">30d</button><button class="tab" onclick="loadHist(8760)">1y</button><span id="histMeta" class="muted"></span></div><svg id="histSvg" width="100%" height="160" style="background:#0d1117;border:1px solid var(--border);border-radius:8px"></svg><div id="histLegend" class="muted"></div><div id="histPct" class="muted"></div></div><div class="card"><h3>Per-model p50/p95/p99</h3><div id="histByModel" class="muted"></div></div></div>
<div id="tab-times" style="display:none"><div class="card"><h3>Requests over time — avg + p95 + blocked/error stacked</h3><div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0"><button class="tab" onclick="loadTimes(24)">24h</button><button class="tab" onclick="loadTimes(168)">7d</button><button class="tab" onclick="loadTimes(720)">30d</button><span id="timesMeta" class="muted"></span></div><svg id="timeSvg" width="100%" height="160" style="background:#0d1117;border:1px solid var(--border);border-radius:8px"></svg><div id="timeLegend" class="muted"></div></div></div>
<div id="tab-summary" style="display:none"><div class="card"><h3>Global Summary — total / success / blocked / error</h3><div id="summaryBox" class="muted">loading…</div><div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-top:8px"><svg id="pieSvg" width="180" height="180" style="background:#0d1117;border:1px solid var(--border);border-radius:50%"></svg><div id="pieLegend" class="muted"></div><svg id="modelBarSvg" width="360" height="180" style="background:#0d1117;border:1px solid var(--border);border-radius:8px"></svg></div></div></div>
<div id="tab-panels" style="display:none"><div class="card"><h3>Panels & Prometheus</h3><div style="display:flex;gap:6px;flex-wrap:wrap;margin:8px 0"><button class="tab" onclick="loadPanels()">Refresh</button><button class="tab" onclick="window.open('http://192.168.96.82:19090/prometheus','_blank')">Prometheus UI</button><button class="tab" onclick="window.open('http://192.168.96.82:13001','_blank')">Grafana</button><button class="tab" onclick="window.open('http://192.168.96.82:16686','_blank')">Jaeger</button></div><div id="panelsTbl" class="muted">loading…</div><div id="promTbl" class="muted" style="margin-top:8px"></div></div></div>
<div id="tab-traces" style="display:none"><div class="card"><h3>Traces — OTEL → Jaeger + fallback :3000</h3><div style="display:flex;gap:6px;margin-bottom:8px"><input id="traceId" placeholder="request_id" style="flex:1"><button class="tab" onclick="loadTraces()">Recent</button><button class="tab" onclick="loadTrace()">Show</button></div><div id="tracesTbl" class="muted">loading…</div><div id="traceDetail" class="log" style="margin-top:8px;min-height:120px">select a trace</div><svg id="traceGantt" width="100%" height="100" style="background:#0d1117;border:1px solid var(--border);border-radius:8px;margin-top:8px"></svg></div></div>
</div>
<script>
function switchTab(t){document.querySelectorAll('[id^="tab-"]').forEach(e=>e.style.display='none');document.getElementById('tab-'+t).style.display='block';document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));document.querySelector(`.tab[data-t="${t}"]`)?.classList.add('active'); if(t==='ratings') loadRatings(); if(t==='hist') loadHist(8760); if(t==='times') loadTimes(168); if(t==='summary') loadSummary(8760); if(t==='panels') loadPanels(); if(t==='traces') loadTraces();}
async function fetchJSON(u){const r=await fetch(u); if(!r.ok) throw new Error(r.status+' '+await r.text().then(s=>s.slice(0,300))); return r.json()}
async function loadRatings(){try{const j=await fetchJSON('/api/ratings'); document.getElementById('ratingsTbl').innerHTML=`<table><tr><th>model</th><th>creator</th><th>params</th><th>quant</th><th>benchmark_mean</th><th>size_gb</th><th>status</th></tr>`+j.map(m=>`<tr><td><code>${m.id}</code></td><td>${m.creator}</td><td>${m.params}</td><td>${m.quant}</td><td style="color:${m.benchmark_mean>0.6?'#3fb950':m.benchmark_mean>0.4?'#d29922':'var(--muted)'}"><b>${m.benchmark_mean}</b></td><td>${m.size_gb}</td><td>${m.status}</td></tr>`).join('')+`</table>`; drawRatings(j);}catch(e){document.getElementById('ratingsTbl').textContent='error '+e.message}}
function drawRatings(models){const svg=document.getElementById('ratingsSvg'); if(!svg) return; const w=svg.clientWidth||560, h=220, pad=20; svg.setAttribute('viewBox',`0 0 ${w} ${h}`); svg.innerHTML=''; const max=Math.max(...models.map(m=>m.benchmark_mean||0),0.7); models.slice(0,11).forEach((m,i)=>{const bw=(m.benchmark_mean||0)/max*(w-pad*40); const y=pad+i*18; const rect=document.createElementNS('http://www.w3.org/2000/svg','rect'); rect.setAttribute('x',pad+80); rect.setAttribute('y',y); rect.setAttribute('width',bw); rect.setAttribute('height',12); rect.setAttribute('fill', m.benchmark_mean>0.6?'#3fb950':m.benchmark_mean>0.4?'#d29922':'#8b949e'); svg.appendChild(rect); const txt=document.createElementNS('http://www.w3.org/2000/svg','text'); txt.setAttribute('x',pad); txt.setAttribute('y',y+10); txt.setAttribute('fill','#e6edf3'); txt.setAttribute('font-size','9'); txt.textContent=m.id.slice(0,14); svg.appendChild(txt); const v=document.createElementNS('http://www.w3.org/2000/svg','text'); v.setAttribute('x',pad+82+bw); v.setAttribute('y',y+10); v.setAttribute('fill','#8b949e'); v.setAttribute('font-size','8'); v.textContent=(m.benchmark_mean||0).toFixed(3); svg.appendChild(v);});}
function drawHist(svg,counts){const w=svg.clientWidth||560,h=120,pad=10; svg.setAttribute('viewBox',`0 0 ${w} ${h}`);const max=Math.max(...counts,1);svg.innerHTML='';counts.forEach((c,i)=>{const bh=c/max*(h-pad*2);const bw=(w-pad*2)/counts.length-2;const x=pad+i*(bw+2),y=h-pad-bh;const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('x',x);r.setAttribute('y',y);r.setAttribute('width',bw);r.setAttribute('height',bh);r.setAttribute('fill','#58a6ff');svg.appendChild(r);});}
async function loadHist(hours){try{const j=await fetchJSON(`/api/histogram?hours=${hours}`);drawHist(document.getElementById('histSvg'),j.counts||[]);document.getElementById('histLegend').textContent=`p50 ${j.p50_ms} p95 ${j.p95_ms} p99 ${j.p99_ms} total ${j.total}`;document.getElementById('histPct').textContent=j.counts_pct?`% ${j.counts_pct.slice(0,8).join(', ')}`:'';const by=j.by_model||{};document.getElementById('histByModel').innerHTML=Object.entries(by).map(([m,v])=>`${m} p95 ${v.p95}`).join(' · ') || 'no per-model';document.getElementById('histMeta').textContent=hours+'h';}catch(e){document.getElementById('histLegend').textContent='error '+e.message}}
async function loadTimes(hours){try{const j=await fetchJSON(`/api/timeseries?hours=${hours}&bucket_min=60`);const svg=document.getElementById('timeSvg');const s=j.series||[];if(!s.length){document.getElementById('timeLegend').textContent='no data';return;}const w=svg.clientWidth||560,h=120,pad=14;svg.setAttribute('viewBox',`0 0 ${w} ${h}`);const max=Math.max(...s.map(x=>x.avg_ms),1);svg.innerHTML='';s.forEach((pt,i)=>{const x=pad+i*(w-pad*2)/Math.max(s.length-1,1);const y=h-pad-pt.avg_ms/max*(h-pad*2);if(i>0){const prev=s[i-1];const xp=pad+(i-1)*(w-pad*2)/Math.max(s.length-1,1);const y2=h-pad-prev.avg_ms/max*(h-pad*2);const l=document.createElementNS('http://www.w3.org/2000/svg','line');l.setAttribute('x1',xp);l.setAttribute('y1',y2);l.setAttribute('x2',x);l.setAttribute('y2',y);l.setAttribute('stroke','#3fb950');l.setAttribute('stroke-width','2');svg.appendChild(l);}const c=document.createElementNS('http://www.w3.org/2000/svg','circle');c.setAttribute('cx',x);c.setAttribute('cy',y);c.setAttribute('r','2');c.setAttribute('fill','#3fb950');svg.appendChild(c);});document.getElementById('timeLegend').textContent=s.length+' points';document.getElementById('timesMeta').textContent=hours+'h';}catch(e){document.getElementById('timeLegend').textContent='error '+e.message}}
async function loadSummary(hours){try{const j=await fetchJSON(`/api/summary?hours=${hours}`);document.getElementById('summaryBox').innerHTML=`Total ${j.total} Success ${(j.success_rate*100).toFixed(1)}% Blocked ${(j.blocked_rate*100).toFixed(1)}% Error ${(j.error_rate*100).toFixed(1)}%`;const svg=document.getElementById('pieSvg');if(svg){const total=Object.values(j.by_status).reduce((a,b)=>a+b,0)||1;let acc=0;svg.setAttribute('viewBox','0 0 100 100');svg.innerHTML='';Object.entries(j.by_status).forEach(([k,v])=>{const pct=v/total;const ang=pct*360;const large=ang>180?1:0;const x1=50+40*Math.cos((acc*360-90)*Math.PI/180),y1=50+40*Math.sin((acc*360-90)*Math.PI/180);acc+=pct;const x2=50+40*Math.cos((acc*360-90)*Math.PI/180),y2=50+40*Math.sin((acc*360-90)*Math.PI/180);const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d',`M50,50 L${x1},${y1} A40,40 0 ${large},1 ${x2},${y2} Z`);p.setAttribute('fill',k==='success'?'#3fb950':k==='blocked'?'#d29922':'#f85149');svg.appendChild(p);});}}catch(e){document.getElementById('summaryBox').textContent='error '+e.message}}
async function loadPanels(){try{const p=await fetchJSON('/api/panels');document.getElementById('panelsTbl').innerHTML=`<table><tr><th>panel</th><th>status</th><th>code</th></tr>`+Object.entries(p).map(([k,v])=>`<tr><td>${k}</td><td>${v.status}</td><td>${v.code||''}</td></tr>`).join('')+`</table>`;const pr=await fetchJSON('/api/prom');document.getElementById('promTbl').innerHTML=`<table><tr><th>job</th><th>health</th></tr>`+pr.map(x=>`<tr><td>${x.labels.job}</td><td>${x.health}</td></tr>`).join('')+`</table>`;}catch(e){document.getElementById('panelsTbl').textContent='error '+e.message}}
async function loadTraces(){try{const j=await fetchJSON('/api/traces?limit=10');const rows=j.data||j||[];document.getElementById('tracesTbl').innerHTML=rows.slice(0,10).map(r=>`<div class="kv"><span>${r.request_id?.slice(0,12)}</span><span>${r.name}</span></div>`).join('')||'none';}catch(e){document.getElementById('tracesTbl').textContent='error '+e.message}}
async function loadTrace(){const id=document.getElementById('traceId').value.trim();if(!id) return;try{const j=await fetchJSON('/api/trace/'+encodeURIComponent(id));document.getElementById('traceDetail').textContent=JSON.stringify(j,null,2).slice(0,4000);}catch(e){document.getElementById('traceDetail').textContent='error '+e.message}}
// init
fetchJSON('/api/health').then(j=>{document.getElementById('health').textContent=j.status;document.getElementById('health').className='badge ok';}).catch(e=>{document.getElementById('health').textContent='error';});
loadRatings(); loadSummary(8760); loadPanels();
</script></body></html>"""
@app.get("/", response_class=HTMLResponse)
def index(): return HTMLResponse(HTML)
@app.get("/api/health")
def health(): return {"status":"ok","panel":"observability","port":16333}
@app.get("/api/ratings")
def ratings():
    out=[]
    for mid,cfg in MODEL_REGISTRY.items():
        out.append({"id":mid,"name":cfg.get("name"),"creator":cfg.get("creator"),"params":cfg.get("params"),"quant":cfg.get("quant"),"size_gb":cfg.get("size_gb"),"benchmark_mean":cfg.get("benchmark_mean"),"status":cfg.get("status")})
    out.sort(key=lambda x: (x["benchmark_mean"] or 0), reverse=True)
    return out
@app.get("/api/histogram")
async def hist(hours: int=8760):
    async with httpx.AsyncClient(timeout=5, trust_env=False) as c:
        r=await c.get(f"{MANAGER}/api/metrics/histogram?hours={hours}")
        return JSONResponse(r.json(), status_code=r.status_code)
@app.get("/api/timeseries")
async def times(hours: int=168, bucket_min: int=60):
    async with httpx.AsyncClient(timeout=5, trust_env=False) as c:
        r=await c.get(f"{MANAGER}/api/metrics/timeseries?hours={hours}&bucket_min={bucket_min}")
        return JSONResponse(r.json(), status_code=r.status_code)
@app.get("/api/summary")
async def summary(hours: int=8760):
    async with httpx.AsyncClient(timeout=5, trust_env=False) as c:
        r=await c.get(f"{MANAGER}/api/metrics/summary?hours={hours}")
        return JSONResponse(r.json(), status_code=r.status_code)
@app.get("/api/panels")
async def panels():
    async with httpx.AsyncClient(timeout=5, trust_env=False) as c:
        r=await c.get(f"{MANAGER}/api/panels/health")
        return JSONResponse(r.json(), status_code=r.status_code)
@app.get("/api/prom")
async def prom():
    async with httpx.AsyncClient(timeout=5, trust_env=False) as c:
        r=await c.get(f"{PROM}/prometheus/api/v1/targets")
        j=r.json()
        return JSONResponse(j["data"]["activeTargets"], status_code=r.status_code)
@app.get("/api/traces")
async def traces(limit: int=10):
    async with httpx.AsyncClient(timeout=5, trust_env=False) as c:
        r=await c.get(f"{MANAGER}/panel/trace/api/observe/requests?limit={limit}")
        return JSONResponse(r.json(), status_code=r.status_code)
@app.get("/api/trace/{rid}")
async def trace(rid: str):
    async with httpx.AsyncClient(timeout=5, trust_env=False) as c:
        r=await c.get(f"{MANAGER}/panel/trace/api/observe/timeline/{rid}")
        return JSONResponse(r.json(), status_code=r.status_code)
