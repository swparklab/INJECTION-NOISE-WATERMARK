"""Browser UI for the watermark platform.

A polished, media-engineering styled console with:
    - Korean / English language toggle (persisted)
    - Light / Dark theme toggle (persisted)
    - Pages: dashboard, insert (embed), read (detect/trace), remove, audit, models

All pages are dependency-free server-rendered HTML; vanilla JS calls the JSON API.
UI text is driven by an i18n dictionary applied via ``data-i18n`` attributes.
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"], include_in_schema=False)


# --------------------------------------------------------------------------
# i18n dictionary (ko / en)
# --------------------------------------------------------------------------
I18N: dict[str, dict[str, str]] = {
    "ko": {
        "brand.tag": "콘텐츠 프로비넌스 · 미디어 엔지니어링",
        "nav.home": "대시보드",
        "nav.embed": "워터마크 삽입",
        "nav.read": "판독 · 추적",
        "nav.remove": "제거",
        "nav.audit": "감사 로그",
        "nav.models": "모델",
        "nav.api": "API 문서",
        "footer": "비가시성 워터마크로 콘텐츠의 소유권을 증명하고 유출을 추적합니다.",
        # dashboard
        "home.title": "워터마크 운영 콘솔",
        "home.sub": "보이지 않는 추적형 워터마크를 삽입하고 · 판독하고 · 제거합니다.",
        "tile.embed.t": "① 삽입",
        "tile.embed.d": "이미지 또는 영상에 수신자별 추적 워터마크를 삽입합니다.",
        "tile.read.t": "② 판독 · 추적",
        "tile.read.d": "유출 의심 파일을 올려 워터마크와 수신자를 복원합니다.",
        "tile.remove.t": "③ 제거",
        "tile.remove.d": "권리자용 워터마크 제거 및 노이즈 분리(포렌식).",
        "tile.audit.t": "감사 로그",
        "tile.audit.d": "위변조 방지 해시체인 활동 로그와 무결성 검증.",
        "tile.models.t": "모델",
        "tile.models.d": "사용 가능한 워터마크 엔진과 특성.",
        "tile.api.t": "API 문서",
        "tile.api.d": "인터랙티브 OpenAPI / Swagger 레퍼런스.",
        "tile.cta": "바로가기 →",
        # common form
        "f.file": "파일",
        "f.file.img": "파일 (이미지)",
        "f.kind": "미디어 유형",
        "kind.image": "이미지",
        "kind.video": "영상",
        "f.model": "모델",
        "f.asset": "자산 ID (Asset)",
        "f.client": "클라이언트 ID",
        "f.recipient": "수신자 ID",
        "f.dist": "유통 ID",
        "f.strength": "삽입 강도",
        "f.client_opt": "클라이언트 ID (선택 — 검색 범위 축소)",
        "f.method": "제거 방식",
        "f.asset_tmpl": "자산 ID (템플릿 상쇄 방식에 필요)",
        "roi.title": "삽입 영역 · 시간 (영상)",
        "roi.region": "삽입 영역 — 박스를 드래그/리사이즈해서 지정",
        "roi.x": "X (%)",
        "roi.y": "Y (%)",
        "roi.w": "너비 (%)",
        "roi.h": "높이 (%)",
        "roi.start": "시작 (초)",
        "roi.end": "끝 (초)",
        "roi.hint": "전체에 넣으려면 박스를 가득 채우세요. 작은 영역은 고해상도 영상에서만 가능합니다.",
        "roi.read_region": "판독 영역 — 삽입 때와 같은 영역으로 지정",
        # buttons
        "btn.embed": "워터마크 삽입",
        "btn.embed.busy": "삽입 중…",
        "btn.read": "워터마크 판독",
        "btn.read.busy": "분석 중…",
        "btn.remove": "제거 실행",
        "btn.remove.busy": "처리 중…",
        # embed page
        "embed.title": "① 워터마크 삽입",
        "embed.sub": "보이지 않는 수신자 귀속 워터마크를 삽입합니다. 결과물은 원본과 시각적으로 동일합니다.",
        # read page
        "read.title": "② 워터마크 판독 · 추적",
        "read.sub": "유출/의심 파일을 올리면 삽입된 워터마크를 복원하고 원래 수신자로 추적합니다.",
        # remove page
        "remove.title": "③ 워터마크 제거 · 분리",
        "remove.sub": "권리자용 제거 또는 포렌식 노이즈 분리. 모든 제거는 감사 로그에 기록됩니다.",
        "method.freq": "주파수 억제",
        "method.neural": "뉴럴 디노이징",
        "method.template": "템플릿 상쇄 (키 필요)",
        "method.residual": "잔차 재구성",
        "method.iso": "워터마크 분리 (노이즈 보기)",
        # results / kv
        "kv.delivery": "딜리버리 ID",
        "kv.token": "토큰",
        "kv.model": "모델",
        "kv.psnr": "PSNR (dB)",
        "kv.ssim": "SSIM",
        "kv.recipient": "수신자",
        "kv.asset": "자산 ID",
        "kv.confidence": "신뢰도",
        "kv.signature": "서명",
        "kv.chain": "체인 오브 커스터디",
        "kv.method": "방식",
        "kv.detected": "워터마크 감지 (이전)",
        "kv.success": "제거 성공도",
        "kv.quality": "품질 (입력 대비 SSIM)",
        "badge.watermarked": "워터마크 삽입됨",
        "badge.found": "워터마크 발견",
        "badge.notfound": "귀속 워터마크 없음",
        "badge.done": "완료",
        "badge.error": "오류",
        "sig.valid": "유효 ✓",
        "sig.invalid": "무효 ✗",
        "msg.notfound": "이 파일에서 등록된 워터마크를 복원하지 못했습니다.",
        "dl.file": "⬇ 워터마크 파일 다운로드",
        "dl.result": "⬇ 결과 다운로드",
        # audit
        "audit.title": "감사 로그",
        "audit.sub": "추가 전용 해시체인 로그. 변조가 발생하면 체인이 깨지고 여기서 감지됩니다.",
        "audit.checking": "무결성 확인 중…",
        "audit.valid": "체인 유효",
        "audit.broken": "체인 손상",
        "audit.entries": "건",
        "th.action": "동작",
        "th.actor": "주체",
        "th.resource": "리소스",
        "th.when": "시각",
        "audit.empty": "활동 없음 — 삽입 또는 판독을 실행해 보세요.",
        # models
        "models.title": "워터마크 모델",
        "models.sub": "모델 셀렉터 뒤의 플러그형 엔진. 뉴럴/디퓨전 백엔드는 가중치가 없으면 내장 엔진으로 폴백합니다.",
        "th.id": "ID",
        "th.name": "이름",
        "th.media": "미디어",
        "th.notes": "설명",
    },
    "en": {
        "brand.tag": "Content Provenance · Media Engineering",
        "nav.home": "Dashboard",
        "nav.embed": "Insert",
        "nav.read": "Read · Trace",
        "nav.remove": "Remove",
        "nav.audit": "Audit",
        "nav.models": "Models",
        "nav.api": "API Docs",
        "footer": "Prove ownership and trace leaks with invisible watermarks.",
        "home.title": "Watermark Operations Console",
        "home.sub": "Insert invisible, traceable watermarks · read them back · remove them.",
        "tile.embed.t": "① Insert",
        "tile.embed.d": "Embed a recipient-bound tracing watermark into an image or video.",
        "tile.read.t": "② Read · Trace",
        "tile.read.d": "Upload a suspect file to recover the watermark and recipient.",
        "tile.remove.t": "③ Remove",
        "tile.remove.d": "Rights-holder removal and forensic noise isolation.",
        "tile.audit.t": "Audit",
        "tile.audit.d": "Tamper-evident hash-chained activity log with integrity check.",
        "tile.models.t": "Models",
        "tile.models.d": "The available watermark engines and their capabilities.",
        "tile.api.t": "API Docs",
        "tile.api.d": "Interactive OpenAPI / Swagger reference.",
        "tile.cta": "Open →",
        "f.file": "File",
        "f.file.img": "File (image)",
        "f.kind": "Media type",
        "kind.image": "Image",
        "kind.video": "Video",
        "f.model": "Model",
        "f.asset": "Asset ID",
        "f.client": "Client ID",
        "f.recipient": "Recipient ID",
        "f.dist": "Distribution ID",
        "f.strength": "Strength",
        "f.client_opt": "Client ID (optional — narrows search)",
        "f.method": "Method",
        "f.asset_tmpl": "Asset ID (required for template cancellation)",
        "roi.title": "Region · Time (video)",
        "roi.region": "Embed region — drag / resize the box",
        "roi.x": "X (%)",
        "roi.y": "Y (%)",
        "roi.w": "Width (%)",
        "roi.h": "Height (%)",
        "roi.start": "Start (s)",
        "roi.end": "End (s)",
        "roi.hint": "Fill the box for whole-frame. Small regions only fit on high-resolution video.",
        "roi.read_region": "Read region — match the region used at embed time",
        "btn.embed": "Embed watermark",
        "btn.embed.busy": "Embedding…",
        "btn.read": "Read watermark",
        "btn.read.busy": "Analyzing…",
        "btn.remove": "Run removal",
        "btn.remove.busy": "Processing…",
        "embed.title": "① Insert watermark",
        "embed.sub": "Embed an invisible, recipient-bound watermark. The output looks identical to the original.",
        "read.title": "② Read · Trace watermark",
        "read.sub": "Upload a suspect or leaked file. The system recovers the embedded watermark and resolves the original recipient.",
        "remove.title": "③ Remove · Isolate watermark",
        "remove.sub": "Rights-holder removal or forensic noise-isolation. All removals are recorded in the audit trail.",
        "method.freq": "Frequency suppression",
        "method.neural": "Neural denoising",
        "method.template": "Template cancellation (needs key)",
        "method.residual": "Residual reconstruction",
        "method.iso": "Watermark isolation (noise view)",
        "kv.delivery": "Delivery ID",
        "kv.token": "Token",
        "kv.model": "Model",
        "kv.psnr": "PSNR (dB)",
        "kv.ssim": "SSIM",
        "kv.recipient": "Recipient",
        "kv.asset": "Asset ID",
        "kv.confidence": "Confidence",
        "kv.signature": "Signature",
        "kv.chain": "Chain of custody",
        "kv.method": "Method",
        "kv.detected": "Watermark detected (before)",
        "kv.success": "Removal success",
        "kv.quality": "Quality (SSIM vs input)",
        "badge.watermarked": "WATERMARKED",
        "badge.found": "WATERMARK FOUND",
        "badge.notfound": "NO WATERMARK ATTRIBUTED",
        "badge.done": "DONE",
        "badge.error": "ERROR",
        "sig.valid": "valid ✓",
        "sig.invalid": "invalid ✗",
        "msg.notfound": "No registered watermark was recovered from this file.",
        "dl.file": "⬇ Download watermarked file",
        "dl.result": "⬇ Download result",
        "audit.title": "Audit trail",
        "audit.sub": "Append-only, hash-chained log. Any tampering breaks the chain and is detected here.",
        "audit.checking": "Checking integrity…",
        "audit.valid": "CHAIN VALID",
        "audit.broken": "CHAIN BROKEN",
        "audit.entries": "entries",
        "th.action": "Action",
        "th.actor": "Actor",
        "th.resource": "Resource",
        "th.when": "When",
        "audit.empty": "No activity yet — run an Insert or Read.",
        "models.title": "Watermark models",
        "models.sub": "Pluggable engines behind the model selector. Neural/diffusion backends fall back to the internal engine when weights are absent.",
        "th.id": "ID",
        "th.name": "Name",
        "th.media": "Media",
        "th.notes": "Notes",
    },
}

_I18N_JSON = json.dumps(I18N, ensure_ascii=False)


# --------------------------------------------------------------------------
# Styling — media-engineering aesthetic with light/dark CSS variables
# --------------------------------------------------------------------------
_CSS = """
:root{
  --bg:#f4f7fb; --bg2:#eaf0f7; --panel:#ffffff; --panel2:#f7fafd;
  --text:#0d1b2a; --muted:#5b6b7f; --border:#e2e8f0;
  --accent:#1f6feb; --accent2:#06b6d4; --ok:#15803d; --okbg:#dcfce7;
  --bad:#b91c1c; --badbg:#fee2e2; --shadow:0 6px 24px rgba(20,40,80,.08);
}
[data-theme=dark]{
  --bg:#070b12; --bg2:#0b111c; --panel:#0f1622; --panel2:#0c121d;
  --text:#e6edf3; --muted:#8b9bb0; --border:#1d2738;
  --accent:#4da3ff; --accent2:#2bd4c7; --ok:#46d97e; --okbg:#0b3d1e;
  --bad:#ff7b7b; --badbg:#3d1414; --shadow:0 8px 30px rgba(0,0,0,.45);
}
*{box-sizing:border-box}
body{margin:0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI','Apple SD Gothic Neo',
     'Malgun Gothic',Roboto,sans-serif;background:
     radial-gradient(1200px 500px at 80% -10%, var(--bg2), transparent), var(--bg);
     color:var(--text);min-height:100vh;transition:background .3s,color .3s}
