"""Browser UI for the watermark platform.

Serves lightweight, dependency-free HTML pages (vanilla JS calling the JSON API)
for the core operator workflows:

    /            dashboard
    /ui/embed    insert a watermark into an image or video
    /ui/read     read / trace the watermark in an uploaded file
    /ui/remove   remove or isolate a watermark (rights holder)
    /ui/audit    audit trail + integrity check
    /ui/models   available watermark models
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"], include_in_schema=False)

_STYLE = """
* { box-sizing: border-box; }
body { margin:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background:#0c1018; color:#e6edf3; }
header { background:#11151f; border-bottom:1px solid #222b3a; padding:14px 24px; display:flex;
         align-items:center; gap:24px; position:sticky; top:0; z-index:10; }
header .brand { font-weight:700; letter-spacing:.5px; color:#fff; }
header .brand span { color:#4da3ff; }
nav a { color:#9fb0c3; text-decoration:none; margin-right:18px; font-size:14px; padding:6px 0; }
nav a:hover { color:#fff; }
nav a.active { color:#4da3ff; border-bottom:2px solid #4da3ff; }
main { max-width:880px; margin:32px auto; padding:0 24px; }
h1 { font-size:22px; margin:0 0 6px; }
.sub { color:#8b9bb0; margin:0 0 24px; font-size:14px; }
.card { background:#11161f; border:1px solid #222b3a; border-radius:12px; padding:24px; margin-bottom:20px; }
label { display:block; font-size:13px; color:#9fb0c3; margin:14px 0 6px; }
input, select { width:100%; padding:10px 12px; background:#0c1018; border:1px solid #2a3547;
        border-radius:8px; color:#e6edf3; font-size:14px; }
input[type=file] { padding:8px; }
input[type=range] { padding:0; }
.row { display:flex; gap:16px; } .row > div { flex:1; }
button { margin-top:20px; background:#2563eb; color:#fff; border:0; border-radius:8px;
         padding:12px 20px; font-size:15px; font-weight:600; cursor:pointer; }
button:hover { background:#1d4ed8; } button:disabled { background:#374151; cursor:wait; }
.result { margin-top:20px; padding:16px; border-radius:8px; background:#0c1320; border:1px solid #1e2a3d;
          font-size:14px; display:none; }
.result.show { display:block; }
.kv { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #1a2332; }
.kv:last-child { border-bottom:0; } .kv b { color:#fff; } .kv .v { color:#9fd; font-family:monospace; }
.badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:700; }
.ok { background:#0b3d1e; color:#46d97e; } .bad { background:#3d1414; color:#ff7b7b; }
.hint { font-size:12px; color:#6b7a90; margin-top:4px; }
a.dl { display:inline-block; margin-top:14px; color:#4da3ff; }
.grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
.tile { background:#11161f; border:1px solid #222b3a; border-radius:12px; padding:20px; }
.tile h3 { margin:0 0 6px; color:#fff; } .tile p { margin:0; color:#8b9bb0; font-size:13px; }
.tile a { color:#4da3ff; text-decoration:none; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { text-align:left; padding:8px 10px; border-bottom:1px solid #1a2332; }
th { color:#8b9bb0; font-weight:600; }
pre { background:#0c1320; padding:12px; border-radius:8px; overflow:auto; font-size:12px; color:#9fd; }
"""


def _nav(active: str) -> str:
    items = [
        ("/", "Dashboard", "home"),
        ("/ui/embed", "Insert", "embed"),
        ("/ui/read", "Read / Trace", "read"),
        ("/ui/remove", "Remove", "remove"),
        ("/ui/audit", "Audit", "audit"),
        ("/ui/models", "Models", "models"),
    ]
    links = "".join(
        f'<a href="{href}" class="{"active" if key == active else ""}">{label}</a>'
        for href, label, key in items
    )
    return links


def _page(title: str, active: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title} · INJECTION-NOISE-WATERMARK</title><style>{_STYLE}</style></head><body>"
        "<header><div class='brand'>INJECTION·NOISE·<span>WATERMARK</span></div>"
        f"<nav>{_nav(active)}</nav></header><main>{body}</main></body></html>"
    )


# --- shared JS helpers (no template braces conflict; raw string) ----------
_JS_HELPERS = """
async function loadModels(selId){
  try{
    const r = await fetch('/api/v1/models'); const d = await r.json();
    const sel = document.getElementById(selId); if(!sel) return;
    sel.innerHTML = d.details.map(m => `<option value="${m.id}">${m.name} (${m.id})</option>`).join('');
  }catch(e){}
}
function basename(p){ return (p||'').split(/[\\\\/]/).pop(); }
function kv(k,v){ return `<div class="kv"><b>${k}</b><span class="v">${v}</span></div>`; }
function badge(ok, t){ return `<span class="badge ${ok?'ok':'bad'}">${t}</span>`; }
function show(id, html){ const e=document.getElementById(id); e.innerHTML=html; e.classList.add('show'); }
"""


@router.get("/", response_class=HTMLResponse)
async def home() -> str:
    """Dashboard with links to each workflow."""
    body = """
    <h1>Watermark Operations Console</h1>
    <p class="sub">Insert invisible, traceable watermarks · read them back · remove them.</p>
    <div class="grid">
      <div class="tile"><h3>① Insert</h3><p>Embed a delivery watermark into an image or video, registered to a recipient.</p><p><a href="/ui/embed">Go to Insert →</a></p></div>
      <div class="tile"><h3>② Read / Trace</h3><p>Upload a (possibly leaked) file and recover the watermark + recipient.</p><p><a href="/ui/read">Go to Read →</a></p></div>
      <div class="tile"><h3>③ Remove</h3><p>Rights-holder removal or forensic noise-isolation of a watermark.</p><p><a href="/ui/remove">Go to Remove →</a></p></div>
      <div class="tile"><h3>Audit</h3><p>Tamper-evident, hash-chained activity log with integrity check.</p><p><a href="/ui/audit">Open Audit →</a></p></div>
      <div class="tile"><h3>Models</h3><p>The available watermark engines and their capabilities.</p><p><a href="/ui/models">View Models →</a></p></div>
      <div class="tile"><h3>API Docs</h3><p>Interactive OpenAPI / Swagger reference.</p><p><a href="/docs">Open /docs →</a></p></div>
    </div>
    """
    return _page("Dashboard", "home", body)


@router.get("/ui/embed", response_class=HTMLResponse)
async def embed_page() -> str:
    """Watermark-insertion page (image or video)."""
    body = """
    <h1>① Insert watermark</h1>
    <p class="sub">Embed an invisible, recipient-bound watermark. The output looks identical to the original.</p>
    <div class="card">
      <form id="f">
        <label>File (image or video)</label>
        <input type="file" id="file" accept="image/*,video/*" required>
        <div class="row">
          <div><label>Media type</label>
            <select id="kind"><option value="image">Image</option><option value="video">Video</option></select></div>
          <div><label>Model</label><select id="model"></select></div>
        </div>
        <div class="row">
          <div><label>Asset ID</label><input id="asset_id" value="ASSET-001" required></div>
          <div><label>Client ID</label><input id="client_id" value="CLIENT-A" required></div>
        </div>
        <div class="row">
          <div><label>Recipient ID</label><input id="recipient_id" value="studio@partner.com" required></div>
          <div><label>Distribution ID</label><input id="distribution_id" value="OTT-KR"></div>
        </div>
        <label>Strength: <span id="sv">0.20</span></label>
        <input type="range" id="strength" min="0.05" max="0.4" step="0.01" value="0.20"
               oninput="document.getElementById('sv').textContent=this.value">
        <button type="submit" id="go">Embed watermark</button>
      </form>
      <div class="result" id="res"></div>
    </div>
    <script>
    __HELPERS__
    loadModels('model');
    document.getElementById('f').addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      const b=document.getElementById('go'); b.disabled=true; b.textContent='Embedding…';
      const fd=new FormData();
      fd.append('file', document.getElementById('file').files[0]);
      for(const k of ['asset_id','client_id','recipient_id','model','strength','distribution_id'])
        fd.append(k, document.getElementById(k).value);
      const kind=document.getElementById('kind').value;
      const url = kind==='video' ? '/api/v1/video/embed' : '/api/v1/embed';
      try{
        const r=await fetch(url,{method:'POST',body:fd}); const d=await r.json();
        if(!r.ok){ show('res', badge(false,'ERROR')+' '+(d.detail||'failed')); }
        else{
          const dl='/api/v1/assets/'+basename(d.output_uri);
          show('res', badge(true,'WATERMARKED')
            +kv('Delivery ID', d.delivery_id)+kv('Token', d.token_id)+kv('Model', d.model)
            +kv('PSNR (dB)', d.psnr)+kv('SSIM', d.ssim)
            +`<a class="dl" href="${dl}" download>⬇ Download watermarked file</a>`);
        }
      }catch(e){ show('res', badge(false,'ERROR')+' '+e); }
      b.disabled=false; b.textContent='Embed watermark';
    });
    </script>
    """.replace("__HELPERS__", _JS_HELPERS)
    return _page("Insert", "embed", body)


@router.get("/ui/read", response_class=HTMLResponse)
async def read_page() -> str:
    """Watermark read / trace page."""
    body = """
    <h1>② Read / Trace watermark</h1>
    <p class="sub">Upload a suspect or leaked file. The system recovers the embedded watermark and resolves it to the original recipient.</p>
    <div class="card">
      <form id="f">
        <label>File (image or video)</label>
        <input type="file" id="file" accept="image/*,video/*" required>
        <div class="row">
          <div><label>Media type</label>
            <select id="kind"><option value="image">Image</option><option value="video">Video</option></select></div>
          <div><label>Client ID (optional — narrows search)</label><input id="client_id" value="CLIENT-A"></div>
        </div>
        <button type="submit" id="go">Read watermark</button>
      </form>
      <div class="result" id="res"></div>
    </div>
    <script>
    __HELPERS__
    document.getElementById('f').addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      const b=document.getElementById('go'); b.disabled=true; b.textContent='Analyzing…';
      const fd=new FormData();
      fd.append('file', document.getElementById('file').files[0]);
      const cid=document.getElementById('client_id').value; if(cid) fd.append('client_id', cid);
      const kind=document.getElementById('kind').value;
      const url = kind==='video' ? '/api/v1/video/trace' : '/api/v1/trace';
      try{
        const r=await fetch(url,{method:'POST',body:fd}); const d=await r.json();
        if(!r.ok){ show('res', badge(false,'ERROR')+' '+(d.detail||'failed')); }
        else if(d.found){
          show('res', badge(true,'WATERMARK FOUND')
            +kv('Recipient', d.recipient)+kv('Asset ID', d.asset_id)+kv('Delivery ID', d.delivery_id)
            +kv('Model', d.watermark_model)+kv('Confidence', (d.confidence*100).toFixed(1)+'%')
            +kv('Signature', d.signature_valid?'valid ✓':'invalid ✗')
            +kv('Chain of custody', (d.trace_path||[]).join(' → ')));
        } else {
          show('res', badge(false,'NO WATERMARK ATTRIBUTED')
            +'<div class="hint">No registered watermark was recovered from this file.</div>');
        }
      }catch(e){ show('res', badge(false,'ERROR')+' '+e); }
      b.disabled=false; b.textContent='Read watermark';
    });
    </script>
    """.replace("__HELPERS__", _JS_HELPERS)
    return _page("Read", "read", body)


@router.get("/ui/remove", response_class=HTMLResponse)
async def remove_page() -> str:
    """Watermark removal / isolation page."""
    body = """
    <h1>③ Remove / Isolate watermark</h1>
    <p class="sub">Rights-holder removal or forensic noise-isolation. All removals are recorded in the audit trail.</p>
    <div class="card">
      <form id="f">
        <label>File (image)</label>
        <input type="file" id="file" accept="image/*" required>
        <div class="row">
          <div><label>Method</label>
            <select id="method">
              <option value="frequency_suppression">Frequency suppression</option>
              <option value="neural_denoising">Neural denoising</option>
              <option value="template_cancellation">Template cancellation (needs key)</option>
              <option value="residual_reconstruction">Residual reconstruction</option>
              <option value="watermark_isolation">Watermark isolation (noise view)</option>
            </select></div>
          <div><label>Model</label><select id="model"></select></div>
        </div>
        <label>Asset ID (required for template cancellation)</label>
        <input id="asset_id" value="ASSET-001">
        <button type="submit" id="go">Run removal</button>
      </form>
      <div class="result" id="res"></div>
    </div>
    <script>
    __HELPERS__
    loadModels('model');
    document.getElementById('f').addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      const b=document.getElementById('go'); b.disabled=true; b.textContent='Processing…';
      const fd=new FormData();
      fd.append('file', document.getElementById('file').files[0]);
      for(const k of ['method','model','asset_id']) fd.append(k, document.getElementById(k).value);
      fd.append('requested_by','console');
      try{
        const r=await fetch('/api/v1/remove',{method:'POST',body:fd}); const d=await r.json();
        if(!r.ok){ show('res', badge(false,'ERROR')+' '+(d.detail||'failed')); }
        else{
          const dl='/api/v1/assets/'+basename(d.output_uri);
          show('res', badge(true,'DONE')
            +kv('Method', d.method)+kv('Watermark detected (before)', d.watermark_detected)
            +kv('Removal success', (d.removal_success*100).toFixed(1)+'%')
            +kv('Quality (SSIM vs input)', d.quality_score)
            +`<a class="dl" href="${dl}" download>⬇ Download result</a>`);
        }
      }catch(e){ show('res', badge(false,'ERROR')+' '+e); }
      b.disabled=false; b.textContent='Run removal';
    });
    </script>
    """.replace("__HELPERS__", _JS_HELPERS)
    return _page("Remove", "remove", body)


@router.get("/ui/audit", response_class=HTMLResponse)
async def audit_page() -> str:
    """Audit trail viewer + integrity check."""
    body = """
    <h1>Audit trail</h1>
    <p class="sub">Append-only, hash-chained log. Any tampering breaks the chain and is detected here.</p>
    <div class="card">
      <div id="status">Checking integrity…</div>
      <table id="tbl"><thead><tr><th>#</th><th>Action</th><th>Actor</th><th>Resource</th><th>When</th></tr></thead><tbody></tbody></table>
    </div>
    <script>
    __HELPERS__
    (async ()=>{
      try{
        const v=await (await fetch('/api/v1/audit/verify')).json();
        document.getElementById('status').innerHTML =
          (v.valid?badge(true,'CHAIN VALID'):badge(false,'CHAIN BROKEN'))+' &nbsp; '+v.entries+' entries';
        const logs=await (await fetch('/api/v1/audit/logs?limit=100')).json();
        const tb=document.querySelector('#tbl tbody');
        tb.innerHTML = logs.map((l,i)=>`<tr><td>${i+1}</td><td>${l.action}</td><td>${l.actor}</td>
          <td>${l.resource_id||''}</td><td>${(l.created_at||'').replace('T',' ').slice(0,19)}</td></tr>`).join('')
          || '<tr><td colspan=5 class="hint">No activity yet — run an Insert or Read.</td></tr>';
      }catch(e){ document.getElementById('status').innerHTML = badge(false,'ERROR')+' '+e; }
    })();
    </script>
    """.replace("__HELPERS__", _JS_HELPERS)
    return _page("Audit", "audit", body)


@router.get("/ui/models", response_class=HTMLResponse)
async def models_page() -> str:
    """Available watermark models."""
    body = """
    <h1>Watermark models</h1>
    <p class="sub">Pluggable engines behind the model selector. Neural/diffusion backends fall back to the internal engine when their weights are absent.</p>
    <div class="card">
      <table id="tbl"><thead><tr><th>ID</th><th>Name</th><th>Media</th><th>Notes</th></tr></thead><tbody></tbody></table>
    </div>
    <script>
    (async ()=>{
      const d=await (await fetch('/api/v1/models')).json();
      document.querySelector('#tbl tbody').innerHTML = d.details.map(m=>
        `<tr><td><code>${m.id}</code></td><td>${m.name}</td><td>${m.media_types.join(', ')}</td><td>${m.description}</td></tr>`).join('');
    })();
    </script>
    """
    return _page("Models", "models", body)
