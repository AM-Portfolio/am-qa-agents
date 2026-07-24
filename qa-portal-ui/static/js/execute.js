function card(l,v){ return '<div class="card"><label>'+esc(l)+'</label><div class="v">'+esc(v)+'</div></div>'; }
function cardHtml(l,v){ return '<div class="card"><label>'+esc(l)+'</label><div class="v">'+v+'</div></div>'; }

let openApiVersionCache = {}; // service -> versions payload
let selectedRunOpenApiEnv = null; // env chosen in header version select
let selectedRunOpenApiVersion = null; // info.version string

function updateStopButton(running){
  const btn = document.getElementById("btn-stop-run");
  if(btn) btn.style.display = running ? "inline-block" : "none";
}

async function loadOpenApiVersions(service){
  if(!service) return [];
  if(openApiVersionCache[service]) return openApiVersionCache[service];
  try {
    const data = await fetchJson("/api/catalog/"+encodeURIComponent(service)+"/openapi/versions");
    openApiVersionCache[service] = data.environments || [];
  } catch(_){
    openApiVersionCache[service] = [];
  }
  return openApiVersionCache[service];
}

function parseVersionOptionValue(val){
  // value format: environment|version
  if(!val) return { environment: null, version: null };
  const i = String(val).indexOf("|");
  if(i < 0) return { environment: val, version: null };
  return { environment: val.slice(0,i), version: val.slice(i+1) || null };
}

async function refreshRunOpenApiVersionSelect(preferredEnv, preferredVersion){
  const sel = document.getElementById("run-openapi-version");
  if(!sel) return;
  const cfgId = document.getElementById("run-config")?.value;
  let service = "am-analysis";
  let environment = preferredEnv || selectedRunOpenApiEnv || "dev";
  let openapiVersion = preferredVersion || selectedRunOpenApiVersion || null;
  if(cfgId){
    const c = configs.find(x=>x.id===cfgId) || (await fetchJson("/api/configs/"+cfgId));
    service = c.service || service;
    environment = preferredEnv || c.environment || environment;
    openapiVersion = preferredVersion != null ? preferredVersion : (c.openapi_version || openapiVersion);
  }
  const versions = await loadOpenApiVersions(service);
  const opts = ['<option value="">API version (auto - '+esc(environment)+')</option>'];
  versions.forEach(v=>{
    const value = (v.environment||"")+"|"+(v.version||"unknown");
    const label = v.label || (v.ok ? (v.environment+" - "+(v.version||"?")) : (v.environment+" - fail"));
    const disabled = v.ok ? "" : " disabled";
    const selected = (v.environment===environment && (!openapiVersion || String(v.version)===String(openapiVersion))) ? " selected" : "";
    opts.push('<option value="'+esc(value)+'"'+disabled+selected+'>'+esc(label)+'</option>');
  });
  sel.innerHTML = opts.join("");
  // If preferred matched a disabled option, keep auto
  if(sel.selectedIndex < 0) sel.value = "";
  const cur = parseVersionOptionValue(sel.value);
  selectedRunOpenApiEnv = cur.environment || environment;
  selectedRunOpenApiVersion = cur.version && cur.version !== "unknown" ? cur.version : openapiVersion;
  syncSidebarApiVersionSelect(sel.value);
}

function syncSidebarApiVersionSelect(value){
  const side = document.getElementById("f-api-version");
  const head = document.getElementById("run-openapi-version");
  if(!side || !head) return;
  // Mirror header options into sidebar (aligned with other filters)
  if(side.innerHTML !== head.innerHTML){
    const prev = value != null ? value : side.value;
    side.innerHTML = head.innerHTML;
    if(prev && [].some.call(side.options, o=>o.value===prev)) side.value = prev;
    else if(value != null) side.value = value;
  } else if(value != null){
    side.value = value;
  }
}

async function onRunOpenApiVersionChange(){
  const sel = document.getElementById("run-openapi-version");
  const parsed = parseVersionOptionValue(sel && sel.value);
  selectedRunOpenApiEnv = parsed.environment;
  selectedRunOpenApiVersion = parsed.version && parsed.version !== "unknown" ? parsed.version : null;
  syncSidebarApiVersionSelect(sel && sel.value);
  // Changing version changes which OpenAPI catalog feeds API picker
  selectedApiIds = null;
  serviceApisCache = {};
  const btn = document.getElementById("btn-api-picker");
  if(btn) btn.textContent = "APIs (all)";
  const picker = document.getElementById("api-picker");
  if(picker && picker.style.display !== "none"){
    await toggleApiPicker(true);
  }
}

function applyOpenApiVersionToBody(body){
  const sel = document.getElementById("run-openapi-version");
  const parsed = parseVersionOptionValue(sel && sel.value);
  if(parsed.environment) body.environment = parsed.environment;
  if(parsed.version && parsed.version !== "unknown") body.openapi_version = parsed.version;
  else if(selectedRunOpenApiVersion) body.openapi_version = selectedRunOpenApiVersion;
  return body;
}

async function stopSelectedRun(runId){
  const id = runId || selectedRunId;
  if(!id) return alert("No running test selected");
  if(!confirm("Stop this load test?")) return;
  try {
    await fetchJson("/api/runs/"+id+"/stop", {method:"POST"});
    stopRunWatch();
    updateStopButton(false);
    await refreshRuns({resetPage: true});
    await selectRun(id);
  } catch(e){
    alert("Stop failed: "+e.message);
  }
}

function readSelectedApiIds(){
  if(selectedApiIds == null) return null;
  return selectedApiIds.length ? selectedApiIds.slice() : null;
}

function applyApiIdsToBody(body){
  const ids = readSelectedApiIds();
  if(ids && ids.length) body.api_ids = ids;
  return body;
}

function currentTestType(){
  return document.getElementById("run-test-type")?.value || "k6";
}

/** SPT configs visible for the selected test type (UI / API / both). */
function configsForCurrentTestType(){
  const tt = currentTestType();
  return (configs || []).filter(c=>{
    const ct = String(c.test_type || "k6").toLowerCase();
    if(tt === "playwright") return ct === "playwright" || ct === "mixed";
    if(tt === "mixed") return ct === "mixed" || ct === "playwright";
    // k6: API-only + mixed (both enabled)
    return ct === "k6" || ct === "mixed" || !c.test_type;
  });
}

function applyUiTestFieldsToBody(body){
  const tt = currentTestType();
  body.test_type = tt;
  if(tt === "k6") return body;
  const mode = document.getElementById("run-ui-mode")?.value || "profile";
  if(mode === "suite"){
    body.ui_suite = document.getElementById("run-ui-suite")?.value || "smoke";
    body.ui_profile = null;
  } else {
    const p = document.getElementById("run-ui-profile")?.value;
    if(p) body.ui_profile = p;
    body.ui_suite = null;
  }
  const formats = readSelectedReportFormats();
  if(formats.length) body.report_formats = formats;
  return body;
}

function readSelectedReportFormats(){
  const boxes = document.querySelectorAll("#run-report-formats [data-report-fmt]");
  const out = [];
  boxes.forEach(b=>{
    if(b.checked) out.push(String(b.getAttribute("data-report-fmt")||"").toLowerCase());
  });
  // Always keep at least one format
  return out.length ? out : ["html"];
}

function restoreReportFormats(formats){
  const wanted = new Set((formats||[]).map(x=>String(x).toLowerCase()));
  if(!wanted.size){ wanted.add("html"); wanted.add("pdf"); wanted.add("json"); }
  document.querySelectorAll("#run-report-formats [data-report-fmt]").forEach(b=>{
    const key = String(b.getAttribute("data-report-fmt")||"").toLowerCase();
    b.checked = wanted.has(key);
  });
}

const FALLBACK_UI_PROFILES = [
  "AUTH_FLOW_MAIN",
  "AUTH_FLOW_PORTFOLIO",
  "DASHBOARD_SMOKE_FLOW",
  "PORTFOLIO_SMOKE_FLOW",
  "PORTFOLIO_TABS_FLOW",
  "MARKET_SMOKE_FLOW",
  "TRADE_SMOKE_FLOW",
  "DOC_INTEL_SMOKE_FLOW",
  "DOC_UPLOAD_FLOW",
  "PROFILE_SMOKE_FLOW",
  "SUBSCRIPTION_SMOKE_FLOW",
  "ADMIN_GATE_FLOW",
];

let _uiFlowCatalog = null;
let _uiProfilesLoaded = false;
let _mainView = "auto"; // flows | run | config | specs | auto
let _selectedFlowId = "";
let _uiExplorerTab = "profile"; // profile | suite | run_profiles
let _uiFlowOpenGroup = null; // exclusive accordion — one flow group open at a time

function uiFlowLabel(id){
  const f = (_uiFlowCatalog && _uiFlowCatalog.flows || []).find(x => x.id === id);
  return f ? (f.label + " (" + id + ")") : id;
}

function setMainView(view){
  _mainView = view || "auto";
  document.body.classList.remove("view-flows","view-run","view-config","view-specs");
  if(view && view !== "auto") document.body.classList.add("view-"+view);
  if(view !== "flows"){
    const btn = document.getElementById("btn-ui-flow-picker");
    if(btn) btn.textContent = "Browse flows";
  }
}

function updateUiAgentChip(){
  const chip = document.getElementById("ui-agent-chip");
  if(!chip) return;
  const ag = (_uiFlowCatalog && _uiFlowCatalog.agent) || {};
  if(ag.online){
    chip.className = "ui-agent-chip ok";
    chip.textContent = "UI agent online";
    chip.title = ag.url || "ui-test-agent reachable";
  } else {
    chip.className = "ui-agent-chip bad";
    chip.textContent = "UI agent offline";
    chip.title = ag.error || (ag.url ? ("Cannot reach "+ag.url) : "SPT_UI_TEST_AGENT_URL not reachable");
  }
}

function updateUiFlowHint(){
  const hint = document.getElementById("ui-flow-hint");
  if(!hint) return;
  const mode = document.getElementById("run-ui-mode")?.value || "profile";
  if(mode === "suite"){
    const sid = document.getElementById("run-ui-suite")?.value || "smoke";
    const suite = (_uiFlowCatalog && _uiFlowCatalog.suites || []).find(s => s.id === sid);
    if(suite){
      hint.textContent = suite.summary + " · " + (suite.profiles||[]).length + " flows";
      hint.title = (suite.profiles||[]).join(", ");
    } else {
      hint.textContent = sid;
    }
    return;
  }
  const fid = document.getElementById("run-ui-profile")?.value || "";
  const flow = (_uiFlowCatalog && _uiFlowCatalog.flows || []).find(f => f.id === fid);
  hint.textContent = flow ? (flow.summary || flow.group || "") : "";
  hint.title = flow ? (flow.id + " · " + (flow.summary||"")) : "";
}

function onUiFlowSelectChange(){
  updateUiFlowHint();
  const fid = document.getElementById("run-ui-profile")?.value || "";
  if(fid) _selectedFlowId = fid;
  if(currentTestType() === "playwright" || currentTestType() === "mixed"){
    if(_mainView === "flows" && document.getElementById("flow-detail-pane")) refreshUiFlowSelection();
    else if(_mainView === "flows" || _mainView === "auto") showUiFlowsWorkspace();
  }
}

function findUiFlow(id){
  return (_uiFlowCatalog && _uiFlowCatalog.flows || []).find(f => f.id === id) || null;
}

function findUiSuite(id){
  return (_uiFlowCatalog && _uiFlowCatalog.suites || []).find(s => s.id === id) || null;
}

function agentExecutableFlowIds(){
  const det = (_uiFlowCatalog && _uiFlowCatalog.deterministic) || [];
  const fromFlows = (_uiFlowCatalog && _uiFlowCatalog.flows || [])
    .filter(f => !f.custom)
    .map(f => f.id);
  const ids = [...new Set([...(det||[]), ...fromFlows])];
  return ids.length ? ids : FALLBACK_UI_PROFILES.slice();
}

function linesToList(text){
  return String(text||"").split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
}