header{backdrop-filter:saturate(150%) blur(8px);background:color-mix(in srgb,var(--panel) 85%,transparent);
       border-bottom:1px solid var(--border);padding:0 28px;display:flex;align-items:center;gap:28px;
       height:64px;position:sticky;top:0;z-index:20}
.brand{display:flex;align-items:center;gap:12px;text-decoration:none}
.brand .logo{width:30px;height:30px;flex:0 0 auto}
.brand .bt{font-weight:800;letter-spacing:.4px;font-size:15px;color:var(--text);line-height:1}
.brand .bs{font-size:10.5px;color:var(--muted);letter-spacing:.3px;margin-top:3px}
.brand .grad{background:linear-gradient(90deg,var(--accent),var(--accent2));
     -webkit-background-clip:text;background-clip:text;color:transparent}
nav{display:flex;gap:4px;flex:1;flex-wrap:wrap}
nav a{color:var(--muted);text-decoration:none;font-size:13.5px;padding:8px 12px;border-radius:8px;font-weight:500}
nav a:hover{color:var(--text);background:color-mix(in srgb,var(--accent) 12%,transparent)}
nav a.active{color:var(--accent);background:color-mix(in srgb,var(--accent) 14%,transparent)}
.ctrls{display:flex;gap:8px;align-items:center}
.ctrls button{background:var(--panel2);border:1px solid var(--border);color:var(--text);
     border-radius:9px;padding:7px 11px;font-size:13px;cursor:pointer;font-weight:600}
