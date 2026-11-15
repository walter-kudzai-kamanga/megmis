(() => {
  const $ = (sel) => document.querySelector(sel);
  const DEFAULT_KEY = "meg_local_49a3245c285d784ab6f8a9d86e961c8f";
  const state = {
    apiKey: localStorage.getItem("megmis_api_key") || DEFAULT_KEY,
    lang: localStorage.getItem("megmis_voice_lang") || "en",
    sessionId: null,
    recording: false,
    mediaRecorder: null,
    chunks: [],
    audioCtx: null,
    analyser: null,
    raf: 0,
    ws: null,
    map: null,
    mapLayers: [],
  };
  const ROUTE_COLORS = ["#c47a3a", "#3a8fc4", "#6aa84f", "#c44a7a"];
  if (!state.apiKey || !String(state.apiKey).trim()) {
    state.apiKey = DEFAULT_KEY;
  }

  const api = (path, opts) => {
    opts = opts || {};
    const headers = Object.assign({}, opts.headers || {}, { "X-API-Key": state.apiKey });
    const fetchOpts = Object.assign({}, opts, { headers: headers });
    if (opts.json) {
      headers["Content-Type"] = "application/json";
      fetchOpts.body = JSON.stringify(opts.json);
      delete fetchOpts.json;
    }
    return fetch("/api/v1" + path, fetchOpts).then(async (r) => {
      const ct = r.headers.get("content-type") || "";
      if (!r.ok) {
        const t = await r.text();
        throw new Error(r.status + " " + t);
      }
      if (ct.indexOf("application/json") >= 0) return r.json();
      return r;
    });
  };

  function logTurn(role, text, meta) {
    meta = meta || "";
    const box = $("#transcript");
    const div = document.createElement("div");
    div.innerHTML =
      '<span class="turn-' +
      role +
      '">' +
      (role === "user" ? "You" : "Agent") +
      ":</span> " +
      escapeHtml(text) +
      (meta ? '<div class="turn-meta">' + escapeHtml(meta) + "</div>" : "");
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function setStatus(id, text, ok) {
    const el = $(id);
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("ok", !!ok);
  }

  function showBanner(msg, ok) {
    const el = $("#banner");
    if (!el) return;
    el.hidden = !msg;
    el.textContent = msg || "";
    el.classList.toggle("ok", !!ok);
  }

  function flashError(err) {
    const msg = err && err.message ? err.message : String(err);
    showBanner("Request failed: " + msg + ". Is the API running on this host/port?", false);
    console.error(err);
  }

  function renderTools(trace) {
    trace = trace || [];
    const root = $("#tools");
    root.innerHTML = "";
    if (!trace.length) {
      root.innerHTML =
        '<div class="tool-row"><span class="dot warn"></span><span>No tools yet</span><span>-</span></div>';
      return;
    }
    trace.forEach((t) => {
      const row = document.createElement("div");
      row.className = "tool-row";
      const name = t.tool || t;
      let extra = "ok";
      if (t.ranked_routes) extra = t.ranked_routes.length + " routes";
      else if (t.origin && t.destination) extra = t.origin + " → " + t.destination;
      else if (t.place) extra = t.place;
      row.innerHTML =
        '<span class="dot"></span><span>' +
        escapeHtml(name) +
        "</span><span>" +
        escapeHtml(extra) +
        "</span>";
      root.appendChild(row);
    });
  }

  function ensureMap() {
    const el = $("#route-map");
    if (!el || typeof L === "undefined") return null;
    if (state.map) return state.map;
    state.map = L.map(el, { zoomControl: true, attributionControl: true }).setView(
      [-18.5, 30.5],
      6
    );
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 16,
      attribution: "&copy; OpenStreetMap",
    }).addTo(state.map);
    setTimeout(function () {
      state.map.invalidateSize();
    }, 80);
    return state.map;
  }

  function clearMapLayers() {
    if (!state.map) return;
    state.mapLayers.forEach(function (layer) {
      try {
        state.map.removeLayer(layer);
      } catch (_) {}
    });
    state.mapLayers = [];
  }

  function renderMap(mapPayload) {
    const map = ensureMap();
    if (!map) return;
    clearMapLayers();
    if (!mapPayload) {
      map.setView([-18.5, 30.5], 6);
      return;
    }
    const bounds = [];
    const o = mapPayload.origin || {};
    const d = mapPayload.destination || {};
    if (o.lat != null && o.lon != null) {
      const m = L.marker([o.lat, o.lon]).bindPopup("From: " + (o.name || "origin"));
      m.addTo(map);
      state.mapLayers.push(m);
      bounds.push([o.lat, o.lon]);
    }
    if (d.lat != null && d.lon != null) {
      const m = L.marker([d.lat, d.lon]).bindPopup("To: " + (d.name || "destination"));
      m.addTo(map);
      state.mapLayers.push(m);
      bounds.push([d.lat, d.lon]);
    }
    (mapPayload.routes || []).forEach(function (r, idx) {
      const geom = r.geometry || [];
      if (!geom.length) return;
      const latlngs = geom.map(function (p) {
        return [p[0], p[1]];
      });
      const color = ROUTE_COLORS[idx % ROUTE_COLORS.length];
      const line = L.polyline(latlngs, {
        color: color,
        weight: idx === 0 ? 5 : 3,
        opacity: idx === 0 ? 0.95 : 0.65,
        dashArray: idx === 0 ? null : "8 6",
      }).bindPopup(
        "#" +
          (r.rank || idx + 1) +
          " " +
          (r.label || "") +
          "<br/>" +
          (((r.distance_m || 0) / 1000).toFixed(1) + " km")
      );
      line.addTo(map);
      state.mapLayers.push(line);
      latlngs.forEach(function (ll) {
        bounds.push(ll);
      });
    });
    if (bounds.length) {
      map.fitBounds(bounds, { padding: [28, 28] });
    }
    setTimeout(function () {
      map.invalidateSize();
    }, 60);
  }

  function renderResults(results) {
    const root = $("#results");
    if (!root) return;
    root.innerHTML = "";
    if (!results) {
      root.innerHTML =
        '<div class="result-empty">Ask anything — Dijkstra routes appear on the map.</div>';
      renderMap(null);
      return;
    }
    renderMap(results.map || null);
    const u = results.understood || {};
    const bits = [];
    bits.push(
      '<div class="result-card"><h3>Understood</h3><pre>' +
        escapeHtml(
          JSON.stringify(
            {
              intent: u.intent,
              from: u.origin,
              to: u.destination,
              profile: u.profile,
              places: u.places,
              algorithm: (results.route && results.route.algorithm) || "dijkstra",
            },
            null,
            2
          )
        ) +
        "</pre></div>"
    );
    if (results.ranked_routes) {
      const lines = (results.ranked_routes || [])
        .map(function (r) {
          const km = ((r.distance_m || 0) / 1000).toFixed(1);
          const mins = Math.round((r.duration_s || 0) / 60);
          return (
            "#" +
            r.rank +
            " " +
            (r.label || "") +
            " — " +
            km +
            " km / " +
            mins +
            " min\n  " +
            (r.via || "") +
            "\n  " +
            (r.explanation || "")
          );
        })
        .join("\n");
      bits.push(
        '<div class="result-card"><h3>Dijkstra ranked routes</h3><pre>' +
          escapeHtml(lines) +
          "</pre></div>"
      );
    }
    if (results.weather) {
      bits.push(
        '<div class="result-card"><h3>Weather</h3><pre>' +
          escapeHtml(JSON.stringify(results.weather, null, 2)) +
          "</pre></div>"
      );
    }
    if (results.risk) {
      bits.push(
        '<div class="result-card"><h3>Journey risk</h3><pre>' +
          escapeHtml(JSON.stringify(results.risk, null, 2)) +
          "</pre></div>"
      );
    }
    if (results.journey) {
      bits.push(
        '<div class="result-card"><h3>Journey monitor</h3><pre>' +
          escapeHtml(JSON.stringify(results.journey, null, 2)) +
          "</pre></div>"
      );
    }
    if (results.incidents) {
      bits.push(
        '<div class="result-card"><h3>Incidents</h3><pre>' +
          escapeHtml(JSON.stringify(results.incidents, null, 2)) +
          "</pre></div>"
      );
    }
    if (results.help) {
      bits.push(
        '<div class="result-card"><h3>Help</h3><pre>' +
          escapeHtml(JSON.stringify(results.help, null, 2)) +
          "</pre></div>"
      );
    }
    root.innerHTML = bits.join("");
  }

  async function ensureSession(forceNew) {
    if (state.sessionId && !forceNew) return state.sessionId;
    if (state.ws) {
      try {
        state.ws.close();
      } catch (_) {}
      state.ws = null;
    }
    const res = await api("/agents/sessions", {
      method: "POST",
      json: { lang: state.lang, channel: "ui", scenario: null },
    });
    state.sessionId = res.data.session_id;
    setStatus("#chip-session", "session " + state.sessionId.slice(0, 8) + "...", true);
    logTurn("agent", res.data.greeting || "Session ready. Ask any corridor.");
    connectWs();
    return state.sessionId;
  }

  function connectWs() {
    if (!state.sessionId) return;
    if (state.ws) {
      try {
        state.ws.close();
      } catch (_) {}
    }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url =
      proto +
      "://" +
      location.host +
      "/ws/voice/" +
      state.sessionId +
      "?api_key=" +
      encodeURIComponent(state.apiKey) +
      "&lang=" +
      state.lang;
    const ws = new WebSocket(url);
    state.ws = ws;
    ws.binaryType = "arraybuffer";
    ws.onopen = () => setStatus("#chip-ws", "ws connected", true);
    ws.onclose = () => setStatus("#chip-ws", "ws closed", false);
    ws.onerror = () => setStatus("#chip-ws", "ws error", false);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "agent" && msg.data) applyAgent(msg.data);
        else if (msg.type === "stt" && msg.data) {
          logTurn("user", msg.data.text || "(empty)", "stt conf " + (msg.data.confidence || "?"));
        } else if (msg.type === "ready") setStatus("#chip-ws", "ws ready", true);
      } catch (_) {}
    };
  }

  function applyAgent(data) {
    const u = (data.results && data.results.understood) || {};
    const meta =
      "intent " +
      (data.intent || "?") +
      (u.origin && u.destination ? " · " + u.origin + " → " + u.destination : "");
    logTurn("agent", data.reply_text || "", meta);
    renderTools(data.tool_trace || []);
    renderResults(data.results || null);
    if (data.audio && data.audio.audio_b64) {
      const mime = data.audio.mime || "audio/mpeg";
      const audio = new Audio("data:" + mime + ";base64," + data.audio.audio_b64);
      audio.play().catch(() => {});
    }
    if (data.tool_trace) {
      const mon = data.tool_trace.find((t) => t.tool === "journey.monitor");
      if (mon) {
        setStatus(
          "#chip-journey",
          "journey " + String(mon.journey_id || "").slice(0, 8) + "...",
          true
        );
      }
    }
  }

  async function sendText() {
    const text = $("#utterance").value.trim();
    if (!text) return;
    await ensureSession();
    logTurn("user", text);
    $("#utterance").value = "";
    if (state.ws && state.ws.readyState === 1) {
      state.ws.send(
        JSON.stringify({ type: "utterance", text: text, lang: state.lang, synthesize: true })
      );
      return;
    }
    const res = await api("/agents/sessions/" + state.sessionId + "/utterance", {
      method: "POST",
      json: { text: text, lang: state.lang, synthesize: true },
    });
    applyAgent(res.data);
  }

  function drawWave() {
    const canvas = $("#wave");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);
    if (!state.analyser) {
      ctx.strokeStyle = "#2a3b32";
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();
      return;
    }
    const buf = new Uint8Array(state.analyser.frequencyBinCount);
    state.analyser.getByteTimeDomainData(buf);
    ctx.strokeStyle = "#c47a3a";
    ctx.lineWidth = 2;
    ctx.beginPath();
    const slice = width / buf.length;
    for (let i = 0; i < buf.length; i++) {
      const v = buf[i] / 128.0;
      const y = (v * height) / 2;
      const x = i * slice;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    state.raf = requestAnimationFrame(drawWave);
  }

  async function toggleMic() {
    if (state.recording) {
      if (state.mediaRecorder) state.mediaRecorder.stop();
      state.recording = false;
      $("#mic").classList.remove("live");
      $("#mic").textContent = "Mic";
      cancelAnimationFrame(state.raf);
      return;
    }
    await ensureSession();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const src = state.audioCtx.createMediaStreamSource(stream);
    state.analyser = state.audioCtx.createAnalyser();
    state.analyser.fftSize = 2048;
    src.connect(state.analyser);
    drawWave();

    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";
    const rec = new MediaRecorder(stream, { mimeType: mime });
    state.chunks = [];
    rec.ondataavailable = (e) => {
      if (e.data.size) state.chunks.push(e.data);
    };
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(state.chunks, { type: mime });
      await uploadAudio(blob);
    };
    rec.start();
    state.mediaRecorder = rec;
    state.recording = true;
    $("#mic").classList.add("live");
    $("#mic").textContent = "Stop";
  }

  async function uploadAudio(blob) {
    await ensureSession();
    const fd = new FormData();
    fd.append("audio", blob, "utterance.webm");
    fd.append("lang", state.lang);
    fd.append("synthesize", "true");
    fd.append("run_agent", "true");
    const res = await fetch("/api/v1/agents/sessions/" + state.sessionId + "/stt", {
      method: "POST",
      headers: { "X-API-Key": state.apiKey },
      body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    const body = await res.json();
    if (body.data && body.data.stt && body.data.stt.text) {
      logTurn("user", body.data.stt.text, "whisper " + (body.data.stt.provider || ""));
    }
    if (body.data && body.data.agent) applyAgent(body.data.agent);
  }

  function parseOdFromText(text) {
    const t = String(text || "").trim();
    let m = t.match(/\bfrom\s+(.+?)\s+to\s+(.+)$/i);
    if (!m) m = t.match(/^\s*(.+?)\s+to\s+(.+)\s*$/i);
    if (!m) return null;
    return { origin: m[1].trim(), destination: m[2].trim() };
  }

  async function mcpTool(name, args) {
    const res = await fetch("/mcp/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
        "X-API-Key": state.apiKey,
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: Date.now(),
        method: "tools/call",
        params: { name: name, arguments: args || {} },
      }),
    });
    const data = await res.json();
    if (data.error) throw new Error(JSON.stringify(data.error));
    return data.result;
  }

  async function recordOnce() {
    await ensureSession();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";
    const rec = new MediaRecorder(stream, { mimeType: mime });
    const chunks = [];
    return new Promise((resolve, reject) => {
      rec.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data);
      };
      rec.onerror = (e) => reject(e.error || new Error("recorder error"));
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        resolve(new Blob(chunks, { type: mime }));
      };
      rec.start();
      setStatus("#chip-mcp-whisper", "listening 4s…", false);
      setTimeout(() => {
        try {
          rec.stop();
        } catch (e) {
          reject(e);
        }
      }, 4000);
    });
  }

  async function sttBlob(blob, runAgent) {
    await ensureSession();
    const fd = new FormData();
    fd.append("audio", blob, "utterance.webm");
    fd.append("lang", state.lang);
    fd.append("synthesize", "false");
    fd.append("run_agent", runAgent ? "true" : "false");
    const res = await fetch("/api/v1/agents/sessions/" + state.sessionId + "/stt", {
      method: "POST",
      headers: { "X-API-Key": state.apiKey },
      body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async function whisperOnly() {
    const out = $("#whisper-mcp-out");
    out.textContent = "Recording… speak now";
    const blob = await recordOnce();
    out.textContent = "Transcribing with Whisper…";
    const body = await sttBlob(blob, false);
    const stt = (body.data && body.data.stt) || {};
    setStatus("#chip-speech", "STT: " + (stt.provider || "?") + " · " + (stt.model || ""), true);
    setStatus("#chip-stt-provider", "speech " + (stt.provider || "?"), true);
    setStatus("#chip-mcp-whisper", "STT done", true);
    out.textContent = JSON.stringify({ stt: stt }, null, 2);
    if (stt.text) {
      $("#utterance").value = stt.text;
      logTurn("user", stt.text, "whisper-only " + (stt.provider || ""));
    }
  }

  async function whisperToMcp() {
    const out = $("#whisper-mcp-out");
    out.textContent = "Recording… speak a route (e.g. Harare to Kariba)";
    const blob = await recordOnce();
    out.textContent = "Whisper STT…";
    setStatus("#chip-mcp-whisper", "whisper…", false);
    const body = await sttBlob(blob, false);
    const stt = (body.data && body.data.stt) || {};
    setStatus("#chip-speech", "STT: " + (stt.provider || "?") + " · " + (stt.model || ""), !!stt.provider);
    setStatus("#chip-stt-provider", "speech " + (stt.provider || "?"), true);
    const text = stt.text || "";
    if (!text) {
      out.textContent = JSON.stringify({ error: "empty transcript", stt: stt }, null, 2);
      setStatus("#chip-mcp-whisper", "empty STT", false);
      return;
    }
    logTurn("user", text, "whisper→mcp " + (stt.provider || ""));
    $("#utterance").value = text;
    const od = parseOdFromText(text);
    const trace = { transcript: text, stt: stt, mcp: [] };
    setStatus("#chip-mcp-whisper", "calling MCP…", false);

    if (od) {
      const route = await mcpTool("optimize_route", {
        origin: { name: od.origin },
        destination: { name: od.destination },
        profile: /fast/i.test(text) ? "fastest" : "safest",
      });
      trace.mcp.push({ tool: "optimize_route", result: route });
      const risk = await mcpTool("assess_journey_risk", {
        origin: { name: od.origin },
        destination: { name: od.destination },
        profile: "safest",
      });
      trace.mcp.push({ tool: "assess_journey_risk", result: risk });
      const wx = await mcpTool("get_current_weather", {
        location: { name: od.destination },
      });
      trace.mcp.push({ tool: "get_current_weather", result: wx });
      // Also run through voice agent so map/results update
      const agent = await api("/agents/sessions/" + state.sessionId + "/utterance", {
        method: "POST",
        json: { text: text, lang: state.lang, synthesize: true },
      });
      applyAgent(agent.data);
    } else {
      const geo = await mcpTool("geocode", { address: text });
      trace.mcp.push({ tool: "geocode", result: geo });
      const agent = await api("/agents/sessions/" + state.sessionId + "/utterance", {
        method: "POST",
        json: { text: text, lang: state.lang, synthesize: true },
      });
      applyAgent(agent.data);
    }

    out.textContent = JSON.stringify(trace, null, 2);
    setStatus("#chip-mcp-whisper", "MCP done (" + trace.mcp.length + " tools)", true);
    showBanner("Whisper → MCP finished (" + (stt.provider || "stt") + ").", true);
  }

  function setLang(lang) {
    state.lang = lang;
    localStorage.setItem("megmis_voice_lang", lang);
    document.querySelectorAll("[data-lang]").forEach((b) => {
      b.classList.toggle("active", b.dataset.lang === lang);
    });
  }

  function bind() {
    const keyInput = $("#api-key");
    if (keyInput) {
      keyInput.value = state.apiKey || DEFAULT_KEY;
      state.apiKey = keyInput.value.trim();
      localStorage.setItem("megmis_api_key", state.apiKey);
      keyInput.addEventListener("change", (e) => {
        state.apiKey = e.target.value.trim() || DEFAULT_KEY;
        e.target.value = state.apiKey;
        localStorage.setItem("megmis_api_key", state.apiKey);
        state.sessionId = null;
      });
    }
    $("#btn-session").onclick = () =>
      ensureSession(true)
        .then(() =>
          showBanner("Fresh interactive session — say e.g. route from Bulawayo to Gweru.", true)
        )
        .catch(flashError);
    $("#btn-send").onclick = () => sendText().catch(flashError);
    $("#utterance").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendText().catch(flashError);
      }
    });
    $("#mic").onclick = () => toggleMic().catch(flashError);
    const btnWm = $("#btn-whisper-mcp");
    if (btnWm) btnWm.onclick = () => whisperToMcp().catch(flashError);
    const btnWo = $("#btn-whisper-only");
    if (btnWo) btnWo.onclick = () => whisperOnly().catch(flashError);
    document.querySelectorAll("[data-lang]").forEach((b) => {
      b.onclick = () => setLang(b.dataset.lang);
    });
    const canvas = $("#wave");
    const resize = () => {
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
    };
    resize();
    window.addEventListener("resize", resize);
    setLang(state.lang);
    drawWave();
    fetch("/healthz")
      .then((r) => {
        if (!r.ok) throw new Error("healthz " + r.status);
        return r.json();
      })
      .then((h) => {
        const ok = h.status === "ok" || h.status === "degraded";
        showBanner(
          ok
            ? "API connected (" +
                h.status +
                "). Open a session — type any place, or use Whisper → MCP."
            : "API unhealthy: " + JSON.stringify(h),
          ok
        );
        ensureMap();
        setStatus("#chip-session", ok ? "api up" : "api down", ok);
        setStatus("#chip-stt-provider", "speech ready", ok);
      })
      .catch(() => {
        showBanner(
          "Cannot reach the Mamiriro API. Start it with: uvicorn megmis.main:app --port 8000",
          false
        );
        setStatus("#chip-session", "api down", false);
      });
  }

  bind();
})();
