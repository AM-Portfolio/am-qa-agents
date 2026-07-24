let mode="runs", runs=[], configs=[], catalog={}, selectedRunId=null, selectedConfigId=null, editPayloads={};
let sidebarError = "";
let runPollTimer = null;
let selectedApiIds = null; // null = all APIs; string[] = subset
let serviceApisCache = {}; // service -> apis list
const RUNS_PAGE_SIZE = 10;
let runsPage = 1;
let runsTotal = 0;

function setSidebarMessage(msg){ sidebarError = msg || ""; document.getElementById("sidebar-list").innerHTML = '<div class="empty">'+esc(msg)+'</div>'; }
function updateCounts(){
  const rc = document.getElementById("runs-count");
  const cc = document.getElementById("configs-count");
  const sc = document.getElementById("specs-count");
  const runsN = runsTotal || (runs && runs.length) || 0;
  const configsN = (configs && configs.length) || 0;
  const specsN = (typeof specsList !== "undefined" && specsList && specsList.length) || 0;
  if(rc) rc.textContent = runsN ? String(runsN) : "";
  if(cc) cc.textContent = configsN ? String(configsN) : "";
  if(sc) sc.textContent = specsN ? String(specsN) : "";
  setRailBadge("rail-runs-count", runsN);
  setRailBadge("rail-configs-count", configsN);
  setRailBadge("rail-specs-count", specsN);
}

function setRailBadge(id, n){
  const el = document.getElementById(id);
  if(!el) return;
  if(n > 0){
    el.textContent = n > 99 ? "99+" : String(n);
    el.classList.add("on");
  } else {
    el.textContent = "";
    el.classList.remove("on");
  }
}

function syncRailActive(){
  ["runs","configs","specs"].forEach(m=>{
    const btn = document.getElementById("rail-"+m);
    if(btn) btn.classList.toggle("active", mode === m);
  });
}

/** Collapsed rail: jump to mode and expand so the list (profiles / OpenAPI / runs) is usable. */
async function railGo(m){
  if(document.body.classList.contains("sidebar-collapsed")){
    document.body.classList.remove("sidebar-collapsed");
    localStorage.setItem("spt_sidebar_collapsed", "0");
    const btn = document.getElementById("btn-toggle-sidebar");
    if(btn) btn.textContent = "Hide list";
  }
  await setMode(m);
}

async function railAction(kind){
  if(kind === "new-profile"){
    if(document.body.classList.contains("sidebar-collapsed")){
      document.body.classList.remove("sidebar-collapsed");
      localStorage.setItem("spt_sidebar_collapsed", "0");
      const btn = document.getElementById("btn-toggle-sidebar");
      if(btn) btn.textContent = "Hide list";
    }
    await setMode("configs");
    if(typeof newConfig === "function") newConfig();
    return;
  }
  if(kind === "apis"){
    if(typeof toggleApiPicker === "function") toggleApiPicker();
    return;
  }
  if(kind === "ui-flows"){
    const tt = document.getElementById("run-test-type");
    if(tt && tt.value === "k6"){
      tt.value = "playwright";
      if(typeof onTestTypeChange === "function") await onTestTypeChange();
      return;
    }
    if(typeof ensureUiProfilesLoaded === "function") await ensureUiProfilesLoaded(true);
    if(typeof showUiFlowsWorkspace === "function") showUiFlowsWorkspace();
  }
}

async function fetchJson(path, opts){
  opts = Object.assign({}, opts || {});
  const timeoutMs = opts.timeoutMs != null ? opts.timeoutMs : 8000;
  delete opts.timeoutMs;
  if(!opts.signal && typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function"){
    opts.signal = AbortSignal.timeout(timeoutMs);
  }
  try {
    const r = await fetch(api(path), opts);
    if(!r.ok) throw new Error(path+" HTTP "+r.status);
    return r.json();
  } catch(e){
    if(e && (e.name === "TimeoutError" || e.name === "AbortError")){
      throw new Error(path+" timed out ("+timeoutMs+"ms)");
    }
    throw e;
  }
}

function showBanner(msg){ const b=document.getElementById("banner"); b.style.display="block"; b.textContent=msg; }

