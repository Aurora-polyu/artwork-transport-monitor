(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const METRICS = {
    temperature_c: { label: "Temperature", color: "#326a9e", unit: "°C", decimals: 1 },
    humidity_percent_rh: { label: "Humidity", color: "#217143", unit: "%RH", decimals: 1 },
    light_lux: { label: "Light", color: "#a95e00", unit: "lux", decimals: 0 },
    gravity_deviation_g: { label: "Gravity Deviation", color: "#7561a8", unit: "g", decimals: 3 },
  };
  const state = {
    snapshot: null,
    capabilities: null,
    selectedSessionId: "",
    sessionData: null,
    liveEvents: [],
    reportUrl: null,
    socketState: "connecting",
    requestNumber: 0,
    error: "",
  };

  const byId = (id) => document.getElementById(id);
  const svg = (name, attributes = {}) => {
    const element = document.createElementNS(SVG_NS, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  };
  const setText = (id, value) => { byId(id).textContent = value; };
  const records = () => state.sessionData ? state.sessionData.records : [];
  const latestRecord = () => records().length ? records()[records().length - 1] : null;
  const timestampText = (value) => value ? value.replace("T", " ") : "—";
  const numberText = (value, metric) => Number(value).toFixed(METRICS[metric].decimals);

  function addEvent(event) {
    const key = [event.type, event.timestamp || "", event.message].join("|");
    if (!state.liveEvents.some((item) => item.key === key)) {
      state.liveEvents.unshift({ ...event, key });
      state.liveEvents = state.liveEvents.slice(0, 40);
    }
  }

  function setSocketState(value) {
    state.socketState = value;
    render();
  }

  function renderBanner() {
    const banner = byId("dashboard-banner");
    const message = state.error || (state.socketState === "disconnected" ? "Live updates disconnected. Last loaded session data remains available." : "");
    banner.textContent = message;
    banner.classList.toggle("is-hidden", !message);
  }

  function renderHeader() {
    const transport = state.snapshot && state.snapshot.transport;
    const lifecycle = transport ? transport.state : "not_started";
    setText("lifecycle-status", lifecycle === "not_started" ? "Not started" : lifecycle === "running" ? "Running" : "Completed");
    const connection = byId("connection-status");
    const labels = { connected: "Connected", connecting: "Connecting", disconnected: "Disconnected" };
    connection.className = `connection-state is-${state.socketState}`;
    connection.innerHTML = "";
    const dot = document.createElement("span");
    dot.className = "status-dot";
    connection.append(dot, document.createTextNode(labels[state.socketState] || "Disconnected"));
    const simulation = state.capabilities && state.capabilities.sensors && state.capabilities.sensors.state === "simulated";
    byId("simulation-badge").classList.toggle("is-hidden", !simulation);
  }

  function renderSessionPicker() {
    const select = byId("session-select");
    const transport = state.snapshot && state.snapshot.transport;
    const sessionIds = state.snapshot && state.snapshot.session_ids ? [...state.snapshot.session_ids] : [];
    if (transport && transport.session_id && !sessionIds.includes(transport.session_id)) sessionIds.unshift(transport.session_id);
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = sessionIds.length ? "Select a session" : "No sessions available";
    select.append(empty);
    sessionIds.forEach((sessionId) => {
      const option = document.createElement("option");
      option.value = sessionId;
      option.textContent = sessionId;
      select.append(option);
    });
    select.disabled = !sessionIds.length;
    select.value = state.selectedSessionId;
    setText("session-started", state.sessionData ? timestampText(state.sessionData.started_at) : "—");
    setText("session-ended", state.sessionData && state.sessionData.ended_at ? timestampText(state.sessionData.ended_at) : "—");
  }

  function metricStatus(metric, value) {
    if (value === null || value === undefined) return { text: "Unavailable", className: "" };
    if (metric === "temperature_c") return value >= 18 && value <= 27 ? { text: "Normal", className: "is-normal" } : { text: "Outside approved range", className: "is-violation" };
    if (metric === "humidity_percent_rh") return value >= 25 && value <= 75 ? { text: "Normal", className: "is-normal" } : { text: "Outside approved range", className: "is-violation" };
    if (metric === "light_lux") return value <= 6000 ? { text: "Normal", className: "is-normal" } : { text: "Above approved limit", className: "is-violation" };
    return { text: "Provisional calibration", className: "is-provisional" };
  }

  function renderSparkline(target, values, color) {
    target.replaceChildren();
    if (!values.length) return;
    const width = 180;
    const height = 34;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const points = values.map((value, index) => `${index * (width / Math.max(values.length - 1, 1))},${height - 3 - ((value - min) / range) * (height - 7)}`).join(" ");
    target.append(svg("line", { x1: 0, y1: height - 2, x2: width, y2: height - 2, stroke: "#e7e0d5", "stroke-width": 1 }));
    target.append(svg("polyline", { points, fill: "none", stroke: color, "stroke-width": 1.9, "stroke-linecap": "round", "stroke-linejoin": "round" }));
  }

  function renderMetrics() {
    const latest = latestRecord();
    document.querySelectorAll("[data-metric]").forEach((card) => {
      const metric = card.dataset.metric;
      const value = latest && latest.reading[metric];
      card.querySelector("[data-value]").textContent = value === null || value === undefined ? "—" : numberText(value, metric);
      const status = card.querySelector("[data-status]");
      const presentation = latest ? metricStatus(metric, value) : { text: state.selectedSessionId ? "Empty session" : "Awaiting first cycle", className: "" };
      status.className = `metric-status ${presentation.className}`;
      status.textContent = presentation.text;
      const values = records().map((record) => record.reading[metric]).filter((item) => item !== null && item !== undefined);
      renderSparkline(card.querySelector("[data-sparkline]"), values, METRICS[metric].color);
    });
  }

  function chartMessage(target, message) {
    target.replaceChildren();
    const label = svg("text", { x: 30, y: 50, class: "svg-empty" });
    label.textContent = message;
    target.append(label);
  }

  function renderHistory() {
    const target = byId("history-chart");
    const message = byId("history-empty");
    const source = records();
    const available = Object.keys(METRICS).some((metric) => source.some((record) => record.reading[metric] !== null && record.reading[metric] !== undefined));
    if (!state.selectedSessionId) { target.classList.add("is-empty"); chartMessage(target, "Select a session to view environmental history."); message.textContent = "No selected session."; return; }
    if (!available) { target.classList.add("is-empty"); chartMessage(target, source.length ? "No environmental readings are available for this session." : "This session has no monitoring records yet."); message.textContent = source.length ? "Unavailable readings are not plotted." : "Empty session."; return; }
    target.classList.remove("is-empty");
    target.replaceChildren();
    const width = 820, height = 300, left = 42, right = 20, top = 22, bottom = 34;
    [top, 85, 148, 211, height - bottom].forEach((y) => target.append(svg("line", { x1: left, y1: y, x2: width - right, y2: y, class: "svg-axis" })));
    Object.entries(METRICS).forEach(([metric, definition]) => {
      const values = source.map((record) => record.reading[metric]);
      const finite = values.filter((value) => value !== null && value !== undefined);
      if (!finite.length) return;
      const min = Math.min(...finite), max = Math.max(...finite), range = max - min || 1;
      const points = values.map((value, index) => {
        if (value === null || value === undefined) return null;
        const x = left + index * ((width - left - right) / Math.max(source.length - 1, 1));
        const y = top + (height - top - bottom) - ((value - min) / range) * (height - top - bottom);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).filter(Boolean);
      if (points.length === 1) {
        const [x, y] = points[0].split(",");
        target.append(svg("circle", { cx: x, cy: y, r: 3.5, fill: definition.color }));
      } else target.append(svg("polyline", { points: points.join(" "), class: "svg-line", stroke: definition.color }));
      const label = svg("text", { x: left, y: 15 + Object.keys(METRICS).indexOf(metric) * 13, class: "svg-label", fill: definition.color });
      label.textContent = `${definition.label}: ${numberText(min, metric)}–${numberText(max, metric)} ${definition.unit}`;
      target.append(label);
    });
    const start = svg("text", { x: left, y: height - 11, class: "svg-label" });
    start.textContent = timestampText(source[0].reading.timestamp);
    target.append(start);
    const latest = source[source.length - 1];
    const end = svg("text", { x: width - right, y: height - 11, class: "svg-label", "text-anchor": "end" });
    end.textContent = timestampText(latest.reading.timestamp);
    target.append(end);
    message.textContent = source.length === 1 ? "One reading recorded; a trend requires additional cycles." : "Each line is scaled independently for its own unit.";
  }

  function renderRoute() {
    const target = byId("route-chart");
    const message = byId("route-empty");
    const gpsRecords = records().map((record) => record.gps).filter(Boolean);
    const fixes = gpsRecords.filter((point) => point.status === "fix");
    const noFixCount = gpsRecords.filter((point) => point.status === "no_fix").length;
    if (!state.selectedSessionId) { chartMessage(target, "Select a session to view its GPS trace."); message.textContent = "No selected session."; return; }
    if (!fixes.length) { chartMessage(target, noFixCount ? "GPS unavailable: only no-fix records were retained." : "No GPS records are available for this session."); message.textContent = noFixCount ? `${noFixCount} no-fix record${noFixCount === 1 ? "" : "s"} retained.` : "GPS unavailable."; return; }
    target.replaceChildren();
    const width = 420, height = 190, pad = 25;
    const lats = fixes.map((point) => point.latitude), lngs = fixes.map((point) => point.longitude);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
    const latRange = maxLat - minLat || 0.001, lngRange = maxLng - minLng || 0.001;
    const project = (point) => ({ x: pad + ((point.longitude - minLng) / lngRange) * (width - pad * 2), y: height - pad - ((point.latitude - minLat) / latRange) * (height - pad * 2) });
    target.append(svg("rect", { x: 0, y: 0, width, height, rx: 9, fill: "#fbf8f2" }));
    target.append(svg("line", { x1: pad, y1: height - pad, x2: width - pad, y2: height - pad, class: "svg-axis" }));
    target.append(svg("line", { x1: pad, y1: pad, x2: pad, y2: height - pad, class: "svg-axis" }));
    const points = fixes.map(project);
    if (points.length > 1) target.append(svg("polyline", { points: points.map((point) => `${point.x},${point.y}`).join(" "), class: "svg-route" }));
    const first = points[0], last = points[points.length - 1];
    target.append(svg("circle", { cx: first.x, cy: first.y, r: 6, class: "svg-start" }));
    const completed = state.sessionData && state.sessionData.ended_at;
    if (points.length > 1) target.append(svg("circle", { cx: last.x, cy: last.y, r: 6, class: completed ? "svg-end" : "svg-current" }));
    const firstLabel = svg("text", { x: first.x + 8, y: first.y - 8, class: "svg-label" }); firstLabel.textContent = "Start"; target.append(firstLabel);
    const currentLabel = svg("text", { x: last.x + 8, y: last.y + 16, class: "svg-label" }); currentLabel.textContent = points.length > 1 ? (completed ? "End" : "Latest") : "Only fix"; target.append(currentLabel);
    message.textContent = points.length === 1 ? "One GPS fix; a trace requires additional fixes." : `${points.length} GPS fixes shown in recorded order.${noFixCount ? ` ${noFixCount} no-fix record${noFixCount === 1 ? "" : "s"} omitted from the trace.` : ""}`;
  }

  function persistedEvents() {
    if (!state.sessionData) return [];
    const events = [{ type: "info", timestamp: state.sessionData.started_at, message: "Transport session started" }];
    state.sessionData.records.forEach((record) => {
      if (record.gps) events.push({ type: record.gps.status === "fix" ? "info" : "warning", timestamp: record.gps.timestamp, message: record.gps.status === "fix" ? "GPS fix recorded" : "GPS no-fix recorded" });
      ["immediate_violations", "prolonged_violations"].forEach((kind) => record[kind].forEach((item) => events.push({ type: "violation", timestamp: item.occurred_at, message: `${item.condition.replaceAll("_", " ")}: ${item.observed_value} ${item.unit}`, detail: `${kind === "immediate_violations" ? "Immediate" : "Prolonged"} threshold ${item.threshold_value} ${item.unit}` })));
    });
    if (state.sessionData.ended_at) events.push({ type: "info", timestamp: state.sessionData.ended_at, message: "Transport session completed" });
    return events;
  }

  function renderEvents() {
    const list = byId("event-list"), empty = byId("events-empty");
    list.replaceChildren();
    const seen = new Set();
    const events = [...persistedEvents(), ...state.liveEvents].filter((event) => {
      const key = [event.type, event.timestamp || "", event.message].join("|");
      if (seen.has(key)) return false;
      seen.add(key); return true;
    }).sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || ""))).slice(0, 30);
    events.forEach((event) => {
      const item = document.createElement("li"); item.className = `event-item is-${event.type}`;
      const time = document.createElement("span"); time.className = "event-time"; time.textContent = timestampText(event.timestamp);
      const marker = document.createElement("span"); marker.className = "event-marker";
      const text = document.createElement("div"); const title = document.createElement("p"); title.textContent = event.message; text.append(title);
      if (event.detail) { const detail = document.createElement("p"); detail.className = "event-detail"; detail.textContent = event.detail; text.append(detail); }
      item.append(time, marker, text); list.append(item);
    });
    empty.classList.toggle("is-hidden", events.length > 0);
  }

  function readableCapability(name, capability) {
    const labels = { sensors: "Sensors", gps: "GPS", artwork: "Artwork", storage: "Storage", realtime: "Realtime" };
    const validation = capability.physical_validation === "not_validated" ? "not physically validated" : capability.physical_validation === "validated" ? "physically validated" : "physical validation not applicable";
    return { label: labels[name], detail: `${capability.state} · ${validation}` };
  }

  function renderCapabilities() {
    const list = byId("capability-list"); list.replaceChildren();
    if (!state.capabilities) { list.append(Object.assign(document.createElement("p"), { className: "panel-empty", textContent: "Capability status unavailable." })); return; }
    Object.entries(state.capabilities).forEach(([name, capability]) => {
      const item = document.createElement("div"); item.className = "capability-item";
      const title = document.createElement("span"); title.className = "capability-name";
      const detail = document.createElement("span"); detail.className = `capability-state is-${capability.state}`;
      const readable = readableCapability(name, capability); title.textContent = readable.label; detail.textContent = readable.detail;
      item.append(title, detail); list.append(item);
    });
  }

  function renderArtwork() {
    const artwork = state.snapshot && state.snapshot.artwork;
    setText("artwork-summary", artwork ? (artwork.checking ? "Checking active" : "Checking idle") : "Unavailable");
    setText("artwork-checking", artwork ? (artwork.checking ? "Workflow is active; statuses remain neutral IN / OUT states." : "Workflow is idle; state is retained in memory only.") : "Artwork workflow status unavailable.");
    const list = byId("artwork-list"), empty = byId("artwork-empty"); list.replaceChildren();
    const items = artwork && artwork.artworks ? artwork.artworks : [];
    items.forEach((item) => {
      const row = document.createElement("li"); row.className = "artwork-item";
      const name = document.createElement("span"); name.textContent = `${item.lot} · ${item.name}`;
      const status = document.createElement("span"); status.className = `artwork-status is-${item.status}`; status.textContent = item.status;
      row.append(name, status); list.append(row);
    });
    empty.classList.toggle("is-hidden", items.length > 0);
  }

  function renderReport() {
    const link = byId("report-link");
    const completed = state.sessionData && state.sessionData.ended_at;
    const url = state.reportUrl || (completed ? `/report?session_id=${encodeURIComponent(state.selectedSessionId)}` : null);
    link.classList.toggle("is-disabled", !url); link.setAttribute("aria-disabled", String(!url)); link.href = url || "/report";
    setText("report-message", !state.selectedSessionId ? "Select or start a session to access its report." : completed ? "This link opens only the selected session’s existing report." : "Report available after this session is completed.");
  }

  function render() { renderBanner(); renderHeader(); renderSessionPicker(); renderMetrics(); renderHistory(); renderRoute(); renderEvents(); renderCapabilities(); renderArtwork(); renderReport(); }

  async function loadCapabilities() {
    try {
      const response = await fetch("/api/dashboard/capabilities");
      if (!response.ok) throw new Error("Capability status could not be loaded.");
      state.capabilities = (await response.json()).components;
      state.error = "";
    } catch (error) { state.error = error.message; }
    render();
  }

  async function loadSession(sessionId) {
    state.selectedSessionId = sessionId;
    state.sessionData = null;
    state.reportUrl = null;
    state.error = "";
    render();
    if (!sessionId) return;
    const requestNumber = ++state.requestNumber;
    try {
      const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/dashboard-data`);
      if (!response.ok) throw new Error(response.status === 404 ? "The selected session is unavailable." : "Session data could not be loaded.");
      const data = await response.json();
      if (requestNumber !== state.requestNumber || state.selectedSessionId !== sessionId) return;
      state.sessionData = data;
    } catch (error) { if (requestNumber === state.requestNumber) state.error = error.message; }
    render();
  }

  function acceptSnapshot(snapshot) {
    state.snapshot = snapshot;
    if (snapshot.capabilities) state.capabilities = snapshot.capabilities.components;
    const activeSession = snapshot.transport && snapshot.transport.session_id;
    const known = snapshot.session_ids || [];
    const preferred = activeSession || (state.selectedSessionId && known.includes(state.selectedSessionId) ? state.selectedSessionId : known[0] || "");
    render();
    loadSession(preferred);
  }

  function appendLiveCycle(payload) {
    if (!state.sessionData || payload.session_id !== state.selectedSessionId) return false;
    state.sessionData.records.push({ sequence: state.sessionData.records.length, reading: payload.reading, gps: null, immediate_violations: [], prolonged_violations: [] });
    return true;
  }

  function attachGps(payload) {
    if (!state.sessionData || payload.session_id !== state.selectedSessionId) return false;
    const record = [...state.sessionData.records].reverse().find((item) => item.reading.timestamp === payload.timestamp && !item.gps);
    if (!record) return false;
    record.gps = { timestamp: payload.timestamp, status: "fix", latitude: payload.latitude, longitude: payload.longitude };
    return true;
  }

  function attachViolation(payload) {
    if (!state.sessionData || payload.session_id !== state.selectedSessionId) return;
    const record = [...state.sessionData.records].reverse().find((item) => item.reading.timestamp === payload.occurred_at);
    if (record) record[`${payload.kind}_violations`].push(payload);
  }

  function connectRealtime() {
    if (typeof window.io !== "function") { setSocketState("disconnected"); state.error = "Realtime client is unavailable."; render(); return; }
    const socket = window.io(); window.artworkMonitorSocket = socket;
    socket.on("connect", () => { setSocketState("connected"); loadCapabilities(); });
    socket.on("disconnect", () => setSocketState("disconnected"));
    socket.on("connect_error", () => setSocketState("disconnected"));
    socket.on("state_snapshot", acceptSnapshot);
    socket.on("transport_started", (payload) => {
      state.snapshot = state.snapshot || { artwork: { artworks: [], checking: false }, session_ids: [] };
      state.snapshot.transport = { state: payload.state, session_id: payload.session_id };
      if (!state.snapshot.session_ids.includes(payload.session_id)) state.snapshot.session_ids.unshift(payload.session_id);
      loadSession(payload.session_id);
    });
    socket.on("transport_cycle", (payload) => {
      if (!appendLiveCycle(payload) && payload.session_id === state.selectedSessionId) loadSession(payload.session_id);
      else render();
    });
    socket.on("gps_update", (payload) => {
      if (!attachGps(payload) && payload.session_id === state.selectedSessionId) loadSession(payload.session_id);
      addEvent({ type: "info", timestamp: payload.timestamp, message: "GPS fix recorded" }); render();
    });
    socket.on("violation", (payload) => { attachViolation(payload); addEvent({ type: "violation", timestamp: payload.occurred_at, message: `${payload.condition.replaceAll("_", " ")}: ${payload.observed_value} ${payload.unit}`, detail: `${payload.kind} threshold ${payload.threshold_value} ${payload.unit}` }); render(); });
    socket.on("transport_completed", (payload) => { if (state.snapshot) state.snapshot.transport = { state: payload.state, session_id: payload.session_id }; if (payload.session_id === state.selectedSessionId) loadSession(payload.session_id); else render(); });
    socket.on("report_ready", (payload) => { if (payload.session_id === state.selectedSessionId) state.reportUrl = payload.report_url; render(); });
    socket.on("artwork_check_started", updateArtwork);
    socket.on("artwork_check_stopped", updateArtwork);
    socket.on("artwork_status_changed", (payload) => { updateArtwork(payload); if (payload.transition) addEvent({ type: "info", timestamp: payload.transition.occurred_at, message: `Artwork status changed to ${payload.transition.status}` }); });
  }

  function updateArtwork(payload) {
    state.snapshot = state.snapshot || { transport: { state: "not_started", session_id: null }, session_ids: [] };
    const previous = state.snapshot.artwork || {};
    state.snapshot.artwork = {
      checking: payload.checking === undefined ? previous.checking : payload.checking,
      artworks: payload.artworks || previous.artworks || [],
    };
    render();
  }

  document.addEventListener("DOMContentLoaded", () => {
    byId("session-select").addEventListener("change", (event) => loadSession(event.target.value));
    render();
    loadCapabilities();
    connectRealtime();
  });
})();