function renderFlowDetailHtml(flow){
  if(!flow){
    return '<div class="empty">Select a UI flow to see steps and verifications.</div>';
  }
  const steps = flow.steps || [];
  const checks = flow.verifications || [];
  const runsAs = flow.runs_as && flow.runs_as !== flow.id
    ? '<div class="sub">Runs as agent profile <code>'+esc(flow.runs_as)+'</code></div>'
    : '';
  const badge = flow.custom ? '<span class="flow-badge custom">custom</span>' : (flow.resettable ? '<span class="flow-badge">edited</span>' : '');
  let actions =
    '<button type="button" onclick="runSelectedUiFlow()">Run this flow</button>'+
    '<button type="button" class="secondary" onclick="showLastUiRunIfAny()">View last result</button>'+
    '<button type="button" class="secondary" onclick="openUiFlowEditor(\''+esc(flow.id)+'\')">Edit</button>';
  if(flow.deletable){
    actions += '<button type="button" class="secondary" onclick="deleteUiFlow(\''+esc(flow.id)+'\')">Delete</button>';
  } else if(flow.resettable){
    actions += '<button type="button" class="secondary" onclick="resetUiFlow(\''+esc(flow.id)+'\')">Reset docs</button>';
  }
  return ''+
    '<div class="flow-detail-head">'+
      '<div><h2 style="margin:0;font-size:1.05rem">'+esc(flow.label)+badge+'</h2>'+
      '<div class="sub">'+esc(flow.id)+' · '+esc(flow.group||"")+'</div>'+runsAs+'</div>'+
      '<div class="flow-detail-actions">'+actions+'</div>'+
    '</div>'+
    '<p class="sub" style="margin:.45rem 0 .75rem">'+esc(flow.summary||"")+'</p>'+
    '<div class="flow-detail-grid">'+
      '<div class="section"><div class="section-h">Steps involved <span class="sub">'+steps.length+'</span></div><div class="section-b">'+
        (steps.length
          ? '<ol class="flow-step-list">'+steps.map((s,i)=>'<li><span class="flow-step-n">'+(i+1)+'</span><span>'+esc(s)+'</span></li>').join("")+'</ol>'
          : '<div class="empty">No step docs for this flow yet.</div>')+
      '</div></div>'+
      '<div class="section"><div class="section-h">Verifications <span class="sub">'+checks.length+'</span></div><div class="section-b">'+
        (checks.length
          ? '<ul class="flow-verify-list">'+checks.map(v=>'<li><span class="flow-verify-mark" aria-hidden="true">✓</span><span>'+esc(v)+'</span></li>').join("")+'</ul>'
          : '<div class="empty">No verification docs yet.</div>')+
      '</div></div>'+
    '</div>'+
    '<p class="sub" style="margin-top:.75rem">Custom flows alias an agent profile via <code>runs_as</code>. Runner appears after <strong>Run this flow</strong>.</p>';
}

function renderSuiteDetailHtml(suite){
  if(!suite){
    return '<div class="empty">Select a suite.</div>';
  }
  const badge = suite.custom ? '<span class="flow-badge custom">custom</span>' : (suite.resettable ? '<span class="flow-badge">edited</span>' : '');
  let actions =
    '<button type="button" onclick="runSelectedUiFlow()">Run suite</button>'+
    '<button type="button" class="secondary" onclick="showLastUiRunIfAny()">View last result</button>'+
    '<button type="button" class="secondary" onclick="openUiSuiteEditor(\''+esc(suite.id)+'\')">Edit</button>';
  if(suite.deletable){
    actions += '<button type="button" class="secondary" onclick="deleteUiSuite(\''+esc(suite.id)+'\')">Delete</button>';
  } else if(suite.resettable){
    actions += '<button type="button" class="secondary" onclick="resetUiSuite(\''+esc(suite.id)+'\')">Reset</button>';
  }
  return ''+
    '<div class="flow-detail-head">'+
      '<div><h2 style="margin:0;font-size:1.05rem">'+esc(suite.label||suite.id)+badge+'</h2>'+
      '<div class="sub">Suite · '+(suite.profiles||[]).length+' flows · agent '+esc(suite.agent_suite||suite.id)+'</div></div>'+
      '<div class="flow-detail-actions">'+actions+'</div>'+
    '</div>'+
    '<p class="sub" style="margin:.45rem 0 .75rem">'+esc(suite.summary||"")+'</p>'+
    '<div class="section"><div class="section-h">Flows in suite</div><div class="section-b">'+
      '<ol class="flow-step-list">'+
        (suite.profiles||[]).map((id,i)=>{
          const f = findUiFlow(id);
          return '<li><span class="flow-step-n">'+(i+1)+'</span><span><strong>'+esc(f?f.label:id)+'</strong> <span class="sub">'+esc(id)+'</span></span></li>';
        }).join("")+
      '</ol></div></div>';
}

function renderRunProfilesPane(){
  const rows = (typeof configsForCurrentTestType === "function" ? configsForCurrentTestType() : (configs||[]))
    .filter(c => {
      const tt = String(c.test_type||"k6").toLowerCase();
      return tt === "playwright" || tt === "mixed";
    });
  if(!rows.length){
    return '<div class="empty">No Playwright run profiles yet. Click <strong>+ New run profile</strong>.</div>';
  }
  return '<div class="section"><div class="section-h">Run profiles <span class="sub">'+rows.length+'</span></div><div class="section-b">'+
    '<div class="flow-explorer-list">'+
      rows.map(c=>
        '<div class="flow-card" style="cursor:default">'+
          '<div style="display:flex;justify-content:space-between;gap:.5rem;width:100%;align-items:flex-start">'+
            '<div><strong>'+esc(c.name)+'</strong>'+
              '<span class="sub">'+esc(c.id)+' · '+esc(c.test_type||"playwright")+' · '+esc(c.audience||"")+'</span>'+
              '<span class="sub">'+(c.ui_suite ? ('Suite '+esc(c.ui_suite)) : ('Flow '+esc(c.ui_profile||"—")))+' · '+esc(c.target_url||"")+'</span></div>'+
            '<div class="flow-detail-actions">'+
              '<button type="button" class="secondary" onclick="editUiRunProfile(\''+esc(c.id)+'\')">Edit</button>'+
              '<button type="button" class="secondary" onclick="deleteUiRunProfile(\''+esc(c.id)+'\')">Delete</button>'+
              '<button type="button" onclick="executeConfig(\''+esc(c.id)+'\')">Run</button>'+
            '</div>'+
          '</div>'+
        '</div>'
      ).join("")+
    '</div></div></div>';
}

async function leaveUiFlowsWorkspace(){
  // Exit Playwright catalog back to run history (keeps test type = Playwright)
  setMainView("run");
  const btn = document.getElementById("btn-ui-flow-picker");
  if(btn) btn.textContent = "Browse flows";
  if(typeof setMode === "function"){
    await setMode("runs");
    return;
  }
  if(selectedRunId && typeof selectRun === "function"){
    await selectRun(selectedRunId, { replaceUrl: true });
    return;
  }
  if(runs.length && typeof selectRun === "function"){
    await selectRun(runs[0].id, { replaceUrl: true });
    return;
  }
  const main = document.getElementById("main");
  if(main){
    main.innerHTML = '<div class="empty">No runs yet. Pick a flow via <strong>Browse flows</strong>, then <strong>Run test</strong>.</div>';
  }
}

function showUiFlowsWorkspace(opts){
  setMainView("flows");
  const picker = document.getElementById("ui-flow-picker");
  if(picker) picker.style.display = "none";
  const api = document.getElementById("api-picker");
  if(api) api.style.display = "none";
  const browseBtn = document.getElementById("btn-ui-flow-picker");
  if(browseBtn) browseBtn.textContent = "Close flows";

  const tab = (opts && opts.tab) || _uiExplorerTab || (
    (document.getElementById("run-ui-mode")?.value === "suite") ? "suite" : "profile"
  );
  _uiExplorerTab = tab;
  if(tab === "profile" || tab === "suite"){
    const modeEl = document.getElementById("run-ui-mode");
    if(modeEl) modeEl.value = tab === "suite" ? "suite" : "profile";
    onUiModeChange();
  }

  const selectedFlow = _selectedFlowId || document.getElementById("run-ui-profile")?.value || (_uiFlowCatalog && _uiFlowCatalog.default_flow) || "";
  const selectedSuite = document.getElementById("run-ui-suite")?.value || "";
  const ag = (_uiFlowCatalog && _uiFlowCatalog.agent) || {};
  const agentLine = ag.online
    ? '<span class="ok">Agent online</span>'+(ag.url?' · '+esc(ag.url):'')
    : '<span class="bad">Agent offline</span> — catalog listed; runs need the agent'+(ag.error?' · '+esc(ag.error):'');

  let listHtml = "";
  let detail = "";
  let toolbarExtra = "";

  if(tab === "run_profiles"){
    listHtml = '<div class="empty" style="padding:.5rem">Select a run profile on the right, or create one.</div>';
    detail = renderRunProfilesPane();
    toolbarExtra = '<button type="button" onclick="createUiRunProfile()">+ New run profile</button>';
  } else if(tab === "suite"){
    toolbarExtra = '<button type="button" onclick="openUiSuiteEditor(null)">+ New suite</button>';
    listHtml = '<div class="flow-explorer-list">'+
      (_uiFlowCatalog && _uiFlowCatalog.suites || []).map(s=>{
        const on = s.id === selectedSuite;
        return '<button type="button" class="flow-card '+(on?"active":"")+'" data-suite-id="'+esc(s.id)+'" onclick="pickUiSuite(\''+esc(s.id)+'\')">'+
          '<strong>'+esc(s.label||s.id)+(s.custom?' <span class="flow-badge custom">custom</span>':'')+'</strong>'+
          '<span class="sub">'+esc(s.summary||"")+'</span>'+
          '<span class="sub">Flows: '+esc((s.profiles||[]).join(" · "))+'</span></button>';
      }).join("")+
    '</div>';
    detail = renderSuiteDetailHtml(findUiSuite(selectedSuite));
  } else {
    toolbarExtra = '<button type="button" onclick="openUiFlowEditor(null)">+ New flow</button>';
    const byGroup = {};
    (_uiFlowCatalog && _uiFlowCatalog.flows || []).forEach(f=>{
      const g = f.group || "Other";
      (byGroup[g] = byGroup[g] || []).push(f);
    });
    const groupNames = Object.keys(byGroup).sort();
    // Default open: group of selected flow, else first group ("" = all collapsed by user)
    if(_uiFlowOpenGroup == null || (_uiFlowOpenGroup && !byGroup[_uiFlowOpenGroup])){
      const sel = findUiFlow(selectedFlow);
      _uiFlowOpenGroup = (sel && (sel.group || "Other")) || groupNames[0] || null;
    }
    listHtml = '<div class="flow-explorer-list">'+
      groupNames.map(g=>{
        const open = _uiFlowOpenGroup === g;
        const n = byGroup[g].length;
        return '<div class="flow-group'+(open?"":" collapsed")+'" data-flow-group="'+esc(g)+'">'+
          '<button type="button" class="flow-group-h" onclick=\'toggleUiFlowGroup('+JSON.stringify(g)+')\' aria-expanded="'+(open?"true":"false")+'">'+
            '<span class="acc-chev">'+(open?"▾":"▸")+'</span>'+
            '<span class="acc-label">'+esc(g)+'</span>'+
            '<span class="acc-count" title="flows in this group">'+n+'</span>'+
          '</button>'+
          '<div class="flow-group-b">'+
            byGroup[g].map(f=>{
              const on = f.id === selectedFlow;
              return '<button type="button" class="flow-card '+(on?"active":"")+'" data-flow-id="'+esc(f.id)+'" onclick="pickUiFlow(\''+esc(f.id)+'\')">'+
                '<strong>'+esc(f.label)+(f.custom?' <span class="flow-badge custom">custom</span>':'')+'</strong>'+
                '<span class="pill">'+esc(f.id)+'</span>'+
                '<span class="sub">'+esc(f.summary||"")+'</span>'+
                '<span class="sub">'+(f.steps||[]).length+' steps · '+(f.verifications||[]).length+' checks'+(f.runs_as && f.runs_as!==f.id ? ' · → '+esc(f.runs_as) : '')+'</span>'+
              '</button>';
            }).join("")+
          '</div>'+
        '</div>';
      }).join("")+
    '</div>';
    detail = renderFlowDetailHtml(findUiFlow(selectedFlow));
  }

  const main = document.getElementById("main");
  if(!main) return;
  const prevScroll = document.querySelector(".flow-explorer")?.scrollTop || 0;
  main.innerHTML =
    '<div class="flow-workspace">'+
      '<div class="flow-workspace-h">'+
        '<div class="flow-workspace-title">'+
          '<button type="button" class="secondary flow-back-btn" onclick="leaveUiFlowsWorkspace()" title="Return to run history">← Back to runs</button>'+
          '<div><strong>Playwright UI</strong> <span class="sub">'+agentLine+' · '+esc(((_uiFlowCatalog&&_uiFlowCatalog.flows)||[]).length)+' flows</span></div>'+
        '</div>'+
        '<div class="flow-workspace-tabs">'+
          '<button type="button" class="secondary'+(tab==="profile"?" active":"")+'" onclick="setUiExplorerMode(\'profile\')">Flows</button>'+
          '<button type="button" class="secondary'+(tab==="suite"?" active":"")+'" onclick="setUiExplorerMode(\'suite\')">Suites</button>'+
          '<button type="button" class="secondary'+(tab==="run_profiles"?" active":"")+'" onclick="setUiExplorerMode(\'run_profiles\')">Run profiles</button>'+
          toolbarExtra+
        '</div>'+
      '</div>'+
      '<div class="flow-workspace-body">'+
        (tab === "run_profiles"
          ? '<section class="flow-detail" id="flow-detail-pane" style="grid-column:1/-1">'+detail+'</section>'
          : '<aside class="flow-explorer">'+listHtml+'</aside><section class="flow-detail" id="flow-detail-pane">'+detail+'</section>')+
      '</div>'+
    '</div>';
  const explorer = document.querySelector(".flow-explorer");
  if(explorer && prevScroll) explorer.scrollTop = prevScroll;
}