function openDatePicker(el){
  if(!el) return;
  try {
    if(typeof el.showPicker === "function") el.showPicker();
  } catch(_){ /* browser may block if not a user gesture; click handler covers that */ }
}

function activeProfileId(){
  const side = document.getElementById("f-profile");
  const head = document.getElementById("run-config");
  const fromSide = side && side.value;
  const fromHead = head && head.value;
  return (fromSide || fromHead || "") || "";
}

function activeProfile(){
  const id = activeProfileId();
  if(!id) return null;
  return (configs||[]).find(c=>c.id===id) || null;
}

function syncProfileControls(profileId, opts){
  opts = opts || {};
  const id = profileId != null ? profileId : activeProfileId();
  const side = document.getElementById("f-profile");
  const head = document.getElementById("run-config");
  if(side && [].some.call(side.options, o=>o.value===id)) side.value = id;
  else if(side && id === "") side.value = "";
  if(head){
    if(id && [].some.call(head.options, o=>o.value===id)) head.value = id;
    else if(!id) head.value = "";
  }
  updateRunIdFilterState();
}

function updateRunIdFilterState(){
  const runIdEl = document.getElementById("f-run-id");
  if(!runIdEl) return;
  const hasProfile = !!activeProfileId();
  runIdEl.placeholder = hasProfile
    ? "Run ID (optional within profile)…"
    : "Run ID — pick from history or paste id…";
  runIdEl.title = hasProfile
    ? "Optional: narrow to a specific run id under the selected profile"
    : "No profile selected — browse history or filter by run id";
}

function filterParams(extra){
  const p = new URLSearchParams();
  const service = document.getElementById("f-service").value;
  const environment = document.getElementById("f-env").value;
  const status = document.getElementById("f-status").value;
  const from = document.getElementById("f-from") && document.getElementById("f-from").value;
  const to = document.getElementById("f-to") && document.getElementById("f-to").value;
  const q = document.getElementById("f-q").value.trim();
  const profileId = activeProfileId();
  const runId = (document.getElementById("f-run-id") && document.getElementById("f-run-id").value.trim()) || "";
  if(service) p.set("service", service);
  if(environment) p.set("environment", environment);
  if(status) p.set("status", status);
  if(from) p.set("from", from);
  if(to) p.set("to", to);
  if(q) p.set("q", q);
  if(profileId) p.set("config_id", profileId);
  if(runId) p.set("run_id", runId);
  if(extra){
    Object.keys(extra).forEach(k=>{
      if(extra[k] != null && extra[k] !== "") p.set(k, String(extra[k]));
    });
  }
  return p.toString() ? "?"+p.toString() : "";
}

function portalUiPath(){
  return location.pathname.replace(/\/$/, "") || "/ui";
}

function readUrlState(){
  return new URLSearchParams(location.search);
}

function applyUrlStateToFilters(params){
  params = params || readUrlState();
  const map = {
    "f-service": "service",
    "f-env": "environment",
    "f-status": "status",
    "f-from": "from",
    "f-to": "to",
    "f-q": "q",
    "f-run-id": "run_id",
    "f-profile": "config",
    "f-audience": "audience"
  };
  Object.keys(map).forEach(id=>{
    const el = document.getElementById(id);
    if(!el) return;
    const v = params.get(map[id]);
    if(v != null) el.value = v;
  });
  // Header profile mirrors sidebar / URL config=
  const cfg = params.get("config");
  if(cfg != null) syncProfileControls(cfg);
  updateRunIdFilterState();
}

