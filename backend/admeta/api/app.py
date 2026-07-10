"""admeta 검색 웹앱 — FastAPI.

로컬 실행:
    py -3 -m uvicorn admeta.api.app:app --reload --port 8000
    → 브라우저에서 http://localhost:8000

- GET /              검색 페이지(단일 HTML)
- GET /api/search?q= 검색 결과(JSON): 매칭 개념 + 플랫폼별 대응 필드
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from admeta.db import store

app = FastAPI(title="admeta-hub 검색")


@app.get("/api/search")
def api_search(q: str = "") -> JSONResponse:
    con = store.connect()
    try:
        results = store.search(con, q.strip()) if q.strip() else []
        unmapped = store.search_unmapped(con, q.strip()) if q.strip() else []
    finally:
        con.close()
    return JSONResponse({"query": q, "count": len(results),
                         "results": results, "unmapped": unmapped})


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _PAGE


_PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>admeta-hub · 광고 지표 표준 검색</title>
<style>
  :root{--bg:#0f1117;--card:#1a1d27;--line:#2a2e3a;--fg:#e6e8ee;--mut:#8b90a0;--accent:#5b8cff}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);
    font-family:system-ui,'Segoe UI',sans-serif;line-height:1.5}
  .wrap{max-width:860px;margin:0 auto;padding:32px 20px}
  h1{font-size:22px;margin:0 0 4px} .sub{color:var(--mut);font-size:14px;margin-bottom:20px}
  .box{display:flex;gap:8px;position:sticky;top:12px}
  input{flex:1;padding:12px 14px;border-radius:10px;border:1px solid var(--line);
    background:var(--card);color:var(--fg);font-size:16px;outline:none}
  input:focus{border-color:var(--accent)}
  .hint{color:var(--mut);font-size:13px;margin:10px 2px 22px}
  .grp{background:var(--card);border:1px solid var(--line);border-radius:14px;
    padding:16px 18px;margin-bottom:14px}
  .k{font-size:18px;font-weight:700;color:var(--accent)}
  .kind{font-size:11px;color:var(--mut);border:1px solid var(--line);border-radius:6px;
    padding:1px 7px;margin-left:8px;vertical-align:middle}
  .kdesc{color:var(--mut);font-size:13px;margin:4px 0 12px}
  .row{display:flex;gap:10px;padding:8px 0;border-top:1px solid var(--line);flex-wrap:wrap}
  .plat{font-size:11px;font-weight:700;padding:3px 8px;border-radius:6px;white-space:nowrap;
    height:fit-content}
  .google_ads{background:#1a3a1a;color:#8fe08f} .meta{background:#16233f;color:#8fb4ff}
  .fname{font-family:'Consolas',monospace;font-size:14px} .fdesc{color:var(--mut);font-size:13px}
  .badge{font-size:11px;color:var(--mut);margin-left:auto;white-space:nowrap}
  .human{color:#ffd479}
  .empty{color:var(--mut);text-align:center;padding:40px}
</style></head>
<body><div class="wrap">
  <h1>🔗 admeta-hub</h1>
  <div class="sub">플랫폼마다 다른 광고 지표를 표준 개념으로 — "메타 clicks = 구글 뭐?"</div>
  <div class="box"><input id="q" placeholder="clicks, 비용, impressions, ctr ... 검색" autofocus></div>
  <div class="hint">필드명·설명·표준키로 검색 · 예: <b>clicks</b>, <b>spend</b>, <b>ctr</b></div>
  <div id="out"></div>
</div>
<script>
const q=document.getElementById('q'), out=document.getElementById('out');
let t;
q.addEventListener('input',()=>{clearTimeout(t);t=setTimeout(run,200)});
async function run(){
  const v=q.value.trim();
  if(!v){out.innerHTML='';return}
  const r=await fetch('/api/search?q='+encodeURIComponent(v));
  const d=await r.json();
  if(!d.results.length){out.innerHTML='<div class="empty">매칭되는 표준 개념이 없어요</div>';return}
  out.innerHTML=d.results.map(g=>`
    <div class="grp">
      <div><span class="k">${g.canonical_key}</span><span class="kind">${g.kind}</span></div>
      <div class="kdesc">${g.description||''}</div>
      ${g.fields.map(f=>`
        <div class="row">
          <span class="plat ${f.platform}">${f.platform.replace('google_ads','Google').replace('meta','Meta')}</span>
          <div><div class="fname">${f.api_name}</div><div class="fdesc">${(f.description||'').slice(0,110)}</div></div>
          <span class="badge">conf ${f.confidence?.toFixed(2)??'-'} ${f.reviewed_by==='human'?'· <span class=human>✔검수</span>':''}</span>
        </div>`).join('')}
    </div>`).join('');
}
</script>
</body></html>"""