function setUiExplorerMode(mode){
  if(mode === "run_profiles"){
    _uiExplorerTab = "run_profiles";
    showUiFlowsWorkspace({ tab: "run_profiles" });
    return;
  }
  _uiExplorerTab = mode === "suite" ? "suite" : "profile";
  const el = document.getElementById("run-ui-mode");
  if(el) el.value = _uiExplorerTab === "suite" ? "suite" : "profile";
  onUiModeChange();
  showUiFlowsWorkspace({ tab: _uiExplorerTab });
}

async function reloadUiCatalogAndWorkspace(opts){
  _uiProfilesLoaded = false;
  await ensureUiProfilesLoaded(true);
  if(_mainView === "flows") showUiFlowsWorkspace(opts || { tab: _uiExplorerTab });
}

function openUiFlowEditor(id){
  const create = !id;
  const flow = create ? {
    id: "", label: "", group: "Custom", summary: "", steps: [], verifications: [],
    runs_as: agentExecutableFlowIds()[0] || "AUTH_FLOW_MAIN", custom: true
  } : (findUiFlow(id) || { id });
  const execOpts = agentExecutableFlowIds().map(x=>
    '<option value="'+esc(x)+'"'+(x===(flow.runs_as||flow.id)?" selected":"")+'>'+esc(x)+'</option>'
  ).join("");
  const pane = document.getElementById("flow-detail-pane");
  if(!pane) return;
  pane.innerHTML =
    '<div class="flow-form">'+
      '<h2 style="margin:0 0 .5rem;font-size:1.05rem">'+(create?"New flow":"Edit flow")+'</h2>'+
      '<p class="sub">'+(flow.custom || create
        ? "Custom flows must set <code>runs_as</code> to an agent profile."
        : "Builtin flow — saves documentation overrides only.")+'</p>'+
      '<label>ID</label><input id="uf-id" value="'+esc(flow.id)+'" '+(create?"":"readonly")+' placeholder="MY_FLOW_ALIAS"/>'+
      '<label>Label</label><input id="uf-label" value="'+esc(flow.label||"")+'"/>'+
      '<label>Group</label><input id="uf-group" value="'+esc(flow.group||"Custom")+'"/>'+
      '<label>Summary</label><input id="uf-summary" value="'+esc(flow.summary||"")+'"/>'+
      ((flow.custom || create)
        ? '<label>Runs as (agent profile)</label><select id="uf-runs-as">'+execOpts+'</select>'
        : '')+
      '<label>Steps (one per line)</label><textarea id="uf-steps">'+esc((flow.steps||[]).join("\n"))+'</textarea>'+
      '<label>Verifications (one per line)</label><textarea id="uf-checks">'+esc((flow.verifications||[]).join("\n"))+'</textarea>'+
      '<div class="flow-detail-actions" style="margin-top:.75rem">'+
        '<button type="button" onclick="saveUiFlowEditor('+(create?"true":"false")+')">Save</button>'+
        '<button type="button" class="secondary" onclick="refreshUiFlowSelection()">← Back</button>'+
      '</div>'+
    '</div>';
}

async function saveUiFlowEditor(isCreate){
  const id = (document.getElementById("uf-id")?.value || "").trim();
  if(!id) return alert("Flow id required");
  const body = {
    label: document.getElementById("uf-label")?.value || id,
    group: document.getElementById("uf-group")?.value || "Custom",
    summary: document.getElementById("uf-summary")?.value || "",
    steps: linesToList(document.getElementById("uf-steps")?.value),
    verifications: linesToList(document.getElementById("uf-checks")?.value),
  };
  const runsAs = document.getElementById("uf-runs-as")?.value;
  if(runsAs) body.runs_as = runsAs;
  try {
    if(isCreate){
      body.id = id;
      await fetchJson("/api/ui-test/flows", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body) });
    } else {
      await fetchJson("/api/ui-test/flows/"+encodeURIComponent(id), { method:"PUT", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body) });
    }
    _selectedFlowId = id;
    await reloadUiCatalogAndWorkspace({ tab: "profile" });
    pickUiFlow(id);
  } catch(e){
    alert(e.message || String(e));
  }
}

async function deleteUiFlow(id){
  if(!confirm("Delete custom flow "+id+"?")) return;
  try {
    await fetchJson("/api/ui-test/flows/"+encodeURIComponent(id), { method:"DELETE" });
    await reloadUiCatalogAndWorkspace({ tab: "profile" });
  } catch(e){ alert(e.message || String(e)); }
}

async function resetUiFlow(id){
  if(!confirm("Reset documentation overrides for "+id+"?")) return;
  try {
    await fetchJson("/api/ui-test/flows/"+encodeURIComponent(id)+"?reset=1", { method:"DELETE" });
    await reloadUiCatalogAndWorkspace({ tab: "profile" });
    pickUiFlow(id);
  } catch(e){ alert(e.message || String(e)); }
}

function openUiSuiteEditor(id){
  const create = !id;
  const suite = create ? {
    id: "", label: "", summary: "", profiles: [], agent_suite: "smoke", custom: true
  } : (findUiSuite(id) || { id });
  const selected = new Set(suite.profiles || []);
  const checks = (_uiFlowCatalog && _uiFlowCatalog.flows || []).map(f=>
    '<label><input type="checkbox" data-flow-check value="'+esc(f.id)+'"'+(selected.has(f.id)?" checked":"")+'/> '+
      esc(f.label)+' <span class="sub">'+esc(f.id)+'</span></label>'
  ).join("");
  const pane = document.getElementById("flow-detail-pane");
  if(!pane) return;
  pane.innerHTML =
    '<div class="flow-form">'+
      '<h2 style="margin:0 0 .5rem;font-size:1.05rem">'+(create?"New suite":"Edit suite")+'</h2>'+
      '<label>ID</label><input id="us-id" value="'+esc(suite.id)+'" '+(create?"":"readonly")+' placeholder="nightly_core"/>'+
      '<label>Label</label><input id="us-label" value="'+esc(suite.label||"")+'"/>'+
      '<label>Summary</label><input id="us-summary" value="'+esc(suite.summary||"")+'"/>'+
      '<label>Agent suite wrapper</label><select id="us-agent">'+
        '<option value="smoke"'+(String(suite.agent_suite||"smoke")==="smoke"?" selected":"")+'>smoke</option>'+
        '<option value="release_gate"'+(String(suite.agent_suite||"")==="release_gate"?" selected":"")+'>release_gate</option>'+
      '</select>'+
      '<label>Flows in suite</label><div class="flow-check-list" id="us-flows">'+checks+'</div>'+
      '<div class="flow-detail-actions" style="margin-top:.75rem">'+
        '<button type="button" onclick="saveUiSuiteEditor('+(create?"true":"false")+')">Save</button>'+
        '<button type="button" class="secondary" onclick="refreshUiFlowSelection()">← Back</button>'+
      '</div>'+
    '</div>';
}

async function saveUiSuiteEditor(isCreate){
  const id = (document.getElementById("us-id")?.value || "").trim();
  if(!id) return alert("Suite id required");
  const profiles = [];
  document.querySelectorAll("#us-flows [data-flow-check]:checked").forEach(el => profiles.push(el.value));
  if(!profiles.length) return alert("Pick at least one flow");
  const body = {
    label: document.getElementById("us-label")?.value || id,
    summary: document.getElementById("us-summary")?.value || "",
    profiles,
    agent_suite: document.getElementById("us-agent")?.value || "smoke",
  };
  try {
    if(isCreate){
      body.id = id;
      await fetchJson("/api/ui-test/suites", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body) });
    } else {
      await fetchJson("/api/ui-test/suites/"+encodeURIComponent(id), { method:"PUT", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body) });
    }
    const sel = document.getElementById("run-ui-suite");
    if(sel){
      if(![].some.call(sel.options, o=>o.value===id)){
        const opt = document.createElement("option");
        opt.value = id; opt.textContent = body.label || id;
        sel.appendChild(opt);
      }
      sel.value = id;
    }
    await reloadUiCatalogAndWorkspace({ tab: "suite" });
    pickUiSuite(id);
  } catch(e){
    alert(e.message || String(e));
  }
}

async function deleteUiSuite(id){
  if(!confirm("Delete custom suite "+id+"?")) return;
  try {
    await fetchJson("/api/ui-test/suites/"+encodeURIComponent(id), { method:"DELETE" });
    await reloadUiCatalogAndWorkspace({ tab: "suite" });
  } catch(e){ alert(e.message || String(e)); }
}

async function resetUiSuite(id){
  if(!confirm("Reset overrides for suite "+id+"?")) return;
  try {
    await fetchJson("/api/ui-test/suites/"+encodeURIComponent(id)+"?reset=1", { method:"DELETE" });
    await reloadUiCatalogAndWorkspace({ tab: "suite" });
    pickUiSuite(id);
  } catch(e){ alert(e.message || String(e)); }
}

async function createUiRunProfile(){
  try {
    const c = await fetchJson("/api/configs/default");
    const base = Object.assign({}, c);
    delete base.id; delete base.created_at; delete base.updated_at;
    base.name = "playwright-profile";
    base.description = "Playwright UI run profile";
    base.test_type = "playwright";
    base.service = "am-modern-ui";
    base.audience = document.getElementById("f-audience")?.value || "developer";
    base.ui_profile = _selectedFlowId || document.getElementById("run-ui-profile")?.value || "AUTH_FLOW_MAIN";
    base.ui_suite = null;
    base.login_mode = base.login_mode || "demo";
    const saved = await fetchJson("/api/configs", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(base) });
    if(typeof refreshConfigs === "function") await refreshConfigs();
    if(typeof selectConfig === "function") await selectConfig(saved.id);
  } catch(e){
    alert(e.message || String(e));
  }
}