function syncPortalUrl(opts){
  opts = opts || {};
  const p = new URLSearchParams();
  const service = document.getElementById("f-service") && document.getElementById("f-service").value;
  const environment = document.getElementById("f-env") && document.getElementById("f-env").value;
  const status = document.getElementById("f-status") && document.getElementById("f-status").value;
  const from = document.getElementById("f-from") && document.getElementById("f-from").value;
  const to = document.getElementById("f-to") && document.getElementById("f-to").value;
  const q = document.getElementById("f-q") && document.getElementById("f-q").value.trim();
  const runIdFilter = document.getElementById("f-run-id") && document.getElementById("f-run-id").value.trim();
  const profileId = activeProfileId();
  if(service) p.set("service", service);
  if(environment) p.set("environment", environment);
  if(status) p.set("status", status);
  if(from) p.set("from", from);
  if(to) p.set("to", to);
  if(q) p.set("q", q);
  if(runIdFilter) p.set("run_id", runIdFilter);
  // Keep profile filter across tabs (OpenAPI / Profiles / Runs)
  if(profileId) p.set("config", profileId);
  if(mode === "specs" && selectedSpecService) p.set("spec", selectedSpecService);
  else if(mode === "runs" && selectedRunId) p.set("run", selectedRunId);
  if(mode === "specs" && specsEnv) p.set("spec_env", specsEnv);
  if(mode === "specs" && typeof specsPayloadSetVersion !== "undefined" && specsPayloadSetVersion != null){
    p.set("set", String(specsPayloadSetVersion));
  }
  if(mode === "specs" && typeof specsView !== "undefined" && specsView && specsView !== "overview"){
    p.set("view", specsView);
  }
  const next = portalUiPath() + (p.toString() ? "?" + p.toString() : "");
  const cur = location.pathname.replace(/\/$/, "") + (location.search || "");
  if(next === cur) return;
  const state = { run: selectedRunId, config: profileId || selectedConfigId, mode: mode };
  if(opts.replace) history.replaceState(state, "", next);
  else history.pushState(state, "", next);
}

async function loadCatalog(){
  catalog = await fetchJson("/api/catalog");
  const ss = document.getElementById("f-service");
  ss.innerHTML = '<option value="">All services</option>' + (catalog.services||[]).map(s=>'<option value="'+esc(s.id)+'">'+esc(s.label)+'</option>').join("");
  const es = document.getElementById("f-env");
  es.innerHTML = '<option value="">All envs</option>' + (catalog.environments||[]).map(e=>'<option value="'+esc(e)+'">'+esc(e)+'</option>').join("");
}

async function loadHealth(){
  try {
    const h = await fetchJson("/api/platform/health");
    const el = document.getElementById("health-bar");
    const k6 = h.k6_binary ? '<span class="ok">k6</span>' : '<span class="bad">k6 missing</span>';
    const inf = h.influxdb && h.influxdb.configured ? '<span class="ok">influx</span>' : '<span>influx off</span>';
    el.innerHTML = k6 + ' · ' + inf + ' · Grafana · self-hosted';
    // Refresh UI agent chip in background when UI mode may be used
    try {
      if(typeof ensureUiProfilesLoaded === "function"){
        if(!_uiFlowCatalog) await ensureUiProfilesLoaded(true);
        else if(typeof updateUiAgentChip === "function") updateUiAgentChip();
      }
      const chip = document.getElementById("ui-agent-chip");
      if(chip && typeof _uiFlowCatalog !== "undefined" && _uiFlowCatalog && _uiFlowCatalog.agent){
        const ag = _uiFlowCatalog.agent;
        el.innerHTML += ag.online
          ? ' · <span class="ok">UI agent</span>'
          : ' · <span class="bad">UI agent offline</span>';
      }
    } catch(_){}
  } catch(e){ document.getElementById("health-bar").textContent = "platform check failed"; }
}