.ctrls button:hover{border-color:var(--accent);color:var(--accent)}
main{max-width:920px;margin:36px auto;padding:0 24px}
.hero h1{font-size:26px;margin:0 0 8px;letter-spacing:-.3px}
.hero p.sub{color:var(--muted);margin:0 0 26px;font-size:15px;max-width:640px;line-height:1.5}
.card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:26px;
     margin-bottom:20px;box-shadow:var(--shadow)}
label{display:block;font-size:13px;color:var(--muted);margin:16px 0 7px;font-weight:600}
input,select{width:100%;padding:11px 13px;background:var(--panel2);border:1px solid var(--border);
     border-radius:10px;color:var(--text);font-size:14px;outline:none;transition:border .15s}
input:focus,select:focus{border-color:var(--accent)}
input[type=file]{padding:9px;cursor:pointer}
input[type=range]{padding:0;accent-color:var(--accent)}
.row{display:flex;gap:16px;flex-wrap:wrap}.row>div{flex:1;min-width:180px}
button.go{margin-top:22px;background:linear-gradient(90deg,var(--accent),var(--accent2));color:#fff;
     border:0;border-radius:11px;padding:13px 22px;font-size:15px;font-weight:700;cursor:pointer;
     box-shadow:0 6px 18px color-mix(in srgb,var(--accent) 35%,transparent)}
button.go:hover{filter:brightness(1.07)}button.go:disabled{filter:grayscale(.5);cursor:wait}
.result{margin-top:22px;padding:18px;border-radius:12px;background:var(--panel2);
     border:1px solid var(--border);font-size:14px;display:none}