async function editUiRunProfile(id){
  if(typeof setMode === "function") await setMode("configs");
  if(typeof selectConfig === "function") await selectConfig(id);
}

async function deleteUiRunProfile(id){
  if(!confirm("Delete run profile "+id+"?")) return;
  try {
    await fetchJson("/api/profiles/"+encodeURIComponent(id), { method:"DELETE" });
    if(typeof refreshConfigs === "function") await refreshConfigs();
    showUiFlowsWorkspace({ tab: "run_profiles" });
  } catch(e){ alert(e.message || String(e)); }
}

async function runSelectedUiFlow(){
  if(typeof executeSelected === "function") await executeSelected();
}

async function showLastUiRunIfAny(){
  if(typeof setMode === "function") await setMode("runs");
  const uiRuns = (runs||[]).filter(r => String(r.test_type||"") === "playwright" || String(r.test_type||"") === "mixed");
  if(uiRuns.length && typeof selectRun === "function"){
    await selectRun(uiRuns[0].id, { replaceUrl: true });
    return;
  }
  const main = document.getElementById("main");
  if(main) main.innerHTML = '<div class="empty">No UI run results yet. Pick a flow and click <strong>Run this flow</strong>.</div>';
}

async function ensureUiProfilesLoaded(force){
  const sel = document.getElementById("run-ui-profile");
  const suiteSel = document.getElementById("run-ui-suite");
  if(!sel) return;
  if(_uiProfilesLoaded && !force && sel.options.length > 1) {
    updateUiAgentChip();
    updateUiFlowHint();
    return;
  }
  const cur = sel.value;
  try {
    _uiFlowCatalog = await fetchJson("/api/ui-test/profiles");
  } catch(e){
    _uiFlowCatalog = {
      agent: { online: false, error: String(e.message||e) },
      flows: FALLBACK_UI_PROFILES.map(id => ({ id, label: id, group: "Other", summary: "", steps: [], verifications: [], custom: false, editable: true, deletable: false, resettable: false, runs_as: id })),
      suites: [
        { id: "smoke", label: "Smoke suite", summary: "Quick gate", profiles: ["AUTH_FLOW_MAIN","DASHBOARD_SMOKE_FLOW","PORTFOLIO_SMOKE_FLOW"], agent_suite: "smoke", custom: false, editable: true, deletable: false, resettable: false },
        { id: "release_gate", label: "Release gate", summary: "Full checklist", profiles: FALLBACK_UI_PROFILES.slice(0,6), agent_suite: "release_gate", custom: false, editable: true, deletable: false, resettable: false },
      ],
      deterministic: FALLBACK_UI_PROFILES,
      default_flow: "AUTH_FLOW_MAIN",
    };
  }
  const flows = _uiFlowCatalog.flows || [];
  const byGroup = {};
  flows.forEach(f=>{
    const g = f.group || "Other";
    (byGroup[g] = byGroup[g] || []).push(f);
  });
  const opts = ['<option value="">Choose UI flow…</option>'];
  Object.keys(byGroup).sort().forEach(g=>{
    opts.push('<optgroup label="'+esc(g)+'">');
    byGroup[g].forEach(f=>{
      opts.push('<option value="'+esc(f.id)+'" title="'+esc(f.summary||"")+'">'+esc(f.label)+'</option>');
    });
    opts.push('</optgroup>');
  });
  sel.innerHTML = opts.join("");
  const prefer = cur || _selectedFlowId || _uiFlowCatalog.default_flow || "AUTH_FLOW_MAIN";
  if(prefer && [].some.call(sel.options, o=>o.value===prefer)) sel.value = prefer;
  else if(flows[0]) sel.value = flows[0].id;
  _selectedFlowId = sel.value || _selectedFlowId;

  if(suiteSel){
    const suites = _uiFlowCatalog.suites || [];
    const sCur = suiteSel.value;
    suiteSel.innerHTML = suites.map(s=>
      '<option value="'+esc(s.id)+'" title="'+esc(s.summary||"")+'">'+esc(s.label||s.id)+'</option>'
    ).join("") || '<option value="smoke">smoke</option>';
    if(sCur && [].some.call(suiteSel.options, o=>o.value===sCur)) suiteSel.value = sCur;
    else if(_uiFlowCatalog.default_suite) suiteSel.value = _uiFlowCatalog.default_suite;
  }

  _uiProfilesLoaded = true;
  updateUiAgentChip();
  updateUiFlowHint();
}

function onUiModeChange(){
  const mode = document.getElementById("run-ui-mode")?.value || "profile";
  const prof = document.getElementById("run-ui-profile");
  const suite = document.getElementById("run-ui-suite");
  if(prof) prof.style.display = mode === "profile" ? "" : "none";
  if(suite) suite.style.display = mode === "suite" ? "" : "none";
  updateUiFlowHint();
}

function toggleUiFlowGroup(group){
  // Exclusive accordion: open this group only (click again to collapse)
  _uiFlowOpenGroup = (_uiFlowOpenGroup === group) ? "" : group;
  showUiFlowsWorkspace({ tab: "profile" });
}

function pickUiFlow(id){
  _uiExplorerTab = "profile";
  const mode = document.getElementById("run-ui-mode");
  if(mode) mode.value = "profile";
  onUiModeChange();
  const sel = document.getElementById("run-ui-profile");
  if(sel){
    if(![].some.call(sel.options, o=>o.value===id)){
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = uiFlowLabel(id);
      sel.appendChild(opt);
    }
    sel.value = id;
  }
  _selectedFlowId = id;
  const flow = findUiFlow(id);
  if(flow) _uiFlowOpenGroup = flow.group || "Other";
  updateUiFlowHint();
  if(_mainView === "flows" && document.getElementById("flow-detail-pane") && _uiExplorerTab === "profile"){
    refreshUiFlowSelection();
  } else {
    showUiFlowsWorkspace({ tab: "profile" });
  }
}

function pickUiSuite(id){
  _uiExplorerTab = "suite";
  const mode = document.getElementById("run-ui-mode");
  if(mode) mode.value = "suite";
  onUiModeChange();
  const sel = document.getElementById("run-ui-suite");
  if(sel) sel.value = id;
  updateUiFlowHint();
  if(_mainView === "flows" && document.getElementById("flow-detail-pane") && _uiExplorerTab === "suite"){
    refreshUiFlowSelection();
  } else {
    showUiFlowsWorkspace({ tab: "suite" });
  }
}

function refreshUiFlowSelection(){
  const mode = document.getElementById("run-ui-mode")?.value || "profile";
  if(_uiExplorerTab === "run_profiles"){
    const pane = document.getElementById("flow-detail-pane");
    if(pane) pane.innerHTML = renderRunProfilesPane();
    return;
  }
  const selectedFlow = _selectedFlowId || document.getElementById("run-ui-profile")?.value || "";
  const selectedSuite = document.getElementById("run-ui-suite")?.value || "";
  const explorer = document.querySelector(".flow-explorer");
  if(explorer){
    explorer.querySelectorAll(".flow-card").forEach(btn => {
      const fid = btn.getAttribute("data-flow-id");
      const sid = btn.getAttribute("data-suite-id");
      let active = false;
      if(mode === "suite" && sid) active = sid === selectedSuite;
      else if(mode !== "suite" && fid) active = fid === selectedFlow;
      btn.classList.toggle("active", active);
    });
  }
  const pane = document.getElementById("flow-detail-pane");
  if(!pane) return;
  if(mode === "suite"){
    pane.innerHTML = renderSuiteDetailHtml(findUiSuite(selectedSuite));
  } else {
    pane.innerHTML = renderFlowDetailHtml(findUiFlow(selectedFlow));
  }
}

async function toggleUiFlowPicker(force){
  // Prefer main workspace over sticky banner; Browse / Close flows toggles explorer
  const alreadyOpen = _mainView === "flows" && !!document.querySelector(".flow-workspace");
  const show = force === true ? true : (force === false ? false : !alreadyOpen);
  if(show){
    await ensureUiProfilesLoaded(true);
    const tt = document.getElementById("run-test-type");
    if(tt && tt.value === "k6"){
      tt.value = "playwright";
      await onTestTypeChange();
      return;
    }
    showUiFlowsWorkspace();
  } else {
    const el = document.getElementById("ui-flow-picker");
    if(el) el.style.display = "none";
    await leaveUiFlowsWorkspace();
  }
}

async function onTestTypeChange(){
  const tt = currentTestType();
  const ui = tt === "playwright" || tt === "mixed";
  const bar = document.getElementById("ui-run-bar");
  const fmtEl = document.getElementById("run-report-formats");
  const apiBtn = document.getElementById("btn-api-picker");
  const loadInputs = document.querySelector(".load-inputs");
  const preset = document.getElementById("run-preset");
  const runProfile = document.getElementById("run-profile");
  const openapi = document.getElementById("run-openapi-version");
  if(bar) bar.style.display = ui ? "" : "none";
  if(fmtEl) fmtEl.style.display = ui ? "" : "none";
  const picker = document.getElementById("ui-flow-picker");
  if(picker) picker.style.display = "none";
  if(ui){
    await ensureUiProfilesLoaded();
    onUiModeChange();
  }
  if(tt === "playwright"){
    if(apiBtn) apiBtn.style.display = "none";
    if(loadInputs) loadInputs.style.display = "none";
    if(preset) preset.style.display = "none";
    if(runProfile) runProfile.style.display = "none";
    if(openapi) openapi.style.display = "none";
    // Playwright: show flow catalog in main — not a previous run result
    showUiFlowsWorkspace();
  } else {
    if(apiBtn) apiBtn.style.display = "";
    if(loadInputs) loadInputs.style.display = "";
    if(preset) preset.style.display = "";
    if(runProfile) runProfile.style.display = "";
    if(openapi) openapi.style.display = "";
    if(_mainView === "flows") setMainView("auto");
  }
  // Rebuild profile dropdowns for this test type (UI / API / mixed)
  if(typeof refreshConfigSelect === "function"){
    try { await refreshConfigSelect(); } catch(_){}
  }
}

async function loadServiceApisForConfig(){
  const cfgId = document.getElementById("run-config")?.value;
  let service = null;
  let environment = null;
  if(cfgId){
    const c = configs.find(x=>x.id===cfgId) || (await fetchJson("/api/configs/"+cfgId));
    service = c.service;
    environment = c.environment;
  }
  const envEl = document.getElementById("cfg-env");
  if(envEl && envEl.value) environment = envEl.value;
  const svcEl = document.getElementById("cfg-service");
  if(svcEl && svcEl.value) service = svcEl.value;
  // Header API-version select wins for the next run / API picker
  const verSel = document.getElementById("run-openapi-version");
  const parsed = parseVersionOptionValue(verSel && verSel.value);
  if(parsed.environment) environment = parsed.environment;
  else if(selectedRunOpenApiEnv) environment = selectedRunOpenApiEnv;
  if(!service && configs[0]) service = configs[0].service;
  if(!service) service = "am-analysis";
  if(!environment) environment = "dev";
  const cacheKey = service + "|" + environment;
  if(!serviceApisCache[cacheKey]){
    const data = await fetchJson("/api/catalog/"+encodeURIComponent(service)+"/apis?environment="+encodeURIComponent(environment));
    serviceApisCache[cacheKey] = data;
  }
  const data = serviceApisCache[cacheKey];
  return {
    service,
    environment,
    apis: data.apis || [],
    target_url: data.target_url,
    runtime: data.runtime,
    source: data.source,
    openapi_version: data.openapi_version || selectedRunOpenApiVersion
  };
}