async function setMode(m){
  mode=m;
  document.body.classList.remove("mode-runs","mode-configs","mode-specs");
  document.body.classList.add("mode-"+m);
  document.getElementById("tab-runs").classList.toggle("active", m==="runs");
  document.getElementById("tab-configs").classList.toggle("active", m==="configs");
  const tabSpecs = document.getElementById("tab-specs");
  if(tabSpecs) tabSpecs.classList.toggle("active", m==="specs");
  const chev = (id, on)=>{ const el=document.getElementById(id); if(el) el.textContent = on ? "▾" : "▸"; };
  chev("tab-runs-chev", m==="runs");
  chev("tab-configs-chev", m==="configs");
  chev("tab-specs-chev", m==="specs");
  syncRailActive();
  const mainEl = document.getElementById("main");
  if(mainEl) mainEl.innerHTML = '<div class="empty">Loading…</div>';
  try {
  if(m === "specs"){
    // Prefetch Swagger assets so first paint is faster
    try { ensureSwaggerSdk(); } catch(_){}
    try { loadTryToken(false); } catch(_){}
    // Keep profile filter intact — prefer that profile's service in OpenAPI
    const prof = activeProfile();
    if(prof && prof.service){
      const svcEl = document.getElementById("f-service");
      if(svcEl && !svcEl.value) svcEl.value = prof.service;
      if(prof.environment){
        const envEl = document.getElementById("f-env");
        if(envEl && !envEl.value){
          envEl.value = prof.environment;
          specsEnv = prof.environment;
        }
      }
    }
    await refreshSpecsList();
    updateCounts();
    renderList();
    if(prof && prof.service && specsList.some(s=>s.id===prof.service)){
      await selectSpec(prof.service, { replaceUrl: true });
      return;
    }
    if(!selectedSpecService && specsList.length){
      // Prefer a registered OpenAPI service so Try it out works immediately
      const preferred = specsList.find(s=>s.source==="registration" && s.openapi_path)
        || specsList.find(s=>s.openapi_path)
        || specsList[0];
      if(preferred) await selectSpec(preferred.id, { replaceUrl: true });
      return;
    }
    if(selectedSpecService){
      renderSpecDetail();
      syncPortalUrl({ replace: true });
    } else {
      document.getElementById("main").innerHTML = '<div class="empty">Select a service to view OpenAPI.</div>';
      syncPortalUrl({ replace: true });
    }
    return;
  }
  if(m === "runs"){
    // Profile filter stays applied — list is filtered by config_id when set
    if(typeof setMainView === "function") setMainView("run");
    await refreshRuns({ resetPage: true });
    const wantRunId = (document.getElementById("f-run-id") && document.getElementById("f-run-id").value.trim()) || "";
    if(wantRunId && runs.length){
      const hit = runs.find(r=>r.id===wantRunId) || runs[0];
      await selectRun(hit.id, { replaceUrl: true });
    } else if(runs.length){
      await selectRun(runs[0].id, { replaceUrl: true });
    } else {
      stopRunWatch();
      selectedRunId = null;
      const emptyMsg = activeProfileId()
        ? 'No runs for this profile yet. Click <strong>Run test</strong> above.'
        : 'No runs match. Pick a profile, or enter a <strong>Run ID</strong>, or clear filters.';
      document.getElementById("main").innerHTML = '<div class="empty">'+emptyMsg+'</div>';
      syncPortalUrl({ replace: true });
    }
    return;
  }
  if(m === "configs"){
    await refreshConfigs();
    renderList();
    const id = (selectedConfigId && configs.some(c=>c.id===selectedConfigId))
      ? selectedConfigId
      : (configs[0] && configs[0].id);
    if(id) await selectConfig(id, { replaceUrl: true });
    else {
      selectedConfigId = null;
      document.getElementById("main").innerHTML = '<div class="empty">No profiles. Click <strong>+ New profile</strong>.</div>';
      syncPortalUrl({ replace: true });
    }
    return;
  }
  renderList();
  } catch(e){
    if(mainEl) mainEl.innerHTML = '<div class="empty"><span class="bad">'+esc(e.message||e)+'</span><p class="sub">Switch category or retry — portal stays usable.</p></div>';
    showBanner("Tab load failed: "+(e.message||e));
  }
}

async function applyFilters(){
  const verEl = document.getElementById("f-api-version");
  const head = document.getElementById("run-openapi-version");
  if(verEl && head && verEl.options.length > 1 && verEl.value !== head.value){
    head.value = verEl.value;
    if(typeof onRunOpenApiVersionChange === "function") await onRunOpenApiVersionChange();
  }
  updateRunIdFilterState();
  if(mode==="runs"){
    runsPage = 1;
    await refreshRuns();
    const wantRunId = (document.getElementById("f-run-id") && document.getElementById("f-run-id").value.trim()) || "";
    if(wantRunId && runs.length){
      const hit = runs.find(r=>r.id===wantRunId) || runs.find(r=>String(r.id).startsWith(wantRunId)) || runs[0];
      if(hit) await selectRun(hit.id, { replaceUrl: true });
    }
  }
  else if(mode==="configs") await refreshConfigs();
  else if(mode==="specs"){
    const envEl = document.getElementById("f-env");
    if(envEl && envEl.value && envEl.value !== specsEnv){
      specsEnv = envEl.value;
      if(selectedSpecService) delete specsCache[specsCacheKey(selectedSpecService, specsEnv)];
    }
    if(verEl && verEl.value && typeof parseVersionOptionValue === "function"){
      const parsed = parseVersionOptionValue(verEl.value);
      if(parsed.environment && parsed.environment !== specsEnv){
        specsEnv = parsed.environment;
        if(selectedSpecService) delete specsCache[specsCacheKey(selectedSpecService, specsEnv)];
      }
    }
    await refreshSpecsList();
    if(selectedSpecService) await renderSpecDetail();
  }
  syncPortalUrl({ replace: true });
}

