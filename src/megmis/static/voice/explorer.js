(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const LOC = { name: "Harare" };
  const LOC_BYO = { name: "Bulawayo" };
  const LOC_MUT = { name: "Mutare" };

  /** Sensible Zimbabwe demo payloads keyed by REST path (and MCP tool name). */
  const REST_EXAMPLES = {
    "GET /healthz": { query: {} },
    "GET /api/v1/weather/current": { query: { name: "Harare" } },
    "GET /api/v1/weather/forecast": { query: { name: "Harare", days: 3 } },
    "GET /api/v1/weather/alerts": { query: { name: "Mutare" } },
    "GET /api/v1/weather/air-quality": { query: { name: "Harare" } },
    "GET /api/v1/weather/agricultural": { query: { name: "Gweru" } },
    "GET /api/v1/weather/historical": {
      query: { name: "Harare", start_date: "2024-01-01", end_date: "2024-01-03" },
    },
    "GET /api/v1/weather/compare": { query: { names: "Harare,Bulawayo,Mutare" } },
    "POST /api/v1/weather/risk": {
      body: { location: LOC, activity: "road_trip" },
    },
    "POST /api/v1/weather/activities": {
      body: { location: LOC },
    },
    "GET /api/v1/geo/geocode": { query: { address: "Nyanga, Zimbabwe" } },
    "GET /api/v1/geo/nearby": { query: { name: "Harare", category: "hospital", radius_m: 20000 } },
    "GET /api/v1/geo/emergency": { query: { name: "Harare", type: "hospital" } },
    "POST /api/v1/routes/optimize": {
      body: {
        origin: LOC,
        destination: { name: "Nyamaropa" },
        profile: "safest",
        vehicle_class: "car",
        priorities: ["safe"],
      },
    },
    "POST /api/v1/routes/reroute": {
      body: {
        journey_id: "REPLACE_JOURNEY_ID",
        current_position: { lat: -17.9, lon: 31.2 },
        reason: "conditions_changed",
      },
    },
    "GET /api/v1/routes/{route_id}/conditions": {
      path: { route_id: "REPLACE_ROUTE_ID" },
      query: { corridor: "A3 Harare-Mutare" },
    },
    "GET /api/v1/roads/incidents": { query: { corridor: "Harare-Mutare" } },
    "POST /api/v1/roads/reports": {
      body: {
        location: { name: "Mutare" },
        type: "pothole",
        severity: 3,
        evidence_refs: [],
      },
    },
    "POST /api/v1/journeys": { body: { route_id: "REPLACE_ROUTE_ID" } },
    "GET /api/v1/journeys/{journey_id}": { path: { journey_id: "REPLACE_JOURNEY_ID" } },
    "POST /api/v1/risk/journey": {
      body: {
        origin: LOC,
        destination: LOC_MUT,
        profile: "safest",
        activity: "road_trip",
      },
    },
    "GET /api/v1/risk/{assessment_id}": { path: { assessment_id: "REPLACE_ASSESSMENT_ID" } },
    "GET /api/v1/traffic/congestion": { query: { corridor: "A5 Harare-Bulawayo" } },
    "GET /api/v1/traffic/estimate": { query: { corridor: "A3 Harare-Mutare" } },
    "GET /api/v1/traffic/corridors": { query: {} },
    "GET /api/v1/keys": { query: {} },
    "GET /api/v1/webhooks": { query: {} },
    "GET /api/v1/console/health": { query: {} },
    "GET /api/v1/console/usage": { query: {} },
    "POST /api/v1/agents/sessions": { body: { lang: "en", channel: "ui", scenario: null } },
    "POST /api/v1/agents/scenarios/mutare": { query: { lang: "en" } },
    "GET /api/v1/agents/training/prompts": { query: { lang: "en" } },
  };

  const MCP_EXAMPLES = {
    get_current_weather: { location: LOC },
    get_forecast: { location: LOC, days: 3 },
    get_hourly_forecast: { location: LOC, date: "2026-11-15" },
    get_weather_alerts: { location: LOC_MUT },
    compare_weather: { locations: [LOC, LOC_BYO] },
    get_historical_weather: {
      location: LOC,
      start_date: "2024-01-01",
      end_date: "2024-01-03",
    },
    get_air_quality: { location: LOC },
    get_agricultural_conditions: { location: { name: "Gweru" } },
    analyze_weather_risk: { location: LOC, activity: "outdoor_wedding" },
    recommend_outdoor_activities: { location: LOC },
    geocode: { address: "Nyanga, Zimbabwe" },
    reverse_geocode: { lat: -18.2167, lon: 32.745 },
    find_nearby_places: { location: LOC, category: "hospital", radius_m: 20000 },
    get_emergency_facilities: { location: LOC, type: "hospital" },
    optimize_route: {
      origin: LOC,
      destination: { name: "Nyamaropa" },
      profile: "safest",
      vehicle_class: "car",
      priorities: ["safe"],
    },
    reroute: {
      journey_id: "REPLACE_JOURNEY_ID",
      current_position: { lat: -17.9, lon: 31.2 },
      reason: "conditions_changed",
    },
    get_route_conditions: { corridor: "A3 Harare-Mutare" },
    report_road_condition: {
      location: LOC_MUT,
      type: "pothole",
      severity: 3,
      evidence_refs: [],
    },
    get_road_incidents: { corridor: "Harare-Mutare" },
    assess_journey_risk: {
      origin: LOC,
      destination: LOC_MUT,
      profile: "safest",
      activity: "road_trip",
    },
    get_traffic_congestion: { corridor: "A5 Harare-Bulawayo" },
  };

  const SMOKE_REST = [
    "GET /healthz",
    "GET /api/v1/weather/current",
    "GET /api/v1/weather/forecast",
    "GET /api/v1/weather/alerts",
    "GET /api/v1/geo/geocode",
    "GET /api/v1/geo/nearby",
    "GET /api/v1/geo/emergency",
    "POST /api/v1/routes/optimize",
    "GET /api/v1/roads/incidents",
    "POST /api/v1/risk/journey",
    "GET /api/v1/traffic/corridors",
    "GET /api/v1/traffic/congestion",
    "GET /api/v1/keys",
    "POST /api/v1/agents/sessions",
  ];

  const SMOKE_MCP = [
    "get_current_weather",
    "get_forecast",
    "geocode",
    "optimize_route",
    "get_road_incidents",
    "assess_journey_risk",
    "get_traffic_congestion",
  ];

  const state = {
    tab: "rest",
    apiKey: () => {
      const el = $("#api-key");
      return (el && el.value.trim()) || localStorage.getItem("megmis_api_key") || "";
    },
    restOps: [],
    mcpTools: [],
    selected: null,
    lastIds: { route_id: null, journey_id: null, assessment_id: null, session_id: null },
  };

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function setStatus(msg, ok) {
    const el = $("#api-status");
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle("ok", !!ok);
    el.classList.toggle("bad", ok === false);
  }

  function showResponse(meta, body) {
    const pre = $("#api-response");
    if (!pre) return;
    const text = typeof body === "string" ? body : JSON.stringify(body, null, 2);
    pre.textContent = meta + "\n\n" + text;
    // harvest ids for chained calls
    try {
      const data = typeof body === "string" ? JSON.parse(body) : body;
      const dig = data && (data.data || data);
      if (dig) {
        if (dig.route_id) state.lastIds.route_id = dig.route_id;
        if (dig.id && meta.indexOf("/journeys") >= 0) state.lastIds.journey_id = dig.id;
        if (dig.assessment_id) state.lastIds.assessment_id = dig.assessment_id;
        if (dig.session_id) state.lastIds.session_id = dig.session_id;
        if (dig.routes && dig.route_id) state.lastIds.route_id = dig.route_id;
      }
    } catch (_) {}
  }

  function fillTemplate(obj) {
    const raw = JSON.stringify(obj || {});
    const filled = raw
      .replace(/REPLACE_ROUTE_ID/g, state.lastIds.route_id || "REPLACE_ROUTE_ID")
      .replace(/REPLACE_JOURNEY_ID/g, state.lastIds.journey_id || "REPLACE_JOURNEY_ID")
      .replace(/REPLACE_ASSESSMENT_ID/g, state.lastIds.assessment_id || "REPLACE_ASSESSMENT_ID")
      .replace(/REPLACE_SESSION_ID/g, state.lastIds.session_id || "REPLACE_SESSION_ID");
    return JSON.parse(filled);
  }

  async function restFetch(method, path, { query, body } = {}) {
    let url = path;
    const q = query || {};
    const qs = Object.keys(q)
      .filter((k) => q[k] !== undefined && q[k] !== null && q[k] !== "")
      .map((k) => encodeURIComponent(k) + "=" + encodeURIComponent(q[k]))
      .join("&");
    if (qs) url += (url.indexOf("?") >= 0 ? "&" : "?") + qs;
    const headers = { "X-API-Key": state.apiKey() };
    const opts = { method: method, headers: headers };
    if (body !== undefined && method !== "GET" && method !== "HEAD") {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const t0 = performance.now();
    const res = await fetch(url, opts);
    const ct = res.headers.get("content-type") || "";
    let payload;
    if (ct.indexOf("application/json") >= 0) payload = await res.json();
    else payload = await res.text();
    return {
      ok: res.ok,
      status: res.status,
      ms: Math.round(performance.now() - t0),
      payload: payload,
      method: method,
      url: url,
    };
  }

  async function mcpCall(name, args) {
    const t0 = performance.now();
    const res = await fetch("/mcp/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
        "X-API-Key": state.apiKey(),
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: Date.now(),
        method: "tools/call",
        params: { name: name, arguments: args || {} },
      }),
    });
    const payload = await res.json();
    return {
      ok: res.ok && !payload.error,
      status: res.status,
      ms: Math.round(performance.now() - t0),
      payload: payload,
      method: "MCP",
      url: "tools/call " + name,
    };
  }

  async function mcpListTools() {
    const res = await fetch("/mcp/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
        "X-API-Key": state.apiKey(),
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "tools/list",
        params: {},
      }),
    });
    const data = await res.json();
    return ((data.result || {}).tools || []).map((t) => ({
      name: t.name,
      description: t.description || "",
      inputSchema: t.inputSchema || t.input_schema || {},
    }));
  }

  async function loadOpenApi() {
    const spec = await fetch("/openapi.json").then((r) => r.json());
    const ops = [];
    Object.keys(spec.paths || {}).forEach((path) => {
      const item = spec.paths[path];
      Object.keys(item).forEach((method) => {
        if (!/^(get|post|put|patch|delete)$/i.test(method)) return;
        const op = item[method];
        ops.push({
          method: method.toUpperCase(),
          path: path,
          summary: op.summary || op.operationId || "",
          tags: op.tags || ["other"],
          key: method.toUpperCase() + " " + path,
        });
      });
    });
    // also include root healthz which may be outside /api
    if (!ops.some((o) => o.path === "/healthz")) {
      ops.unshift({
        method: "GET",
        path: "/healthz",
        summary: "Root health",
        tags: ["health"],
        key: "GET /healthz",
      });
    }
    ops.sort((a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method));
    state.restOps = ops;
  }

  function exampleForRest(op) {
    const ex = REST_EXAMPLES[op.key] || {};
    let path = op.path;
    const pathParams = fillTemplate(ex.path || {});
    Object.keys(pathParams).forEach((k) => {
      path = path.replace("{" + k + "}", encodeURIComponent(pathParams[k]));
    });
    return {
      method: op.method,
      path: path,
      query: fillTemplate(ex.query || {}),
      body: ex.body !== undefined ? fillTemplate(ex.body) : op.method === "GET" ? undefined : {},
    };
  }

  function renderCatalog() {
    const root = $("#api-catalog");
    if (!root) return;
    root.innerHTML = "";
    const filter = (($("#api-filter") && $("#api-filter").value) || "").toLowerCase();

    if (state.tab === "rest") {
      const byTag = {};
      state.restOps.forEach((op) => {
        const tag = (op.tags && op.tags[0]) || "other";
        if (filter && (op.key + " " + op.summary + " " + tag).toLowerCase().indexOf(filter) < 0)
          return;
        (byTag[tag] = byTag[tag] || []).push(op);
      });
      Object.keys(byTag)
        .sort()
        .forEach((tag) => {
          const h = document.createElement("div");
          h.className = "api-tag";
          h.textContent = tag;
          root.appendChild(h);
          byTag[tag].forEach((op) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className =
              "api-item" + (state.selected && state.selected.key === op.key ? " active" : "");
            btn.innerHTML =
              '<span class="m ' +
              op.method.toLowerCase() +
              '">' +
              op.method +
              '</span><span class="p">' +
              escapeHtml(op.path) +
              "</span>";
            btn.onclick = () => selectRest(op);
            root.appendChild(btn);
          });
        });
      $("#api-count").textContent = state.restOps.length + " REST ops";
    } else if (state.tab === "mcp") {
      state.mcpTools.forEach((t) => {
        if (filter && (t.name + " " + t.description).toLowerCase().indexOf(filter) < 0) return;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className =
          "api-item" + (state.selected && state.selected.name === t.name ? " active" : "");
        btn.innerHTML =
          '<span class="m mcp">MCP</span><span class="p">' + escapeHtml(t.name) + "</span>";
        btn.title = t.description || "";
        btn.onclick = () => selectMcp(t);
        root.appendChild(btn);
      });
      $("#api-count").textContent = state.mcpTools.length + " MCP tools";
    } else {
      root.innerHTML =
        '<div class="api-tag">Smoke suite</div>' +
        '<p class="api-smoke-note">Runs a curated safe subset of REST + MCP calls with Zimbabwe demo payloads. Destructive key/webhook mutations are skipped.</p>';
      $("#api-count").textContent = SMOKE_REST.length + " REST · " + SMOKE_MCP.length + " MCP";
    }
  }

  function selectRest(op) {
    state.selected = op;
    state.tab = "rest";
    const ex = exampleForRest(op);
    $("#api-method").value = ex.method;
    $("#api-path").value = ex.path;
    $("#api-query").value = JSON.stringify(ex.query || {}, null, 2);
    $("#api-body").value =
      ex.body === undefined ? "" : JSON.stringify(ex.body, null, 2);
    $("#api-meta").textContent = (op.summary || "") + " · " + (op.tags || []).join(", ");
    renderCatalog();
  }

  function selectMcp(tool) {
    state.selected = tool;
    state.tab = "mcp";
    const args = fillTemplate(MCP_EXAMPLES[tool.name] || {});
    $("#api-method").value = "MCP";
    $("#api-path").value = tool.name;
    $("#api-query").value = "{}";
    $("#api-body").value = JSON.stringify(args, null, 2);
    $("#api-meta").textContent = tool.description || "MCP tool";
    renderCatalog();
  }

  async function runSelected() {
    const method = $("#api-method").value.trim();
    const path = $("#api-path").value.trim();
    let query = {};
    let body;
    try {
      query = JSON.parse($("#api-query").value || "{}");
    } catch (e) {
      setStatus("Query JSON invalid: " + e.message, false);
      return;
    }
    const bodyRaw = ($("#api-body").value || "").trim();
    if (bodyRaw) {
      try {
        body = JSON.parse(bodyRaw);
      } catch (e) {
        setStatus("Body JSON invalid: " + e.message, false);
        return;
      }
    }
    setStatus("Running…", true);
    try {
      let result;
      if (method === "MCP") {
        result = await mcpCall(path, body || {});
      } else {
        result = await restFetch(method, path, { query: query, body: body });
      }
      showResponse(
        result.method + " " + result.url + " → " + result.status + " (" + result.ms + " ms)",
        result.payload
      );
      setStatus(result.ok ? "OK " + result.status : "Failed " + result.status, result.ok);
    } catch (e) {
      showResponse("error", String(e && e.message ? e.message : e));
      setStatus("Request failed", false);
    }
  }

  async function runSmoke() {
    const log = [];
    setStatus("Running smoke suite…", true);
    let pass = 0;
    let fail = 0;

    for (let i = 0; i < SMOKE_REST.length; i++) {
      const key = SMOKE_REST[i];
      const op = state.restOps.find((o) => o.key === key) || {
        method: key.split(" ")[0],
        path: key.split(" ").slice(1).join(" "),
        key: key,
        tags: [],
        summary: "",
      };
      const ex = exampleForRest(op);
      try {
        const r = await restFetch(ex.method, ex.path, { query: ex.query, body: ex.body });
        if (r.ok) pass++;
        else fail++;
        log.push({
          kind: "REST",
          key: key,
          status: r.status,
          ms: r.ms,
          ok: r.ok,
        });
        // capture route id from optimize
        if (key.indexOf("/routes/optimize") >= 0 && r.payload && r.payload.data) {
          state.lastIds.route_id = r.payload.data.route_id || state.lastIds.route_id;
        }
      } catch (e) {
        fail++;
        log.push({ kind: "REST", key: key, ok: false, error: String(e) });
      }
    }

    for (let i = 0; i < SMOKE_MCP.length; i++) {
      const name = SMOKE_MCP[i];
      try {
        const r = await mcpCall(name, fillTemplate(MCP_EXAMPLES[name] || {}));
        if (r.ok) pass++;
        else fail++;
        log.push({ kind: "MCP", key: name, status: r.status, ms: r.ms, ok: r.ok });
      } catch (e) {
        fail++;
        log.push({ kind: "MCP", key: name, ok: false, error: String(e) });
      }
    }

    showResponse("Smoke suite: " + pass + " passed, " + fail + " failed", log);
    setStatus("Smoke done — " + pass + " ok / " + fail + " failed", fail === 0);
  }

  function setTab(tab) {
    state.tab = tab;
    $$("[data-api-tab]").forEach((b) => b.classList.toggle("active", b.dataset.apiTab === tab));
    renderCatalog();
    if (tab === "smoke") {
      $("#api-method").value = "SMOKE";
      $("#api-path").value = "suite";
      $("#api-query").value = "{}";
      $("#api-body").value = JSON.stringify({ rest: SMOKE_REST, mcp: SMOKE_MCP }, null, 2);
      $("#api-meta").textContent = "Curated non-destructive smoke coverage";
    }
  }

  async function boot() {
    if (!$("#api-explorer")) return;
    try {
      await loadOpenApi();
      state.mcpTools = await mcpListTools();
      setStatus(
        "Loaded " + state.restOps.length + " REST + " + state.mcpTools.length + " MCP tools",
        true
      );
      setTab("rest");
      const first = state.restOps.find((o) => o.key === "GET /api/v1/weather/current") || state.restOps[0];
      if (first) selectRest(first);
    } catch (e) {
      setStatus("Failed to load catalog: " + (e.message || e), false);
    }

    $$("[data-api-tab]").forEach((b) => {
      b.onclick = () => setTab(b.dataset.apiTab);
    });
    const filter = $("#api-filter");
    if (filter) filter.addEventListener("input", () => renderCatalog());
    $("#btn-api-run").onclick = () => {
      if (state.tab === "smoke" || $("#api-method").value === "SMOKE") runSmoke().catch(console.error);
      else runSelected().catch(console.error);
    };
    $("#btn-api-smoke").onclick = () => runSmoke().catch(console.error);
    $("#btn-api-reload").onclick = () => boot().catch(console.error);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => boot().catch(console.error));
  } else {
    boot().catch(console.error);
  }
})();