function renderApiPicker(service, apis, meta){
  const el = document.getElementById("api-picker");
  if(!el) return;
  meta = meta || {};
  const allIds = apis.map(a=>String(a.id)).filter(Boolean);
  if(selectedApiIds == null) selectedApiIds = allIds.slice();
  const checked = new Set(selectedApiIds);
  const n = checked.size;
  const ver = meta.openapi_version || selectedRunOpenApiVersion || "—";
  const env = meta.environment || selectedRunOpenApiEnv || "—";
  el.innerHTML =
    '<div class="picker-h">'+
      '<strong>APIs for next run</strong> <span class="sub">'+esc(service)+' · env '+esc(env)+' · API '+esc(ver)+' · '+esc(n)+' / '+esc(allIds.length)+' selected</span>'+
      '<button type="button" class="secondary" onclick="apiPickerSelectAll()">Select all</button>'+
      '<button type="button" class="secondary" onclick="apiPickerClear()">Clear</button>'+
      '<button type="button" class="secondary" onclick="toggleApiPicker(false)">Close</button>'+
    '</div>'+
    '<div class="picker-list">'+
      apis.map(a=>{
        const id = String(a.id||"");
        const on = checked.has(id);
        return '<label><input type="checkbox" data-api-pick="'+esc(id)+'"'+(on?" checked":"")+' onchange="onApiPickChange()"/>'+
          '<span><span class="pm-method '+esc((a.method||"GET").toUpperCase())+'">'+esc((a.method||"GET").toUpperCase())+'</span> '+
          esc(a.name||a.path||id)+'<span class="sub">'+esc(a.path||id)+'</span></span></label>';
      }).join("")+
    '</div>';
}

function renderApiPickerError(err){
  const el = document.getElementById("api-picker");
  if(!el) return;
  const msg = (err && err.message) ? String(err.message) : String(err || "unavailable");
  el.innerHTML =
    '<div class="picker-h">'+
      '<strong>APIs</strong> <span class="bad">unavailable</span>'+
      '<button type="button" class="secondary" onclick="toggleApiPicker(true)">Retry</button>'+
      '<button type="button" class="secondary" onclick="toggleApiPicker(false)">Close</button>'+
    '</div>'+
    '<p class="sub" style="margin:.35rem 0 0">Catalog failed — rest of the portal stays usable. <span class="bad">'+esc(msg)+'</span></p>';
  el.style.display = "block";
  const btn = document.getElementById("btn-api-picker");
  if(btn) btn.textContent = "APIs (error)";
}

function onApiPickChange(){
  const boxes = document.querySelectorAll("#api-picker [data-api-pick]");
  if(boxes.length){
    selectedApiIds = Array.from(boxes).filter(b=>b.checked).map(b=>b.getAttribute("data-api-pick"));
  }
  const btn = document.getElementById("btn-api-picker");
  if(btn){
    if(selectedApiIds == null) btn.textContent = "APIs (all)";
    else btn.textContent = "APIs ("+selectedApiIds.length+")";
  }
}

async function apiPickerSelectAll(){
  try {
    const meta = await loadServiceApisForConfig();
    selectedApiIds = meta.apis.map(a=>String(a.id)).filter(Boolean);
    renderApiPicker(meta.service, meta.apis, meta);
    onApiPickChange();
  } catch(e){
    renderApiPickerError(e);
  }
}

async function apiPickerClear(){
  try {
    selectedApiIds = [];
    const meta = await loadServiceApisForConfig();
    renderApiPicker(meta.service, meta.apis, meta);
    onApiPickChange();
  } catch(e){
    renderApiPickerError(e);
  }
}

async function toggleApiPicker(force){
  const el = document.getElementById("api-picker");
  if(!el) return;
  const open = force === false ? false : (force === true ? true : el.style.display === "none");
  if(!open){ el.style.display = "none"; return; }
  el.style.display = "block";
  el.innerHTML = '<div class="picker-h"><strong>APIs</strong> <span class="sub">Loading…</span></div>';
  try {
    const meta = await loadServiceApisForConfig();
    renderApiPicker(meta.service, meta.apis, meta);
    onApiPickChange();
  } catch(e){
    renderApiPickerError(e);
  }
}

function syncPayloadEditor(){
  const ed = document.getElementById("payload-editor");
  if(!ed) return;
  ed.value = JSON.stringify(editPayloads.bench_run||{vus:1,duration:"1s",iterations:1}, null, 2);
}

function syncPayloadEdit(){
  const ed = document.getElementById("payload-editor");
  if(!ed) return;
  try { editPayloads.bench_run = JSON.parse(ed.value); } catch(e){}
}

async function rerunRun(runId){
  const r = await fetchJson("/api/runs/"+runId);
  const preset = document.getElementById("run-preset")?.value || "";
  if(r.config_id){ await executeConfig(r.config_id, preset); return; }
  await runWithEdited(runId);
}

async function saveFromRun(runId){
  const name = prompt("Config name:", "from-run-"+runId.slice(0,8));
  if(!name) return;
  await fetch(api("/api/runs/"+runId+"/save-config?name="+encodeURIComponent(name)), {method:"POST"});
  await refreshConfigs();
  setMode("configs");
}

async function executeSelected(){
  const id = document.getElementById("run-config").value;
  const preset = document.getElementById("run-preset").value;
  if(!id) return alert("Pick a config");
  await executeConfig(id, preset);
}

function readLoadOverrides(){
  const out = {};
  const vus = parseInt(document.getElementById("run-vus")?.value, 10);
  const calls = parseInt(document.getElementById("run-calls")?.value, 10);
  if(Number.isFinite(vus) && vus > 0) out.vus = vus;
  if(Number.isFinite(calls) && calls > 0) out.iterations = calls;
  return out;
}

function profileBenchDefaults(c){
  const bench = (c && c.payloads && c.payloads.bench_run) || {};
  return {
    vus: bench.vus != null ? Number(bench.vus) : null,
    iterations: bench.iterations != null ? Number(bench.iterations) : null,
    duration: bench.duration || null,
    run_profile: (c && c.run_profile) || "load"
  };
}

function readOverrideDiffs(configId){
  const c = (typeof configs !== "undefined" ? configs : []).find(x=>x.id===configId) || {};
  const base = profileBenchDefaults(c);
  const cur = readLoadOverrides();
  const prof = document.getElementById("run-profile")?.value || "load";
  const preset = document.getElementById("run-preset")?.value || "";
  const out = {};
  if(preset) out.preset = preset;
  if(cur.vus != null && base.vus != null && Number(cur.vus) !== Number(base.vus)) out.vus = cur.vus;
  else if(cur.vus != null && base.vus == null) out.vus = cur.vus;
  if(cur.iterations != null && base.iterations != null && Number(cur.iterations) !== Number(base.iterations)) out.iterations = cur.iterations;
  else if(cur.iterations != null && base.iterations == null && cur.iterations) out.iterations = cur.iterations;
  if(prof && prof !== base.run_profile) out.profile = prof;
  else if(prof) out.profile = prof; // still send profile for apply_run_profile consistency when multi
  return out;
}

function refreshOverrideChip(){
  const chip = document.getElementById("override-chip");
  if(!chip) return;
  const id = document.getElementById("run-config")?.value;
  const c = (typeof configs !== "undefined" ? configs : []).find(x=>x.id===id);
  if(!c){ chip.style.display = "none"; return; }
  const base = profileBenchDefaults(c);
  const cur = readLoadOverrides();
  const prof = document.getElementById("run-profile")?.value || "load";
  const preset = document.getElementById("run-preset")?.value || "";
  let overriding = !!preset;
  if(cur.vus != null && base.vus != null && Number(cur.vus) !== Number(base.vus)) overriding = true;
  if(cur.iterations != null && base.iterations != null && Number(cur.iterations) !== Number(base.iterations)) overriding = true;
  if(prof && base.run_profile && prof !== base.run_profile) overriding = true;
  chip.style.display = overriding ? "inline-block" : "none";
}

function onPresetChange(){
  const c = (typeof activeProfile === "function") ? activeProfile() : null;
  if(c && !audienceAllowsMultiLoad(c.audience)){
    applyAudienceLoadLimits(c.audience);
    refreshOverrideChip();
    return;
  }
  const p = document.getElementById("run-preset").value;
  const vusEl = document.getElementById("run-vus");
  const callsEl = document.getElementById("run-calls");
  const profEl = document.getElementById("run-profile");
  if(!vusEl || !callsEl) return;
  if(p === "20u-50"){ vusEl.value = 20; callsEl.value = 50; if(profEl) profEl.value = "load"; }
  else if(p === "smoke"){ vusEl.value = 3; callsEl.value = ""; }
  else if(p === "load"){ vusEl.value = 10; callsEl.value = ""; if(profEl) profEl.value = "load"; }
  else if(p === "stress"){ vusEl.value = 25; callsEl.value = ""; if(profEl) profEl.value = "load"; }
  refreshOverrideChip();
}

function toggleSidebar(){
  document.body.classList.toggle("sidebar-collapsed");
  const collapsed = document.body.classList.contains("sidebar-collapsed");
  localStorage.setItem("spt_sidebar_collapsed", collapsed ? "1" : "0");
  const btn = document.getElementById("btn-toggle-sidebar");
  if(btn) btn.textContent = collapsed ? "Show list" : "Hide list";
  syncRailActive();
}

function onProfileChange(){
  const prof = document.getElementById("run-profile")?.value;
  if(prof !== "debug"){ refreshOverrideChip(); return; }
  const vus = parseInt(document.getElementById("run-vus")?.value, 10);
  const calls = parseInt(document.getElementById("run-calls")?.value, 10);
  if((Number.isFinite(vus) && vus > 1) || (Number.isFinite(calls) && calls > 1)){
    const vusEl = document.getElementById("run-vus");
    const callsEl = document.getElementById("run-calls");
    const presetEl = document.getElementById("run-preset");
    if(vusEl) vusEl.value = 1;
    if(callsEl) callsEl.value = 1;
    if(presetEl) presetEl.value = "";
  }
  refreshOverrideChip();
}