async function refreshRuns(opts){
  opts = opts || {};
  if(opts.resetPage) runsPage = 1;
  setSidebarMessage("Loading runs…");
  try {
    const offset = Math.max(0, (runsPage - 1) * RUNS_PAGE_SIZE);
    const data = await fetchJson("/api/runs"+filterParams({
      limit: RUNS_PAGE_SIZE,
      offset: offset,
    }));
    runs = data.runs || [];
    runsTotal = data.total != null ? data.total : runs.length;
    const pages = Math.max(1, Math.ceil(runsTotal / RUNS_PAGE_SIZE) || 1);
    if(runsPage > pages){
      runsPage = pages;
      return refreshRuns();
    }
    sidebarError = "";
    updateCounts();
    renderList();
    await refreshConfigSelect();
  } catch(e) {
    runs = [];
    runsTotal = 0;
    updateCounts();
    setSidebarMessage("Could not load runs: "+e.message);
    renderRunsPager();
    showBanner("Runs API failed — hard-refresh AM Test Agent (/ui)");
  }
}

function runsPageCount(){
  return Math.max(1, Math.ceil((runsTotal || 0) / RUNS_PAGE_SIZE) || 1);
}

function renderRunsPager(){
  const pager = document.getElementById("runs-pager");
  if(!pager) return;
  if(mode !== "runs" || !runsTotal){
    pager.style.display = "none";
    pager.innerHTML = "";
    return;
  }
  const pages = runsPageCount();
  if(pages <= 1){
    pager.style.display = "flex";
    pager.innerHTML = '<span class="sub">'+esc(runsTotal)+' run'+(runsTotal===1?"":"s")+'</span>';
    return;
  }
  const from = (runsPage - 1) * RUNS_PAGE_SIZE + 1;
  const to = Math.min(runsTotal, runsPage * RUNS_PAGE_SIZE);
  pager.style.display = "flex";
  pager.innerHTML =
    '<button type="button" class="secondary" '+(runsPage<=1?"disabled":"")+' onclick="goRunsPage('+(runsPage-1)+')" title="Previous">‹</button>'+
    '<span class="sub">'+esc(from)+'–'+esc(to)+' of '+esc(runsTotal)+'</span>'+
    '<button type="button" class="secondary" '+(runsPage>=pages?"disabled":"")+' onclick="goRunsPage('+(runsPage+1)+')" title="Next">›</button>';
}

async function goRunsPage(page){
  const pages = runsPageCount();
  const next = Math.min(pages, Math.max(1, Number(page) || 1));
  if(next === runsPage && runs.length) return;
  runsPage = next;
  await refreshRuns();
}

async function refreshConfigs(){
  try {
    const params = new URLSearchParams();
    const svc = document.getElementById("f-service")?.value;
    const aud = document.getElementById("f-audience")?.value;
    if(svc) params.set("service", svc);
    if(aud) params.set("audience", aud);
    const qs = params.toString() ? ("?"+params.toString()) : "";
    configs = (await fetchJson("/api/configs"+qs)).configs || [];
    updateCounts();
    if(mode==="configs") renderList();
    await refreshConfigSelect();
  } catch(e) {
    configs = [];
    updateCounts();
    if(mode==="configs") setSidebarMessage("Could not load profiles: "+e.message);
  }
}

