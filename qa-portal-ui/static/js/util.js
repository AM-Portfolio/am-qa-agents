/* SPT portal - shared utils + shell state */
const BASE = (window.SPT && window.SPT.root) || (document.querySelector('meta[name="api-base"]') || {}).content || "";
const GRAFANA = (window.SPT && window.SPT.grafana) || "";
function api(p){ return BASE + (p.startsWith("/") ? p : "/"+p); }
function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;"); }
function badge(st){
  if(st==="passed") return '<span class="badge passed">passed</span>';
  if(st==="running") return '<span class="badge running">running</span>';
  if(st==="partial") return '<span class="badge partial">partial</span>';
  if(st==="cancelled") return '<span class="badge cancelled">cancelled</span>';
  return '<span class="badge failed">'+(st||"failed")+'</span>';
}

function runOutcomeBadge(r){
  if(r.status === "running") return badge("running");
  if(r.status === "cancelled") return badge("cancelled");
  const pass = r.api_pass_count != null ? Number(r.api_pass_count) : null;
  const fail = r.api_fail_count != null ? Number(r.api_fail_count) : null;
  if(pass != null && fail != null && (pass > 0 || fail > 0)){
    if(fail === 0) return '<span class="badge passed">'+pass+' pass</span>';
    if(pass === 0) return '<span class="badge failed">'+fail+' fail</span>';
    return '<span class="badge partial">'+pass+' pass · '+fail+' fail</span>';
  }
  return badge(r.status);
}

function testTypeLabel(tt){
  const t = String(tt || "k6").toLowerCase();
  if(t === "playwright") return "UI";
  if(t === "mixed") return "UI+API";
  return "API";
}

function runOutcomeLine(r){
  const pass = r.api_pass_count != null ? Number(r.api_pass_count) : null;
  const fail = r.api_fail_count != null ? Number(r.api_fail_count) : null;
  const total = r.api_count != null ? Number(r.api_count) : ((pass||0)+(fail||0));
  if(pass == null && fail == null) return "";
  const tt = String(r.test_type || "k6").toLowerCase();
  const noun = tt === "playwright" ? "UI steps" : (tt === "mixed" ? "steps" : "APIs");
  return '<div class="outcome"><span class="pill">'+esc(testTypeLabel(tt))+'</span> '+esc(noun)+' '+esc(total)+' · <span class="ok">'+esc(pass||0)+' pass</span> · <span class="bad">'+esc(fail||0)+' fail</span></div>';
}

function fmtT(iso){ if(!iso) return "—"; try{return new Date(iso).toLocaleString();}catch(e){return iso||"—";} }

function clearDocumentCookies(){
  const parts = (document.cookie || "").split(";");
  const paths = ["/", location.pathname || "/", (BASE || "") + "/", (BASE || "") + "/ui"];
  const uniqPaths = Array.from(new Set(paths.filter(Boolean)));
  parts.forEach(raw=>{
    const name = String(raw||"").split("=")[0].trim();
    if(!name) return;
    uniqPaths.forEach(p=>{
      document.cookie = name+"=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path="+p;
      document.cookie = name+"=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path="+p+";SameSite=Lax";
    });
  });
}

function clearSptLocalStorage(){
  const drop = [];
  try {
    for(let i=0;i<localStorage.length;i++){
      const k = localStorage.key(i);
      if(k && (k.indexOf("spt_")===0 || k.indexOf("SPT_")===0)) drop.push(k);
    }
  } catch(_){}
  drop.forEach(k=>{ try { localStorage.removeItem(k); } catch(_){} });
  try { sessionStorage.clear(); } catch(_){}
}

async function clearHttpCacheStorage(){
  if(!window.caches || !caches.keys) return 0;
  try {
    const keys = await caches.keys();
    await Promise.all(keys.map(k=> caches.delete(k)));
    return keys.length;
  } catch(_){ return 0; }
}

/**
 * Clear browser SPT state + server OpenAPI/token caches, then hard-reload.
 * Keeps the current URL (service/env query) so you land back on the same screen.
 */
async function clearSptCacheAndCookies(){
  if(!confirm("Clear Test Agent cache & cookies?\n\n• Browser: localStorage (spt_*), sessionStorage, cookies, Cache Storage\n• Server: OpenAPI doc cache + try-token\n\nThe page will reload.")) return;
  showBanner("Clearing cache…");
  let serverOk = false;
  try {
    const r = await fetch(api("/api/platform/clear-cache"), { method: "POST", headers: { "Accept": "application/json" } });
    serverOk = r.ok;
  } catch(_){ serverOk = false; }
  clearSptLocalStorage();
  clearDocumentCookies();
  await clearHttpCacheStorage();
  try {
    if(typeof serviceApisCache !== "undefined") serviceApisCache = {};
    if(typeof specsCache !== "undefined") specsCache = {};
    if(typeof specsVersionsCache !== "undefined") specsVersionsCache = {};
    if(typeof specsTryToken !== "undefined"){ specsTryToken = null; specsTryTokenAt = 0; }
  } catch(_){}
  showBanner(serverOk
    ? "Cache cleared — reloading…"
    : "Browser cache cleared (server clear failed) — reloading…");
  setTimeout(()=> location.reload(), 250);
}

/** Client-side Grafana deep-link (mirrors app/grafana_links.py). */
function grafanaRunUrl(r){
  const base = (GRAFANA || "").replace(/\/$/,"");
  if(!base || !r) return "";
  const pad = 30 * 60 * 1000;
  let fromMs = r.started_at ? Date.parse(r.started_at) : Date.now();
  let toMs = r.finished_at ? Date.parse(r.finished_at) : (r.started_at ? Date.parse(r.started_at) : Date.now());
  if(!Number.isFinite(fromMs)) fromMs = Date.now();
  if(!Number.isFinite(toMs)) toMs = fromMs;
  fromMs -= pad;
  toMs += pad;
  if(toMs <= fromMs) toMs = fromMs + 60 * 60 * 1000;
  const q = new URLSearchParams({
    orgId: "1",
    from: String(fromMs),
    to: String(toMs),
    "var-service": r.service || "All",
    "var-environment": r.environment || "All",
    "var-run_id": r.id || "All",
    "var-api_id": "All"
  });
  return base + "/d/spt-load-testing/spt-load-testing?" + q.toString();
}
function grafanaEmbedUrl(r){
  const u = grafanaRunUrl(r);
  return u ? u + "&kiosk=tv" : "";
}