async function executeConfig(configId, preset){
  if(typeof setMainView === "function") setMainView("run");
  document.getElementById("main").innerHTML = '<div class="empty">Starting run…</div>';
  const cfgMeta = configs.find(x=>x.id===configId) || {};
  const allow = audienceAllowsMultiLoad(cfgMeta.audience);
  let overrides = readOverrideDiffs(configId);
  if(preset) overrides.preset = preset;
  if(!allow){
    overrides = { vus: 1, iterations: 1, profile: "load" };
    const presetEl = document.getElementById("run-preset");
    if(presetEl) presetEl.value = "";
    preset = "";
  } else if(overrides.preset === "20u-50" || (overrides.vus && overrides.vus > 1) || (overrides.iterations && overrides.iterations > 1)){
    overrides.profile = "load";
  }
  // If no load diffs, still send profile from header for apply_run_profile
  if(!overrides.profile){
    overrides.profile = document.getElementById("run-profile")?.value || "load";
  }
  const body = {config_id: configId, triggered_by: "manual", wait: false, ...overrides};
  if(!allow){
    body.profile = "load";
  }
  applyUiTestFieldsToBody(body);
  if(currentTestType() !== "playwright"){
    applyApiIdsToBody(body);
    applyOpenApiVersionToBody(body);
    if(body.api_ids && !body.api_ids.length){
      alert("Select at least one API (APIs button), or Select all");
      return;
    }
  } else {
    if(!body.ui_profile && !body.ui_suite){
      alert("Pick a UI profile or suite for Playwright");
      return;
    }
    if(!body.report_formats || !body.report_formats.length){
      alert("Pick at least one attachment format (HTML / PDF / JSON)");
      return;
    }
  }
  if(typeof collectPayloadSetVersionForRun === "function"){
    const setVer = collectPayloadSetVersionForRun();
    if(setVer != null) body.payload_set_version = setVer;
  }
  if(body.payload_set_version == null){
    const c = cfgMeta;
    const fromCfg = c && (c.payload_set_version != null
      ? c.payload_set_version
      : (c.payloads && c.payloads.payload_set_version));
    if(fromCfg != null) body.payload_set_version = Number(fromCfg);
  }
  if(typeof collectPayloadRefsForRun === "function"){
    const refs = collectPayloadRefsForRun();
    if(refs && refs.length) body.payload_refs = refs;
  }
  const res = await fetchJson("/api/runs/execute", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  updateStopButton(true);
  await refreshRuns({resetPage: true});
  setMode("runs");
  await selectRun(res.id);
}

async function runDebug(runId){
  const r = await fetchJson("/api/runs/"+runId);
  if(typeof setMainView === "function") setMainView("run");
  document.getElementById("main").innerHTML = '<div class="empty">Starting debug run…</div>';
  const body = {
    config: {
      name: r.config_name,
      service: r.service,
      environment: r.environment,
      openapi_version: r.openapi_version || null,
      test_type: r.test_type,
      target_url: r.target_url,
      run_profile: "debug",
      ui_profile: r.ui_profile || ((r.payloads_used||{}).run_params||{}).ui_profile || null,
      ui_suite: r.ui_suite || ((r.payloads_used||{}).run_params||{}).ui_suite || null,
      payloads: r.payloads_used || {},
      scripts: (r.config_snapshot||{}).scripts || {}
    },
    profile: "debug",
    test_type: r.test_type || "k6",
    ui_profile: r.ui_profile || ((r.payloads_used||{}).run_params||{}).ui_profile || null,
    ui_suite: r.ui_suite || ((r.payloads_used||{}).run_params||{}).ui_suite || null,
    wait: false,
    triggered_by: "manual"
  };
  if(String(r.test_type||"k6") !== "playwright"){
    applyApiIdsToBody(body);
    applyOpenApiVersionToBody(body);
  }
  const res = await fetchJson("/api/runs/execute", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  updateStopButton(true);
  await refreshRuns({resetPage: true});
  await selectRun(res.id);
}

async function runWithEdited(runId){
  syncPayloadEdit();
  const r = await fetchJson("/api/runs/"+runId);
  document.getElementById("main").innerHTML = '<div class="empty">Starting run…</div>';
  const body = {
    config: {
      name: r.config_name,
      service: r.service,
      environment: r.environment,
      openapi_version: r.openapi_version || null,
      test_type: r.test_type,
      target_url: r.target_url,
      ui_profile: r.ui_profile || ((r.payloads_used||{}).run_params||{}).ui_profile || null,
      ui_suite: r.ui_suite || ((r.payloads_used||{}).run_params||{}).ui_suite || null,
      payloads: editPayloads,
      scripts: (r.config_snapshot||{}).scripts || {}
    },
    test_type: r.test_type || "k6",
    ui_profile: r.ui_profile || ((r.payloads_used||{}).run_params||{}).ui_profile || null,
    ui_suite: r.ui_suite || ((r.payloads_used||{}).run_params||{}).ui_suite || null,
    wait: false,
    triggered_by: "manual"
  };
  if(String(r.test_type||"k6") !== "playwright"){
    applyApiIdsToBody(body);
    applyOpenApiVersionToBody(body);
  }
  const res = await fetchJson("/api/runs/execute", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  updateStopButton(true);
  await refreshRuns({resetPage: true});
  await selectRun(res.id);
}

function applyProfileToHeader(c){
  if(!c) return;
  const bench = (c.payloads && c.payloads.bench_run) || {};
  const allow = audienceAllowsMultiLoad(c.audience);
  const vusEl = document.getElementById("run-vus");
  const callsEl = document.getElementById("run-calls");
  const profEl = document.getElementById("run-profile");
  const presetEl = document.getElementById("run-preset");
  const typeEl = document.getElementById("run-test-type");
  if(typeEl && c.test_type){
    typeEl.value = c.test_type;
    if(typeof onTestTypeChange === "function") onTestTypeChange();
  }
  if(c.ui_profile){
    const uiProf = document.getElementById("run-ui-profile");
    if(uiProf){
      // ensure option exists then select
      if(![].some.call(uiProf.options, o=>o.value===c.ui_profile)){
        const opt = document.createElement("option");
        opt.value = c.ui_profile;
        opt.textContent = c.ui_profile;
        uiProf.appendChild(opt);
      }
      uiProf.value = c.ui_profile;
    }
  }
  if(!allow){
    if(vusEl) vusEl.value = 1;
    if(callsEl) callsEl.value = 1;
    if(presetEl) presetEl.value = "";
    if(profEl) profEl.value = "load";
  } else {
    if(vusEl && bench.vus != null) vusEl.value = bench.vus;
    if(callsEl){
      if(bench.iterations != null) callsEl.value = bench.iterations;
      else if(bench.duration && !bench.iterations) callsEl.value = "";
    }
    if(profEl && c.run_profile) profEl.value = c.run_profile;
    if(presetEl) presetEl.value = "";
  }
  applyAudienceLoadLimits(c.audience || "developer");
  if(typeof syncProfileControls === "function") syncProfileControls(c.id);
  else {
    const sel = document.getElementById("run-config");
    if(sel && c.id && [].some.call(sel.options, o=>o.value===c.id)) sel.value = c.id;
  }
  if(typeof refreshOverrideChip === "function") refreshOverrideChip();
}

function cfgInputStyle(){
  return 'width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:.35rem';
}

function durationPresetValue(duration){
  const d = String(duration||"").trim().toLowerCase();
  if(d === "15m" || d === "15min") return "15m";
  if(d === "30m" || d === "30min") return "30m";
  if(d === "1h" || d === "60m" || d === "1hr") return "1h";
  if(d) return "custom";
  return "30m";
}

function durationPresetHtml(duration, hasIterations){
  const preset = hasIterations ? "" : durationPresetValue(duration);
  const customVal = (!hasIterations && preset === "custom") ? esc(duration||"") : (preset && preset !== "custom" ? preset : "");
  const customShow = preset === "custom" ? "block" : "none";
  const tags = [
    {v:"", label:"Calls"},
    {v:"15m", label:"15m"},
    {v:"30m", label:"30m"},
    {v:"1h", label:"1h"},
    {v:"custom", label:"Custom"}
  ];
  return '<div class="dur-tags" id="cfg-duration-tags" role="group" aria-label="Duration">'+
    tags.map(t=>'<button type="button" class="dur-tag'+(preset===t.v?" active":"")+'" data-dur="'+t.v+'" onclick="pickDurationTag(\''+t.v+'\')">'+t.label+'</button>').join("")+
  '</div>'+
  '<input type="hidden" id="cfg-duration-preset" value="'+esc(preset)+'"/>'+
  '<input id="cfg-duration" value="'+customVal+'" style="'+cfgInputStyle()+';display:'+customShow+'" placeholder="e.g. 45m or 90s" oninput="document.getElementById(\'cfg-duration-preset\').value=\'custom\'"/>'+
  '<p class="sub">One click. Time modes clear Calls; Calls mode clears duration.</p>';
}

function pickDurationTag(preset){
  const hidden = document.getElementById("cfg-duration-preset");
  const custom = document.getElementById("cfg-duration");
  const calls = document.getElementById("cfg-calls");
  if(hidden) hidden.value = preset == null ? "" : String(preset);
  document.querySelectorAll("#cfg-duration-tags .dur-tag").forEach(btn=>{
    btn.classList.toggle("active", btn.getAttribute("data-dur") === String(preset));
  });
  if(preset && preset !== "custom"){
    if(calls) calls.value = "";
    if(custom){ custom.style.display = "none"; custom.value = preset; }
  } else if(preset === "custom"){
    if(calls) calls.value = "";
    if(custom){
      custom.style.display = "block";
      if(!custom.value || ["15m","30m","1h",""].indexOf(custom.value)>=0) custom.value = "45m";
      custom.focus();
    }
  } else {
    if(custom){ custom.style.display = "none"; custom.value = ""; }
  }
}

function onDurationPresetChange(){
  const preset = document.getElementById("cfg-duration-preset")?.value || "";
  pickDurationTag(preset);
}

function audienceAllowsMultiLoad(audience){
  return String(audience || "developer").toLowerCase() === "developer";
}

function applyAudienceLoadLimits(audience){
  const allow = audienceAllowsMultiLoad(audience);
  const vusEl = document.getElementById("run-vus");
  const callsEl = document.getElementById("run-calls");
  const presetEl = document.getElementById("run-preset");
  const profEl = document.getElementById("run-profile");
  if(!allow){
    if(vusEl){ vusEl.value = 1; vusEl.max = 1; vusEl.title = "Non-developer profiles: 1 VU only (single call with traces)"; }
    if(callsEl){ callsEl.value = 1; callsEl.max = 1; callsEl.title = "Non-developer profiles: 1 call with traces"; }
    if(presetEl){ presetEl.value = ""; presetEl.disabled = true; }
    if(profEl){ profEl.value = "load"; }
  } else {
    if(vusEl){ vusEl.max = 50; vusEl.title = ""; }
    if(callsEl){ callsEl.max = 10000; callsEl.title = ""; }
    if(presetEl) presetEl.disabled = false;
  }
  const lock = document.getElementById("audience-load-lock");
  if(lock){
    lock.style.display = allow ? "none" : "block";
    lock.textContent = allow
      ? ""
      : "Audience “"+(audience||"other")+"” — single call with traces only. Multi-VU / multi-load is limited to developer profiles.";
  }
}

function targetDomainBits(url){
  try {
    const u = new URL(url);
    return { host: u.host, path: u.pathname === "/" ? "" : u.pathname };
  } catch(_){
    return { host: "", path: "" };
  }
}

function setTargetHint(url, meta){
  const hint = document.getElementById("cfg-target-hint");
  if(!hint) return;
  const tt = document.getElementById("cfg-test-type")?.value || "k6";
  const bits = targetDomainBits(url||"");
  const parts = [];
  if(bits.host) parts.push("domain "+bits.host);
  if(bits.path) parts.push("path "+bits.path);
  if(meta && meta.runtime) parts.push("runtime="+meta.runtime);
  if(meta && meta.source) parts.push(meta.source);
  if(meta && meta.openapi_version) parts.push("API "+meta.openapi_version);
  let base = parts.length
    ? ("Auto from service+env · " + parts.join(" · "))
    : "Auto from service targets[env]; edit only to override.";
  if(tt === "playwright" || tt === "mixed"){
    base += " · For UI this must be the SPA origin (e.g. https://am-dev.asrax.in), not /analysis. Portfolio pages come from the UI profile, not this path.";
  } else if(bits.path === "/analysis"){
    base += " · Analysis API base — correct for k6 API-only runs.";
  }
  hint.textContent = base;
}

function setCfgTargetHint(tt, service){
  const hint = document.getElementById("cfg-target-hint");
  if(!hint) return;
  const url = document.getElementById("cfg-target")?.value || "";
  setTargetHint(url, { source: service || "" });
}

function onCfgTestTypeChange(){
  const tt = document.getElementById("cfg-test-type")?.value || "k6";
  const uiSec = document.getElementById("cfg-ui-section");
  const loadSec = document.getElementById("cfg-load-section");
  if(uiSec) uiSec.style.display = (tt === "playwright" || tt === "mixed") ? "" : "none";
  if(loadSec) loadSec.style.display = tt === "playwright" ? "none" : "";
  setCfgTargetHint(tt, document.getElementById("cfg-service")?.value);
  if(tt === "playwright" || tt === "mixed") fillCfgUiProfiles();
  // Prefer modern-ui SPA target when switching into UI modes
  const svc = document.getElementById("cfg-service");
  if(svc && (tt === "playwright" || tt === "mixed") && svc.value === "am-analysis"){
    svc.value = "am-modern-ui";
    onConfigServiceEnvChange();
  } else if(tt === "playwright" || tt === "mixed"){
    const cur = document.getElementById("cfg-target")?.value || "";
    if(/\/analysis\/?$/i.test(cur) || !cur){
      autoFillTargetUrl({ force: true, always: true });
    }
  }
}

async function fillCfgUiProfiles(selected){
  const sel = document.getElementById("cfg-ui-profile");
  if(!sel) return;
  if(!_uiFlowCatalog){
    try { await ensureUiProfilesLoaded(true); } catch(_){}
  }
  const flows = (_uiFlowCatalog && _uiFlowCatalog.flows) || FALLBACK_UI_PROFILES.map(id=>({id,label:id,group:"Other"}));
  const byGroup = {};
  flows.forEach(f=>{
    const g = f.group || "Other";
    (byGroup[g] = byGroup[g] || []).push(f);
  });
  const cur = selected || sel.value || ((_uiFlowCatalog && _uiFlowCatalog.default_flow) || "AUTH_FLOW_MAIN");
  const opts = [];
  Object.keys(byGroup).sort().forEach(g=>{
    opts.push('<optgroup label="'+esc(g)+'">');
    byGroup[g].forEach(f=>{
      opts.push('<option value="'+esc(f.id)+'" title="'+esc(f.summary||"")+'">'+esc(f.label)+'</option>');
    });
    opts.push('</optgroup>');
  });
  sel.innerHTML = opts.join("");
  if([].some.call(sel.options, o=>o.value===cur)) sel.value = cur;
  else if([].some.call(sel.options, o=>o.value==="AUTH_FLOW_MAIN")) sel.value = "AUTH_FLOW_MAIN";
  else if(flows[0]) sel.value = flows[0].id;
}

async function resolveTargetForServiceEnv(service, environment){
  if(!service) return null;
  // Fast path: registration targets already in catalog (if loaded)
  try {
    const svc = (catalog.services||[]).find(s=>s.id===service);
    const env = environment || "dev";
    const targets = (svc && svc.targets) || {};
    const flat = svc
      ? (svc["public_target_url_"+env] || svc["default_target_url_"+env] || svc.public_target_url_dev || svc.default_target_url_dev)
      : null;
    const localPick = targets["public_"+env] || targets.public || targets[env] || flat;
    if(localPick && String(localPick).startsWith("http") && String(localPick).indexOf(".svc.cluster.local") < 0){
      return { target_url: String(localPick).replace(/\/$/,""), source: "catalog.targets" };
    }
  } catch(_){}
  try {
    const data = await fetchJson(
      "/api/catalog/"+encodeURIComponent(service)+"/target?environment="+encodeURIComponent(environment||"dev")
    );
    if(data && data.target_url) return data;
  } catch(_){}
  try {
    const data = await fetchJson(
      "/api/catalog/"+encodeURIComponent(service)+"/apis?environment="+encodeURIComponent(environment||"dev")
    );
    if(data && data.target_url) return data;
  } catch(_){}
  return null;
}

async function autoFillTargetUrl(opts){
  opts = opts || {};
  const service = document.getElementById("cfg-service")?.value;
  const environment = document.getElementById("cfg-env")?.value || "dev";
  const target = document.getElementById("cfg-target");
  const tt = document.getElementById("cfg-test-type")?.value || "k6";
  if(!service || !target) return;
  const data = await resolveTargetForServiceEnv(service, environment);
  if(!data || !data.target_url){
    setTargetHint(target.value, { source: "no target for "+service+"/"+environment });
    return;
  }
  const next = String(data.target_url).replace(/\/$/,"");
  const cur = (target.value||"").trim();
  const staleCluster = cur.indexOf(".svc.cluster.local") >= 0;
  const wrongAnalysisForUi = (service === "am-modern-ui" || tt === "playwright" || tt === "mixed")
    && /\/analysis\/?$/i.test(cur);
  const empty = !cur;
  if(opts.force || empty || staleCluster || wrongAnalysisForUi || opts.always){
    target.value = next;
  }
  setTargetHint(target.value, data);
}

async function selectConfig(id, opts){
  opts = opts || {};
  selectedConfigId=id; selectedRunId=null; renderList();
  // Keep profile filter aligned when opening a profile from the list
  if(typeof syncProfileControls === "function") syncProfileControls(id);
  let c;
  try {
    c = await fetchJson("/api/configs/"+id);
  } catch(e){
    document.getElementById("main").innerHTML =
      '<div class="empty"><span class="bad">Could not load profile</span><p class="sub">'+esc(e.message)+'</p>'+
      '<button type="button" class="secondary" onclick="selectConfig(\''+esc(id)+'\')">Retry</button></div>';
    return;
  }
  editPayloads = JSON.parse(JSON.stringify(c.payloads||{}));
  applyProfileToHeader(c);
  const bench = (c.payloads||{}).bench_run || {vus:1, duration:"30m"};
  const auth = (c.payloads||{}).auth_env || {};
  const audience = c.audience || "developer";
  const setVer = c.payload_set_version != null
    ? c.payload_set_version
    : ((c.payloads||{}).payload_set_version);
  const hasIters = bench.iterations != null && bench.iterations !== "";
  const tt = String(c.test_type || "k6").toLowerCase();
  const uiOn = tt === "playwright" || tt === "mixed";
  document.getElementById("main").innerHTML =
    '<h2>Profile: '+esc(c.name)+' <span class="pill">'+esc(testTypeLabel(tt))+'</span></h2>'+
    '<p class="sub">Test Agent run settings — type (API / UI / both), target, payloads, load. Header can override for one run.</p>'+
    '<div class="toolbar"><button onclick="saveConfig(\''+c.id+'\')">Save profile</button>'+
      '<button class="secondary" onclick="executeConfig(\''+c.id+'\')">Run with this profile</button></div>'+
    '<div class="section"><div class="section-h">Identity</div><div class="section-b">'+
      row("Name", '<input id="cfg-name" value="'+esc(c.name)+'" style="'+cfgInputStyle()+'"/>')+
      row("Description", '<input id="cfg-desc" value="'+esc(c.description||"")+'" style="'+cfgInputStyle()+'"/>')+
      row("Audience", selAudience(audience))+
      row("Test type", '<select id="cfg-test-type" style="'+cfgInputStyle()+'" onchange="onCfgTestTypeChange()">'+
        '<option value="k6"'+(tt==="k6"?" selected":"")+'>API only (k6)</option>'+
        '<option value="playwright"'+(tt==="playwright"?" selected":"")+'>UI only (Playwright)</option>'+
        '<option value="mixed"'+(tt==="mixed"?" selected":"")+'>API + UI (mixed)</option></select>'+
        '<p class="sub">Profiles must declare this. Mixed runs k6 APIs then Playwright UI.</p>')+
    '</div></div>'+
    '<div class="section"><div class="section-h">Target</div><div class="section-b">'+
      row("Service", selService(c.service))+
      row("Environment", selEnv(c.environment))+
      row("API version", '<select id="cfg-openapi-version" style="'+cfgInputStyle()+'"><option value="">Loading…</option></select><p class="sub">OpenAPI contract (info.version) used to discover APIs (API / mixed).</p>')+
      row("Target URL", '<input id="cfg-target" value="'+esc(c.target_url||"")+'" style="'+cfgInputStyle()+'" placeholder="Auto-filled from service + env"/>'+
        '<p class="sub" id="cfg-target-hint"></p>')+
    '</div></div>'+
    '<div class="section" id="cfg-ui-section" style="display:'+(uiOn?"":"none")+'"><div class="section-h">UI flow (Playwright)</div><div class="section-b">'+
      row("UI profile", '<select id="cfg-ui-profile" style="'+cfgInputStyle()+'"><option value="">Loading…</option></select>'+
        '<p class="sub">In-app route under the SPA. <code>AUTH_FLOW_MAIN</code> = dashboard (default). <code>PORTFOLIO_*</code> = portfolio pages — only pick those when you intend to test portfolio.</p>')+
      row("Login mode", '<select id="cfg-login-mode" style="'+cfgInputStyle()+'">'+
        '<option value="demo"'+(String(c.login_mode||"demo")==="demo"?" selected":"")+'>demo</option>'+
        '<option value="credentials"'+(String(c.login_mode||"")==="credentials"?" selected":"")+'>credentials</option></select>')+
    '</div></div>'+
    '<div class="section"><div class="section-h">Payloads</div><div class="section-b">'+
      row("Payload set", '<select id="cfg-payload-set" style="'+cfgInputStyle()+'"><option value="">Loading…</option></select><p class="sub">Same sets as OpenAPI → Set. Applied on run when header/OpenAPI does not override.</p>')+
    '</div></div>'+
    '<div class="section"><div class="section-h">Auth</div><div class="section-b">'+
      row("Default user", '<input id="cfg-username" value="'+esc(auth.username||"")+'" style="'+cfgInputStyle()+'" autocomplete="username"/><p class="sub">Test Agent resolves credentials; password is not stored here.</p>')+
    '</div></div>'+
    '<div class="section" id="cfg-load-section" style="display:'+(tt==="playwright"?"none":"")+'"><div class="section-h">Load defaults</div><div class="section-b">'+
      '<div class="audience-lock" id="cfg-audience-lock" style="display:'+(audienceAllowsMultiLoad(audience)?"none":"block")+'">'+
        (audienceAllowsMultiLoad(audience)?"":('Audience “'+esc(audience)+'” — single call with traces only. Multi-VU / multi-duration load is for developer profiles.'))+
      '</div>'+
      row("Run profile", '<select id="cfg-run-profile" style="'+cfgInputStyle()+'"'+(audienceAllowsMultiLoad(audience)?"":" disabled")+'>'+
        '<option value="debug"'+(c.run_profile==="debug"?" selected":"")+'>debug (1×1 forced)</option>'+
        '<option value="load"'+(c.run_profile!=="debug"?" selected":"")+'>load</option></select>')+
      row("VUs", '<input id="cfg-vus" type="number" min="1" max="'+(audienceAllowsMultiLoad(audience)?50:1)+'" value="'+(audienceAllowsMultiLoad(audience)?(bench.vus!=null?esc(String(bench.vus)):"1"):"1")+'" style="'+cfgInputStyle()+'"'+(audienceAllowsMultiLoad(audience)?"":" disabled")+'/>')+
      row("Calls (iterations)", '<input id="cfg-calls" type="number" min="1" max="'+(audienceAllowsMultiLoad(audience)?10000:1)+'" value="'+(audienceAllowsMultiLoad(audience)?(hasIters?esc(String(bench.iterations)):""):"1")+'" style="'+cfgInputStyle()+'" placeholder="e.g. 50" oninput="onCallsInputChange()"'+(audienceAllowsMultiLoad(audience)?"":" disabled")+'/><p class="sub">Total shared calls. Clears Duration when set.</p>')+
      row("Duration", audienceAllowsMultiLoad(audience)
        ? durationPresetHtml(bench.duration||"30m", hasIters)
        : '<p class="sub">Locked to 1 call (traces on). Switch audience to <strong>developer</strong> for multi-load.</p><input type="hidden" id="cfg-duration-preset" value=""/><input type="hidden" id="cfg-duration" value=""/>')+
    '</div></div>';
  setCfgTargetHint(tt, c.service);
  await fillCfgUiProfiles(c.ui_profile);
  const audSel = document.getElementById("cfg-audience");
  if(audSel) audSel.addEventListener("change", ()=>{
    // Re-render form limits when audience changes (save still required)
    const note = document.getElementById("cfg-audience-lock");
    const a = audSel.value;
    if(note){
      note.style.display = audienceAllowsMultiLoad(a) ? "none" : "block";
      note.textContent = audienceAllowsMultiLoad(a) ? "" :
        'Audience “'+a+'” — single call with traces only. Multi-VU / multi-duration load is for developer profiles.';
    }
    applyAudienceLoadLimits(a);
  });
  const svc = document.getElementById("cfg-service");
  const env = document.getElementById("cfg-env");
  if(svc) svc.addEventListener("change", onConfigServiceEnvChange);
  if(env) env.addEventListener("change", onConfigServiceEnvChange);
  // Secondary catalog calls must not block the profile form
  try { await fillConfigOpenApiVersions(c.service, c.environment, c.openapi_version); }
  catch(e){
    const sel = document.getElementById("cfg-openapi-version");
    if(sel) sel.innerHTML = '<option value="">API versions unavailable</option>';
  }
  try { await fillConfigPayloadSets(c.service, setVer); } catch(_){}
  try {
    await autoFillTargetUrl({ force: !c.target_url || String(c.target_url).indexOf(".svc.cluster.local")>=0, always: false });
  } catch(_){}
  try { await refreshRunOpenApiVersionSelect(c.environment, c.openapi_version); } catch(_){}
  if(!opts.skipUrl) syncPortalUrl({ replace: !!opts.replaceUrl });
}

function onCallsInputChange(){
  const calls = parseInt(document.getElementById("cfg-calls")?.value, 10);
  if(Number.isFinite(calls) && calls > 0){
    pickDurationTag("");
  }
}

async function fillConfigPayloadSets(service, selectedVersion){
  const sel = document.getElementById("cfg-payload-set");
  if(!sel) return;
  if(!service){
    sel.innerHTML = '<option value="">— pick service —</option>';
    return;
  }
  try {
    const data = await fetchJson("/api/payload-sets/"+encodeURIComponent(service));
    const sets = data.sets || data.versions || [];
    const active = data.active_version;
    const opts = ['<option value="">active'+(active!=null?(" (v"+active+")"):"")+'</option>'];
    sets.forEach(s=>{
      const ver = s.version != null ? s.version : s;
      const label = (s.label || ("v"+ver)) + (Number(ver)===Number(active) ? " · active" : "");
      const n = s.api_count != null ? (" · "+s.api_count+" APIs") : "";
      const selected = selectedVersion != null && Number(selectedVersion)===Number(ver) ? " selected" : "";
      opts.push('<option value="'+esc(String(ver))+'"'+selected+'>'+esc(label+n)+'</option>');
    });
    sel.innerHTML = opts.join("");
  } catch(e){
    sel.innerHTML = '<option value="">No payload sets ('+esc(e.message)+')</option>';
  }
}

async function fillConfigOpenApiVersions(service, environment, selectedVersion){
  const sel = document.getElementById("cfg-openapi-version");
  if(!sel) return;
  const versions = await loadOpenApiVersions(service);
  const opts = ['<option value="">auto (from env OpenAPI)</option>'];
  versions.forEach(v=>{
    if(v.environment !== environment) return;
    const ver = v.version || "";
    const label = v.ok ? ((ver||"unknown")+" · "+(v.operation_count||0)+" ops") : "unreachable";
    const selected = (selectedVersion && String(selectedVersion)===String(ver)) ? " selected" : (!selectedVersion && v.ok ? " selected" : "");
    opts.push('<option value="'+esc(ver)+'"'+(v.ok?"":" disabled")+selected+'>'+esc(label)+'</option>');
  });
  versions.filter(v=>v.environment!==environment).forEach(v=>{
    opts.push('<option value="" disabled>'+esc((v.label||v.environment)+" (switch Environment)")+'</option>');
  });
  sel.innerHTML = opts.join("");
  sel.onchange = ()=>{
    selectedRunOpenApiVersion = sel.value || null;
    refreshRunOpenApiVersionSelect(environment, sel.value || null);
  };
}

async function onConfigServiceEnvChange(){
  const service = document.getElementById("cfg-service")?.value;
  const environment = document.getElementById("cfg-env")?.value || "dev";
  if(!service) return;
  delete openApiVersionCache[service];
  // Always refresh reachable target when service or env changes
  await autoFillTargetUrl({ force: true, always: true });
  try {
    const data = await fetchJson("/api/catalog/"+encodeURIComponent(service)+"/apis?environment="+encodeURIComponent(environment));
    serviceApisCache[service + "|" + environment] = data;
    if(data.target_url){
      const target = document.getElementById("cfg-target");
      if(target) target.value = String(data.target_url).replace(/\/$/,"");
      setTargetHint(target && target.value, data);
    }
    await fillConfigOpenApiVersions(service, environment, data.openapi_version || null);
    await fillConfigPayloadSets(service, document.getElementById("cfg-payload-set")?.value || null);
    await refreshRunOpenApiVersionSelect(environment, data.openapi_version || null);
  } catch(e){
    console.warn("target refresh failed", e);
  }
}

function row(l, html){ return '<div style="margin-bottom:.5rem"><label style="font-size:.72rem;color:var(--muted)">'+l+'</label><div>'+html+'</div></div>'; }
function selAudience(v){
  const opts = ["developer","agent","ci","shared"];
  return '<select id="cfg-audience" style="'+cfgInputStyle()+'">'+
    opts.map(a=>'<option value="'+a+'"'+(a===v?" selected":"")+'>'+a+'</option>').join("")+'</select>';
}
function selService(v){
  const services = (catalog.services||[]).slice();
  if(v && !services.some(s=>s.id===v)) services.unshift({id:v, label:v+" (saved)"});
  return '<select id="cfg-service" style="'+cfgInputStyle()+'">'+
    (services.length?"":'<option value="'+esc(v||"")+'">'+esc(v||"—")+'</option>')+
    services.map(s=>'<option value="'+esc(s.id)+'"'+(s.id===v?" selected":"")+'>'+esc(s.label||s.id)+'</option>').join("")+'</select>';
}
function selEnv(v){
  const envs = (catalog.environments||[]).slice();
  if(v && envs.indexOf(v) < 0) envs.unshift(v);
  return '<select id="cfg-env" style="'+cfgInputStyle()+'">'+
    (envs.length?"":'<option>'+esc(v||"dev")+'</option>')+
    envs.map(e=>'<option'+(e===v?" selected":"")+'>'+esc(e)+'</option>').join("")+'</select>';
}

async function saveConfig(id){
  const audience = document.getElementById("cfg-audience")?.value || "developer";
  const allow = audienceAllowsMultiLoad(audience);
  const vus = parseInt(document.getElementById("cfg-vus")?.value, 10);
  const calls = parseInt(document.getElementById("cfg-calls")?.value, 10);
  const preset = document.getElementById("cfg-duration-preset")?.value || "";
  const customDur = (document.getElementById("cfg-duration")?.value || "").trim();
  let duration = "";
  if(preset && preset !== "custom") duration = preset;
  else if(preset === "custom") duration = customDur;
  const bench = {};
  if(!allow){
    bench.vus = 1;
    bench.iterations = 1;
  } else {
    if(Number.isFinite(vus) && vus > 0) bench.vus = vus;
    if(Number.isFinite(calls) && calls > 0){
      bench.iterations = calls;
    } else if(duration){
      bench.duration = duration;
    } else {
      bench.duration = "30m";
    }
  }
  const setRaw = document.getElementById("cfg-payload-set")?.value;
  const payloadSetVersion = setRaw !== "" && setRaw != null ? Number(setRaw) : null;
  const username = (document.getElementById("cfg-username")?.value || "").trim();
  const body = {
    name: document.getElementById("cfg-name").value,
    description: document.getElementById("cfg-desc")?.value || "",
    service: document.getElementById("cfg-service").value,
    environment: document.getElementById("cfg-env").value,
    audience: audience,
    test_type: document.getElementById("cfg-test-type")?.value || "k6",
    openapi_version: document.getElementById("cfg-openapi-version")?.value || null,
    target_url: document.getElementById("cfg-target").value,
    run_profile: allow ? (document.getElementById("cfg-run-profile")?.value || "load") : "load",
    payload_set_version: payloadSetVersion,
    ui_profile: document.getElementById("cfg-ui-profile")?.value || null,
    login_mode: document.getElementById("cfg-login-mode")?.value || null,
    payloads: {
      bench_run: bench,
      auth_env: { username: username || undefined },
      payload_set_version: payloadSetVersion
    }
  };
  if(body.test_type === "k6"){
    body.ui_profile = null;
    body.login_mode = null;
  }
  await fetchJson("/api/configs/"+id, {method:"PUT", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  await refreshConfigs();
  selectConfig(id);
}

function newConfig(){
  setMode("configs");
  document.getElementById("main").innerHTML = '<div class="empty">Creating…</div>';
  fetchJson("/api/configs/default").then(async c=>{
    const base = Object.assign({}, c);
    delete base.id;
    delete base.created_at;
    delete base.updated_at;
    base.name = "new-profile";
    base.audience = document.getElementById("f-audience")?.value || "developer";
    base.description = "New Test Agent profile";
    const saved = await fetchJson("/api/configs", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(base)});
    await refreshConfigs();
    selectConfig(saved.id);
  });
}

async function boot(){
  if(localStorage.getItem("spt_sidebar_collapsed")==="1"){
    document.body.classList.add("sidebar-collapsed");
    const btn = document.getElementById("btn-toggle-sidebar");
    if(btn) btn.textContent = "Show list";
  }
  onPresetChange();
  const urlParams = readUrlState();
  applyUrlStateToFilters(urlParams);
  const wantConfig = urlParams.get("config");
  const wantRun = urlParams.get("run");
  const wantSpec = urlParams.get("spec");
  const wantSet = urlParams.get("set");
  const wantView = urlParams.get("view");
  if(urlParams.get("spec_env")) specsEnv = urlParams.get("spec_env");
  if(wantView === "swagger" || wantView === "ops" || wantView === "raw" || wantView === "config" || wantView === "versions" || wantView === "trace"){
    specsView = wantView === "ops" ? "swagger" : wantView;
  }
  const initialMode = wantSpec ? "specs" : (wantConfig ? "configs" : "runs");
  document.body.classList.remove("mode-runs","mode-configs","mode-specs");
  document.body.classList.add("mode-"+initialMode);
  // Load shell data in parallel so one slow API cannot hang the whole portal
  await Promise.allSettled([
    loadCatalog().then(()=> applyUrlStateToFilters(urlParams)).catch(e=> showBanner("Catalog load failed: "+e.message)),
    loadHealth().catch(()=>{}),
    refreshConfigs().catch(()=>{}),
    refreshRuns().catch(()=>{}),
    refreshSpecsList().catch(()=>{}),
  ]);
  try { if(typeof onTestTypeChange === "function") await onTestTypeChange(); } catch(e){ /* optional */ }
  const btn = document.getElementById("btn-api-picker");
  if(btn) btn.textContent = "APIs (all)";
  try {
    if(wantSpec){
      await setMode("specs");
      await selectSpec(wantSpec, {
        skipUrl: true,
        replaceUrl: true,
        setVersion: wantSet != null && wantSet !== "" ? Number(wantSet) : undefined
      });
      syncPortalUrl({ replace: true });
    } else if(wantConfig){
      await setMode("configs");
      await selectConfig(wantConfig, { skipUrl: true, replaceUrl: true });
      syncPortalUrl({ replace: true });
    } else if(wantRun){
      await setMode("runs");
      await selectRun(wantRun, { skipUrl: true, replaceUrl: true });
      syncPortalUrl({ replace: true });
    } else {
      await setMode(initialMode);
      if(initialMode === "runs" && runs.length) await selectRun(runs[0].id, { replaceUrl: true });
      else syncPortalUrl({ replace: true });
    }
  } catch(e){
    showBanner("Detail load failed: "+e.message);
    if(runs.length && !wantRun && !wantSpec){
      try { await selectRun(runs[0].id, { replaceUrl: true }); } catch(_){}
    }
  }
}

window.addEventListener("popstate", async ()=>{
  const params = readUrlState();
  applyUrlStateToFilters(params);
  const wantConfig = params.get("config");
  const wantRun = params.get("run");
  const wantSpec = params.get("spec");
  const wantSet = params.get("set");
  const wantView = params.get("view");
  if(params.get("spec_env")) specsEnv = params.get("spec_env");
  if(wantView === "swagger" || wantView === "ops" || wantView === "raw" || wantView === "config" || wantView === "versions" || wantView === "trace"){
    specsView = wantView === "ops" ? "swagger" : wantView;
  } else if(wantSpec){
    specsView = "overview";
  }
  try {
    if(wantSpec){
      setMode("specs");
      await refreshSpecsList();
      await selectSpec(wantSpec, {
        skipUrl: true,
        setVersion: wantSet != null && wantSet !== "" ? Number(wantSet) : undefined
      });
    } else if(wantConfig){
      setMode("configs");
      await refreshConfigs();
      await selectConfig(wantConfig, { skipUrl: true });
    } else {
      setMode("runs");
      await refreshRuns({resetPage: true});
      if(wantRun) await selectRun(wantRun, { skipUrl: true });
      else if(runs.length) await selectRun(runs[0].id, { skipUrl: true });
    }
  } catch(e){
    showBanner("Navigation failed: "+e.message);
  }
});

boot();