async function onProfileFilterChange(){
  const side = document.getElementById("f-profile");
  const id = side ? side.value : "";
  syncProfileControls(id);
  const c = configs.find(x=>x.id===id);
  selectedApiIds = null;
  serviceApisCache = {};
  openApiVersionCache = {};
  if(c){
    if(typeof applyProfileToHeader === "function") applyProfileToHeader(c);
    try { await refreshRunOpenApiVersionSelect(c.environment, c.openapi_version); } catch(_){}
    // Align service/env filters with profile (user can still clear)
    const svcEl = document.getElementById("f-service");
    const envEl = document.getElementById("f-env");
    if(svcEl && c.service) svcEl.value = c.service;
    if(envEl && c.environment) envEl.value = c.environment;
  }
  const btn = document.getElementById("btn-api-picker");
  if(btn) btn.textContent = "APIs (all)";
  await applyFilters();
  // If on OpenAPI with a profile, jump to that service
  if(mode === "specs" && c && c.service){
    await refreshSpecsList();
    if(specsList.some(s=>s.id===c.service)) await selectSpec(c.service, { replaceUrl: true });
  }
  // If on Profiles tab, open the profile editor
  if(mode === "configs" && id){
    await selectConfig(id, { replaceUrl: true });
  }
}

async function refreshConfigSelect(){
  if(!configs.length) configs = (await fetchJson("/api/configs")).configs || [];
  const prev = activeProfileId();
  const sel = document.getElementById("run-config");
  const side = document.getElementById("f-profile");
  const filtered = typeof configsForCurrentTestType === "function"
    ? configsForCurrentTestType()
    : configs.slice();
  const tt = typeof currentTestType === "function" ? currentTestType() : "k6";
  const allLabel = tt === "playwright"
    ? "All UI profiles"
    : (tt === "mixed" ? "All mixed/UI profiles" : "All profiles");
  const opts = ['<option value="">'+allLabel+'</option>'].concat(filtered.map(c=>{
    const aud = c.audience || "developer";
    const kind = (c.test_type || "k6");
    const tag = kind === "playwright" ? "UI" : (kind === "mixed" ? "UI+API" : "API");
    return '<option value="'+c.id+'">'+esc(c.name)+' · '+esc(aud)+' · '+esc(tag)+'</option>';
  }));
  if(sel){
    sel.innerHTML = opts.join("");
    if(prev && filtered.some(c=>c.id===prev)) sel.value = prev;
    else if(filtered.length === 1) sel.value = filtered[0].id;
    else sel.value = "";
    if(!sel._sptBound){
      sel._sptBound = true;
      sel.addEventListener("change", async ()=>{
        const sideEl = document.getElementById("f-profile");
        if(sideEl) sideEl.value = sel.value;
        await onProfileFilterChange();
      });
    }
  }
  if(side){
    side.innerHTML = opts.join("");
    if(prev && filtered.some(c=>c.id===prev)) side.value = prev;
    else if(filtered.length === 1) side.value = filtered[0].id;
    else side.value = "";
  }
  syncProfileControls(prev && filtered.some(c=>c.id===prev) ? prev : (sel && sel.value) || "");
  const c = activeProfile();
  if(c){
    if(typeof applyProfileToHeader === "function") applyProfileToHeader(c);
    if(typeof refreshRunOpenApiVersionSelect === "function"){
      try { await refreshRunOpenApiVersionSelect(c.environment, c.openapi_version); } catch(_){}
    }
  }
  updateRunIdFilterState();
}