.result.show{display:block;animation:fade .25s ease}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1}}
.kv{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid var(--border)}
.kv:last-of-type{border-bottom:0}.kv b{color:var(--text);font-weight:600}
.kv .v{color:var(--accent2);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;text-align:right;word-break:break-all}
.badge{display:inline-block;padding:4px 12px;border-radius:30px;font-size:12px;font-weight:800;letter-spacing:.3px}
.badge.ok{background:var(--okbg);color:var(--ok)}.badge.bad{background:var(--badbg);color:var(--bad)}
.hint{font-size:12.5px;color:var(--muted);margin-top:6px}
a.dl{display:inline-block;margin-top:16px;color:var(--accent);font-weight:600;text-decoration:none}
a.dl:hover{text-decoration:underline}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
@media(max-width:720px){.grid{grid-template-columns:1fr}}
.tile{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:22px;
     box-shadow:var(--shadow);transition:transform .15s,border-color .15s}
.tile:hover{transform:translateY(-3px);border-color:var(--accent)}
.tile h3{margin:0 0 8px;font-size:16px}.tile p{margin:0 0 14px;color:var(--muted);font-size:13.5px;line-height:1.5}
.tile a{color:var(--accent);text-decoration:none;font-weight:600;font-size:13.5px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
td code{background:var(--panel2);padding:2px 7px;border-radius:6px;font-size:12.5px}
footer{max-width:920px;margin:10px auto 40px;padding:0 24px;color:var(--muted);font-size:12.5px}

/* ---------- Fluid / responsive sizing (scales with viewport) ---------- */
main{width:min(960px,92vw);max-width:none;margin:clamp(20px,4vw,40px) auto}
.hero h1{font-size:clamp(22px,4.2vw,32px)}
.hero p.sub{font-size:clamp(13.5px,1.6vw,16px)}
.card{padding:clamp(18px,3vw,28px);border-radius:clamp(12px,1.6vw,18px)}
footer{width:min(960px,92vw);max-width:none}
/* true auto-fit responsive grid: 3 -> 2 -> 1 columns by available width */
.grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));perspective:1400px}

@media(max-width:860px){
  header{height:auto;flex-wrap:wrap;padding:12px 18px;gap:12px}
  nav{order:3;width:100%}
  .ctrls{margin-left:auto}
}
@media(max-width:560px){
  nav a{padding:7px 9px;font-size:12.5px}
  .brand .bs{display:none}
  .row{gap:10px}
}