function renderList(){
  const el = document.getElementById("sidebar-list");
  if(mode === "specs"){
    const pager = document.getElementById("runs-pager");
    if(pager){ pager.style.display = "none"; pager.innerHTML = ""; }
    renderSpecsSidebar();
    return;
  }
  if(mode === "configs"){
    const pager = document.getElementById("runs-pager");
    if(pager){ pager.style.display = "none"; pager.innerHTML = ""; }
  }
  if(sidebarError && mode==="runs"){ el.innerHTML = '<div class="empty">'+esc(sidebarError)+'</div>'; renderRunsPager(); return; }
  if(mode==="runs"){
    if(!runs.length){ el.innerHTML='<div class="empty">No runs yet. Click <strong>Run test</strong> above.</div>'; renderRunsPager(); return; }
    el.innerHTML = runs.map(r=>'<div class="item '+(r.id===selectedRunId?"active":"")+'" data-run-id="'+esc(r.id)+'">'+
      '<div><strong>'+esc(r.config_name)+'</strong> '+runOutcomeBadge(r)+'</div>'+
      runOutcomeLine(r)+
      '<div class="sub">'+esc(r.service)+' · '+fmtT(r.started_at)+' · VUs '+(r.payloads_used&&r.payloads_used.bench_run&&r.payloads_used.bench_run.vus||"—")+(r.payloads_used&&r.payloads_used.auth_env&&r.payloads_used.auth_env.username?' · '+esc(r.payloads_used.auth_env.username):'')+'</div></div>').join("");
    el.querySelectorAll("[data-run-id]").forEach(node=>{
      node.addEventListener("click", ()=> selectRun(node.getAttribute("data-run-id")));
    });
    renderRunsPager();
  } else {
    if(!configs.length){ el.innerHTML='<div class="empty">No profiles. Click <strong>+ New profile</strong>.</div>'; return; }
    el.innerHTML = configs.map(c=>{
      const aud = c.audience || "developer";
      const bench = (c.payloads&&c.payloads.bench_run) || {};
      const loadBits = [];
      if(bench.vus != null) loadBits.push("VU "+bench.vus);
      if(bench.iterations != null) loadBits.push(bench.iterations+" calls");
      else if(bench.duration) loadBits.push(String(bench.duration));
      const kind = testTypeLabel(c.test_type);
      return '<div class="item '+(c.id===selectedConfigId?"active":"")+'" data-config-id="'+esc(c.id)+'">'+
        '<div><strong>'+esc(c.name)+'</strong> <span class="pill">'+esc(kind)+'</span> <span class="pill">'+esc(aud)+'</span></div>'+
        '<div class="sub">'+esc(c.service)+' · '+esc(c.environment)+(loadBits.length?' · '+esc(loadBits.join(" / ")):"")+
          (c.ui_profile?' · '+esc(c.ui_profile):'')+'</div></div>';
    }).join("");
    el.querySelectorAll("[data-config-id]").forEach(node=>{
      node.addEventListener("click", ()=> selectConfig(node.getAttribute("data-config-id")));
    });
  }
}

async function selectRun(id, opts){
  opts = opts || {};
  stopRunWatch();
  selectedRunId=id;
  if(typeof setMainView === "function") setMainView("run");
  // Keep profile filter intact when browsing run history
  renderList();
  const r = await fetchJson("/api/runs/"+id);
  editPayloads = JSON.parse(JSON.stringify(r.payloads_used||{}));
  showRunDetail(r, {preserveApi: !!opts.preserveApi});
  if(r.status === "running") startRunWatch(id);
  if(!opts.skipUrl) syncPortalUrl({ replace: !!opts.replaceUrl });
}

function formatBytes(n){
  const x = Number(n);
  if(!isFinite(x) || x < 0) return String(n);
  if(x < 1024) return Math.round(x) + " B";
  if(x < 1024*1024) return (x/1024).toFixed(1) + " KB";
  if(x < 1024*1024*1024) return (x/(1024*1024)).toFixed(2) + " MB";
  return (x/(1024*1024*1024)).toFixed(2) + " GB";
}

function formatBytesRate(n){
  const x = Number(n);
  if(!isFinite(x) || x < 0) return String(n);
  return formatBytes(x) + "/s";
}

function metricStrip(m){
  m = m || {};
  const items = [
    {key:"throughput.requestsPerSecond", label:"RPS"},
    {key:"errorRate", label:"Fail %", fmt:v=>esc(v)+"%"},
    {key:"responseTime.p90", label:"p90 ms"},
    {key:"responseTime.avg", label:"Avg ms"},
    {key:"transfer.receivedBytes", label:"Data in", fmt:v=>esc(formatBytes(v))},
    {key:"transfer.sentBytes", label:"Data out", fmt:v=>esc(formatBytes(v))},
    {key:"transfer.receivedBytesPerSec", label:"In rate", fmt:v=>esc(formatBytesRate(v))},
    {key:"transfer.sentBytesPerSec", label:"Out rate", fmt:v=>esc(formatBytesRate(v))},
  ];
  const parts = [];
  items.forEach(it=>{
    if(m[it.key]==null) return;
    const val = it.fmt ? it.fmt(m[it.key]) : esc(m[it.key]);
    parts.push('<div class="metric"><div class="k">'+esc(it.label)+'</div><div class="n">'+val+'</div></div>');
  });
  if(!parts.length) return "";
  return '<div class="metrics">'+parts.join("")+'</div>';
}