/* ---------- 3D depth / stereoscopic feel ---------- */
.tile{
  transform-style:preserve-3d;
  transition:transform .18s ease, box-shadow .18s ease, border-color .18s;
  will-change:transform;
  box-shadow:var(--shadow), 0 1px 0 color-mix(in srgb,var(--accent) 18%,transparent) inset;
}
.tile::after{ /* glossy sheen that shifts with tilt */
  content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
  background:linear-gradient(135deg, color-mix(in srgb,#fff 14%,transparent), transparent 40%);
  opacity:.0;transition:opacity .2s;
}
.tile{position:relative}
.tile:hover::after{opacity:.6}
.tile h3,.tile p,.tile a{transform:translateZ(28px)}
.tile:hover{box-shadow:0 22px 50px rgba(0,0,0,.35),
  0 0 0 1px color-mix(in srgb,var(--accent) 40%,transparent)}
.card{transform-style:preserve-3d}
button.go{transform:translateZ(0);transition:transform .12s, filter .15s, box-shadow .15s}
button.go:active{transform:translateY(2px) scale(.99)}
.brand .logo{animation:float 4.5s ease-in-out infinite;filter:drop-shadow(0 4px 10px color-mix(in srgb,var(--accent) 45%,transparent))}
@keyframes float{0%,100%{transform:translateY(0) rotate(0deg)}50%{transform:translateY(-3px) rotate(8deg)}}
.badge{transform:translateZ(10px)}

@media(prefers-reduced-motion:reduce){
  *{animation:none!important;transition:none!important}
  .tile,.tile h3,.tile p,.tile a{transform:none!important}
}

/* ---------- ROI / region picker ---------- */
.roiwrap{margin-top:16px;display:none}
.stage{position:relative;width:100%;max-width:520px;user-select:none;touch-action:none;
  border-radius:12px;overflow:hidden;border:1px solid var(--border);background:#000}
.stage img,.stage video{display:block;width:100%}
.roibox{position:absolute;left:0;top:0;width:100%;height:100%;cursor:move;box-sizing:border-box;
  border:2px solid var(--accent);background:color-mix(in srgb,var(--accent) 16%,transparent);
  box-shadow:0 0 0 9999px color-mix(in srgb,#000 35%,transparent)}
.roibox .rh{position:absolute;width:16px;height:16px;background:var(--accent);border-radius:4px;
  right:-9px;bottom:-9px;cursor:nwse-resize;box-shadow:0 2px 6px rgba(0,0,0,.4)}
.roifields{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.roifields>div{flex:1;min-width:70px}
.roifields label{margin:0 0 4px}
.roihint{font-size:12px;color:var(--muted);margin-top:8px}
"""

_LOGO = (
    "<svg class='logo' viewBox='0 0 32 32' fill='none' xmlns='http://www.w3.org/2000/svg'>"
    "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
    "<stop offset='0' stop-color='#4da3ff'/><stop offset='1' stop-color='#2bd4c7'/></linearGradient></defs>"
    "<circle cx='16' cy='16' r='13' stroke='url(#g)' stroke-width='2'/>"
    "<circle cx='16' cy='16' r='8' stroke='url(#g)' stroke-width='1.6' opacity='.7'/>"
    "<circle cx='16' cy='16' r='3' fill='url(#g)'/></svg>"
)


def _nav(active: str) -> str:
    items = [
        ("/", "nav.home", "home"),
        ("/ui/embed", "nav.embed", "embed"),
        ("/ui/read", "nav.read", "read"),
        ("/ui/remove", "nav.remove", "remove"),
        ("/ui/audit", "nav.audit", "audit"),
        ("/ui/models", "nav.models", "models"),
        ("/docs", "nav.api", "api"),
    ]
    return "".join(
        f'<a href="{href}" class="{"active" if key == active else ""}" data-i18n="{k}">{k}</a>'
        for href, k, key in items
    )


_BASE_SCRIPT = """
const I18N = __I18N__;
function curLang(){ return localStorage.getItem('inw_lang') || 'ko'; }
function curTheme(){ return localStorage.getItem('inw_theme') || 'dark'; }
function t(k){ const L=curLang(); return (I18N[L]&&I18N[L][k]!==undefined)?I18N[L][k]:k; }
function applyI18n(){
  const L=curLang(); document.documentElement.lang=L;
  document.querySelectorAll('[data-i18n]').forEach(e=>{ const k=e.getAttribute('data-i18n');
    if(I18N[L][k]!==undefined) e.textContent=I18N[L][k]; });
  document.querySelectorAll('[data-i18n-ph]').forEach(e=>{ const k=e.getAttribute('data-i18n-ph');
    if(I18N[L][k]!==undefined) e.placeholder=I18N[L][k]; });
  const lb=document.getElementById('langBtn'); if(lb) lb.textContent = L==='ko'?'EN':'한국어';
}
function setTheme(th){ localStorage.setItem('inw_theme',th);
  document.documentElement.setAttribute('data-theme',th);
  const tb=document.getElementById('themeBtn'); if(tb) tb.textContent = th==='dark'?'☀ Light':'🌙 Dark'; }
function toggleLang(){ localStorage.setItem('inw_lang', curLang()==='ko'?'en':'ko'); applyI18n(); }
function toggleTheme(){ setTheme(curTheme()==='dark'?'light':'dark'); }
// helpers
async function loadModels(id){ try{ const r=await fetch('/api/v1/models'); const d=await r.json();
  const s=document.getElementById(id); if(s) s.innerHTML=d.details.map(m=>`<option value="${m.id}">${m.name} (${m.id})</option>`).join(''); }catch(e){} }
function basename(p){ return (p||'').split(/[\\\\/]/).pop(); }
function kv(k,v){ return `<div class="kv"><b>${k}</b><span class="v">${v}</span></div>`; }
function badge(ok,txt){ return `<span class="badge ${ok?'ok':'bad'}">${txt}</span>`; }
function show(id,html){ const e=document.getElementById(id); e.innerHTML=html; e.classList.add('show'); }
// ---- interactive 3D tilt (pointer parallax) ----
function initTilt(){
  if(window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if(window.matchMedia('(hover: none)').matches) return; // skip on touch
  const MAX=10; // degrees
  document.querySelectorAll('.tile').forEach(el=>{
    el.addEventListener('pointermove', e=>{
      const r=el.getBoundingClientRect();
      const px=(e.clientX-r.left)/r.width-0.5, py=(e.clientY-r.top)/r.height-0.5;
      el.style.transform=`rotateY(${px*MAX}deg) rotateX(${-py*MAX}deg) translateZ(14px)`;
    });
    el.addEventListener('pointerleave', ()=>{ el.style.transform=''; });
  });
}
// ---- ROI / region + time picker (video) ----
// cfg: {withTime:bool} ; expects ids: file, roiwrap, stage, roibox, roi_x, roi_y, roi_w, roi_h
//      and (if withTime) start_sec, end_sec. Returns an object with isActive()/values().
function attachRoi(cfg){
  const fileEl=document.getElementById('file');
  const wrap=document.getElementById('roiwrap');
  const stage=document.getElementById('stage');
  const box=document.getElementById('roibox');
  let url=null, isVid=false;
  let bx=0,by=0,bw=100,bh=100;
  const $=(id)=>document.getElementById(id);
  function draw(){ box.style.left=bx+'%';box.style.top=by+'%';box.style.width=bw+'%';box.style.height=bh+'%'; }
  function sync(){ $('roi_x').value=Math.round(bx);$('roi_y').value=Math.round(by);
    $('roi_w').value=Math.round(bw);$('roi_h').value=Math.round(bh); }
  function setBox(x,y,w,h){ bw=Math.max(5,Math.min(100,w)); bh=Math.max(5,Math.min(100,h));
    bx=Math.max(0,Math.min(100-bw,x)); by=Math.max(0,Math.min(100-bh,y)); draw(); }
  fileEl.addEventListener('change', e=>{
    const f=e.target.files[0];
    if(!f){ wrap.style.display='none'; return; }
    isVid=(f.type||'').startsWith('video');
    if(!isVid && !cfg.alwaysShow){ wrap.style.display='none'; return; }
    if(url) URL.revokeObjectURL(url); url=URL.createObjectURL(f);
    const media = isVid ? document.createElement('video') : document.createElement('img');
    media.src=url; if(isVid){ media.controls=true; media.muted=true; media.playsInline=true; }
    stage.innerHTML=''; stage.appendChild(media); stage.appendChild(box);
    wrap.style.display='block'; setBox(0,0,100,100); sync();
    if(cfg.withTime && isVid){ media.addEventListener('loadedmetadata', ()=>{
      if(isFinite(media.duration)){ $('start_sec').value='0'; $('end_sec').value=media.duration.toFixed(1); } }); }
  });
  // drag move / resize
  let mode=null,sx,sy,o;
  box.addEventListener('pointerdown', e=>{ e.preventDefault();
    mode = e.target.classList.contains('rh') ? 'resize':'move';
    sx=e.clientX; sy=e.clientY; o={bx,by,bw,bh}; box.setPointerCapture(e.pointerId); });
  box.addEventListener('pointermove', e=>{ if(!mode) return;
    const r=stage.getBoundingClientRect();
    const dx=(e.clientX-sx)/r.width*100, dy=(e.clientY-sy)/r.height*100;
    if(mode==='move') setBox(o.bx+dx,o.by+dy,o.bw,o.bh); else setBox(o.bx,o.by,o.bw+dx,o.bh+dy);
    sync(); });
  box.addEventListener('pointerup', ()=>{ mode=null; });
  ['roi_x','roi_y','roi_w','roi_h'].forEach(id=>$(id).addEventListener('input', ()=>{
    setBox(+$('roi_x').value,+$('roi_y').value,+$('roi_w').value,+$('roi_h').value); }));
  return {
    isVideo:()=>isVid,
    appendTo:(fd)=>{
      const full = Math.round(bx)===0&&Math.round(by)===0&&Math.round(bw)===100&&Math.round(bh)===100;
      if(!full){ fd.append('roi_x',(bx/100).toFixed(4)); fd.append('roi_y',(by/100).toFixed(4));
        fd.append('roi_w',(bw/100).toFixed(4)); fd.append('roi_h',(bh/100).toFixed(4)); }
      if(cfg.withTime && isVid){ const s=$('start_sec').value, en=$('end_sec').value;
        if(s!=='') fd.append('start_sec',s); if(en!=='') fd.append('end_sec',en); }
    }
  };
}
document.documentElement.setAttribute('data-theme', curTheme());
window.addEventListener('DOMContentLoaded', ()=>{ setTheme(curTheme()); applyI18n(); initTilt(); });
"""


def _shell(title: str, active: str, body: str) -> str:
    base = _BASE_SCRIPT.replace("__I18N__", _I18N_JSON)
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title} · INJECTION-NOISE-WATERMARK</title>"
        f"<style>{_CSS}</style><script>{base}</script></head><body>"
        "<header>"
        f"<a class='brand' href='/'>{_LOGO}<span><span class='bt'>INJECTION·NOISE·<span class='grad'>WATERMARK</span></span>"
        "<div class='bs' data-i18n='brand.tag'>brand.tag</div></span></a>"
        f"<nav>{_nav(active)}</nav>"
        "<div class='ctrls'><button id='langBtn' onclick='toggleLang()'>EN</button>"
        "<button id='themeBtn' onclick='toggleTheme()'>🌙 Dark</button></div>"
        "</header>"
        f"<main>{body}</main>"
        "<footer data-i18n='footer'>footer</footer>"
        "</body></html>"
    )


@router.get("/", response_class=HTMLResponse)
async def home() -> str:
    """Dashboard."""
    body = """
    <div class="hero"><h1 data-i18n="home.title">home.title</h1>
    <p class="sub" data-i18n="home.sub">home.sub</p></div>
    <div class="grid">
      <div class="tile"><h3 data-i18n="tile.embed.t"></h3><p data-i18n="tile.embed.d"></p><a href="/ui/embed" data-i18n="tile.cta"></a></div>
      <div class="tile"><h3 data-i18n="tile.read.t"></h3><p data-i18n="tile.read.d"></p><a href="/ui/read" data-i18n="tile.cta"></a></div>
      <div class="tile"><h3 data-i18n="tile.remove.t"></h3><p data-i18n="tile.remove.d"></p><a href="/ui/remove" data-i18n="tile.cta"></a></div>
      <div class="tile"><h3 data-i18n="tile.audit.t"></h3><p data-i18n="tile.audit.d"></p><a href="/ui/audit" data-i18n="tile.cta"></a></div>
      <div class="tile"><h3 data-i18n="tile.models.t"></h3><p data-i18n="tile.models.d"></p><a href="/ui/models" data-i18n="tile.cta"></a></div>
      <div class="tile"><h3 data-i18n="tile.api.t"></h3><p data-i18n="tile.api.d"></p><a href="/docs" data-i18n="tile.cta"></a></div>
    </div>
    """
    return _shell("Dashboard", "home", body)


@router.get("/ui/embed", response_class=HTMLResponse)
async def embed_page() -> str:
    """Insert page."""
    body = """
    <div class="hero"><h1 data-i18n="embed.title"></h1><p class="sub" data-i18n="embed.sub"></p></div>
    <div class="card">
      <form id="f">
        <label data-i18n="f.file"></label>
        <input type="file" id="file" accept="image/*,video/*" required>
        <div class="row">
          <div><label data-i18n="f.kind"></label>
            <select id="kind"><option value="image" data-i18n="kind.image"></option><option value="video" data-i18n="kind.video"></option></select></div>
          <div><label data-i18n="f.model"></label><select id="model"></select></div>
        </div>
        <div class="row">
          <div><label data-i18n="f.asset"></label><input id="asset_id" value="ASSET-001" required></div>
          <div><label data-i18n="f.client"></label><input id="client_id" value="CLIENT-A" required></div>
        </div>
        <div class="row">
          <div><label data-i18n="f.recipient"></label><input id="recipient_id" value="studio@partner.com" required></div>
          <div><label data-i18n="f.dist"></label><input id="distribution_id" value="OTT-KR"></div>
        </div>
        <label><span data-i18n="f.strength"></span>: <span id="sv">0.20</span></label>
        <input type="range" id="strength" min="0.05" max="0.4" step="0.01" value="0.20"
               oninput="document.getElementById('sv').textContent=this.value">

        <div class="roiwrap" id="roiwrap">
          <label data-i18n="roi.region"></label>
          <div class="stage" id="stage"><div class="roibox" id="roibox"><div class="rh"></div></div></div>
          <div class="roifields">
            <div><label data-i18n="roi.x"></label><input id="roi_x" type="number" value="0"></div>
            <div><label data-i18n="roi.y"></label><input id="roi_y" type="number" value="0"></div>
            <div><label data-i18n="roi.w"></label><input id="roi_w" type="number" value="100"></div>
            <div><label data-i18n="roi.h"></label><input id="roi_h" type="number" value="100"></div>
          </div>
          <div class="roifields">
            <div><label data-i18n="roi.start"></label><input id="start_sec" type="number" step="0.1" value="0"></div>
            <div><label data-i18n="roi.end"></label><input id="end_sec" type="number" step="0.1" value=""></div>
          </div>
          <div class="roihint" data-i18n="roi.hint"></div>
        </div>

        <button type="submit" class="go" id="go" data-i18n="btn.embed"></button>
      </form>
      <div class="result" id="res"></div>
    </div>
    <script>
    loadModels('model');
    const roi = attachRoi({withTime:true});
    document.getElementById('file').addEventListener('change', e=>{
      const f=e.target.files[0]; if(!f) return; const k=document.getElementById('kind');
      if((f.type||'').startsWith('video')) k.value='video';
      else if((f.type||'').startsWith('image')) k.value='image';
    });
    document.getElementById('f').addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      const b=document.getElementById('go'); b.disabled=true; b.textContent=t('btn.embed.busy');
      const fd=new FormData();
      fd.append('file', document.getElementById('file').files[0]);
      for(const k of ['asset_id','client_id','recipient_id','model','strength','distribution_id'])
        fd.append(k, document.getElementById(k).value);
      const isVideo = document.getElementById('kind').value==='video';
      if(isVideo) roi.appendTo(fd);
      const url = isVideo ? '/api/v1/video/embed' : '/api/v1/embed';
      try{
        const r=await fetch(url,{method:'POST',body:fd}); const d=await r.json();
        if(!r.ok){ show('res', badge(false,t('badge.error'))+' '+(d.detail||'')); }
        else{ const dl='/api/v1/assets/'+basename(d.output_uri);
          show('res', badge(true,t('badge.watermarked'))
            +kv(t('kv.delivery'),d.delivery_id)+kv(t('kv.token'),d.token_id)+kv(t('kv.model'),d.model)
            +kv(t('kv.psnr'),d.psnr)+kv(t('kv.ssim'),d.ssim)
            +`<a class="dl" href="${dl}" download>${t('dl.file')}</a>`); }
      }catch(e){ show('res', badge(false,t('badge.error'))+' '+e); }
      b.disabled=false; b.textContent=t('btn.embed');
    });
    </script>
    """
    return _shell("Insert", "embed", body)


@router.get("/ui/read", response_class=HTMLResponse)
async def read_page() -> str:
    """Read / trace page."""
    body = """
    <div class="hero"><h1 data-i18n="read.title"></h1><p class="sub" data-i18n="read.sub"></p></div>
    <div class="card">
      <form id="f">
        <label data-i18n="f.file"></label>
        <input type="file" id="file" accept="image/*,video/*" required>
        <div class="row">
          <div><label data-i18n="f.kind"></label>
            <select id="kind"><option value="image" data-i18n="kind.image"></option><option value="video" data-i18n="kind.video"></option></select></div>
          <div><label data-i18n="f.client_opt"></label><input id="client_id" value="CLIENT-A"></div>
        </div>

        <div class="roiwrap" id="roiwrap">
          <label data-i18n="roi.read_region"></label>
          <div class="stage" id="stage"><div class="roibox" id="roibox"><div class="rh"></div></div></div>
          <div class="roifields">
            <div><label data-i18n="roi.x"></label><input id="roi_x" type="number" value="0"></div>
            <div><label data-i18n="roi.y"></label><input id="roi_y" type="number" value="0"></div>
            <div><label data-i18n="roi.w"></label><input id="roi_w" type="number" value="100"></div>
            <div><label data-i18n="roi.h"></label><input id="roi_h" type="number" value="100"></div>
          </div>
        </div>

        <button type="submit" class="go" id="go" data-i18n="btn.read"></button>
      </form>
      <div class="result" id="res"></div>
    </div>
    <script>
    const roi = attachRoi({withTime:false});
    document.getElementById('file').addEventListener('change', e=>{
      const f=e.target.files[0]; if(!f) return; const k=document.getElementById('kind');
      if((f.type||'').startsWith('video')) k.value='video';
      else if((f.type||'').startsWith('image')) k.value='image';
    });
    document.getElementById('f').addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      const b=document.getElementById('go'); b.disabled=true; b.textContent=t('btn.read.busy');
      const fd=new FormData(); fd.append('file', document.getElementById('file').files[0]);
      const cid=document.getElementById('client_id').value; if(cid) fd.append('client_id', cid);
      const isVideo = document.getElementById('kind').value==='video';
      if(isVideo) roi.appendTo(fd);
      const url = isVideo ? '/api/v1/video/trace' : '/api/v1/trace';
      try{
        const r=await fetch(url,{method:'POST',body:fd}); const d=await r.json();
        if(!r.ok){ show('res', badge(false,t('badge.error'))+' '+(d.detail||'')); }
        else if(d.found){ show('res', badge(true,t('badge.found'))
            +kv(t('kv.recipient'),d.recipient)+kv(t('kv.asset'),d.asset_id)+kv(t('kv.delivery'),d.delivery_id)
            +kv(t('kv.model'),d.watermark_model)+kv(t('kv.confidence'),(d.confidence*100).toFixed(1)+'%')
            +kv(t('kv.signature'), d.signature_valid?t('sig.valid'):t('sig.invalid'))
            +kv(t('kv.chain'),(d.trace_path||[]).join(' → '))); }
        else { show('res', badge(false,t('badge.notfound'))+`<div class="hint">${t('msg.notfound')}</div>`); }
      }catch(e){ show('res', badge(false,t('badge.error'))+' '+e); }
      b.disabled=false; b.textContent=t('btn.read');
    });
    </script>
    """
    return _shell("Read", "read", body)


@router.get("/ui/remove", response_class=HTMLResponse)
async def remove_page() -> str:
    """Remove page."""
    body = """
    <div class="hero"><h1 data-i18n="remove.title"></h1><p class="sub" data-i18n="remove.sub"></p></div>
    <div class="card">
      <form id="f">
        <label data-i18n="f.file.img"></label>
        <input type="file" id="file" accept="image/*" required>
        <div class="row">
          <div><label data-i18n="f.method"></label>
            <select id="method">
              <option value="frequency_suppression" data-i18n="method.freq"></option>
              <option value="neural_denoising" data-i18n="method.neural"></option>
              <option value="template_cancellation" data-i18n="method.template"></option>
              <option value="residual_reconstruction" data-i18n="method.residual"></option>
              <option value="watermark_isolation" data-i18n="method.iso"></option>
            </select></div>
          <div><label data-i18n="f.model"></label><select id="model"></select></div>
        </div>
        <label data-i18n="f.asset_tmpl"></label>
        <input id="asset_id" value="ASSET-001">
        <button type="submit" class="go" id="go" data-i18n="btn.remove"></button>
      </form>
      <div class="result" id="res"></div>
    </div>
    <script>
    loadModels('model');
    document.getElementById('f').addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      const b=document.getElementById('go'); b.disabled=true; b.textContent=t('btn.remove.busy');
      const fd=new FormData(); fd.append('file', document.getElementById('file').files[0]);
      for(const k of ['method','model','asset_id']) fd.append(k, document.getElementById(k).value);
      fd.append('requested_by','console');
      try{
        const r=await fetch('/api/v1/remove',{method:'POST',body:fd}); const d=await r.json();
        if(!r.ok){ show('res', badge(false,t('badge.error'))+' '+(d.detail||'')); }
        else{ const dl='/api/v1/assets/'+basename(d.output_uri);
          show('res', badge(true,t('badge.done'))
            +kv(t('kv.method'),d.method)+kv(t('kv.detected'),d.watermark_detected)
            +kv(t('kv.success'),(d.removal_success*100).toFixed(1)+'%')+kv(t('kv.quality'),d.quality_score)
            +`<a class="dl" href="${dl}" download>${t('dl.result')}</a>`); }
      }catch(e){ show('res', badge(false,t('badge.error'))+' '+e); }
      b.disabled=false; b.textContent=t('btn.remove');
    });
    </script>
    """
    return _shell("Remove", "remove", body)


@router.get("/ui/audit", response_class=HTMLResponse)
async def audit_page() -> str:
    """Audit page."""
    body = """
    <div class="hero"><h1 data-i18n="audit.title"></h1><p class="sub" data-i18n="audit.sub"></p></div>
    <div class="card">
      <div id="status" data-i18n="audit.checking"></div>
      <table id="tbl" style="margin-top:16px"><thead><tr>
        <th>#</th><th data-i18n="th.action"></th><th data-i18n="th.actor"></th>
        <th data-i18n="th.resource"></th><th data-i18n="th.when"></th></tr></thead><tbody></tbody></table>
    </div>
    <script>
    (async ()=>{
      try{
        const v=await (await fetch('/api/v1/audit/verify')).json();
        document.getElementById('status').innerHTML =
          (v.valid?badge(true,t('audit.valid')):badge(false,t('audit.broken')))+' &nbsp; '+v.entries+' '+t('audit.entries');
        const logs=await (await fetch('/api/v1/audit/logs?limit=100')).json();
        const tb=document.querySelector('#tbl tbody');
        tb.innerHTML = logs.map((l,i)=>`<tr><td>${i+1}</td><td>${l.action}</td><td>${l.actor}</td>
          <td>${l.resource_id||''}</td><td>${(l.created_at||'').replace('T',' ').slice(0,19)}</td></tr>`).join('')
          || `<tr><td colspan=5 class="hint">${t('audit.empty')}</td></tr>`;
      }catch(e){ document.getElementById('status').innerHTML = badge(false,t('badge.error'))+' '+e; }
    })();
    </script>
    """
    return _shell("Audit", "audit", body)


@router.get("/ui/models", response_class=HTMLResponse)
async def models_page() -> str:
    """Models page."""
    body = """
    <div class="hero"><h1 data-i18n="models.title"></h1><p class="sub" data-i18n="models.sub"></p></div>
    <div class="card">
      <table id="tbl"><thead><tr>
        <th data-i18n="th.id"></th><th data-i18n="th.name"></th>
        <th data-i18n="th.media"></th><th data-i18n="th.notes"></th></tr></thead><tbody></tbody></table>
    </div>
    <script>
    (async ()=>{ const d=await (await fetch('/api/v1/models')).json();
      document.querySelector('#tbl tbody').innerHTML = d.details.map(m=>
        `<tr><td><code>${m.id}</code></td><td>${m.name}</td><td>${m.media_types.join(', ')}</td><td>${m.description}</td></tr>`).join('');
    })();
    </script>
    """
    return _shell("Models", "models", body)
