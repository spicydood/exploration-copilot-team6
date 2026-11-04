/* Exploration Copilot — map module. Owns EC.map and the EC.S.attr slice.
   Attribute tabs, the canvas overlay (grid, outlines, wells, pins, guides), DOM labels over the
   canvas, hover and keyboard access, the readout, the survey locator and the hidden text twins.
   Every colour comes from a CSS token via EC.util.css; the CMAPS ramps are data (legend only). */
(() => {
  "use strict";
  const EC = (window.EC = window.EC || {});
  const ATTRS = [["sand", "Sand probability"], ["vpvs", "Vp/Vs"], ["avo_diff", "Far − Near"], ["pimp", "P-impedance"], ["top_time", "Structure"], ["disc", "Faults"]];
  const CMAPS = {  // CSS gradients approximating the matplotlib colormaps used for the map PNGs
    inferno: "linear-gradient(90deg,#000004,#56106e,#bb3754,#f98e09,#fcffa4)",
    viridis_r: "linear-gradient(90deg,#fde725,#35b779,#31688e,#440154)",
    cividis_r: "linear-gradient(90deg,#fee838,#a59c74,#575c6d,#00224e)",
    RdBu_r: "linear-gradient(90deg,#2166ac,#92c5de,#f7f7f7,#f4a582,#b2182b)",
    magma: "linear-gradient(90deg,#000004,#51127c,#b73779,#fc8961,#fcfdbf)",
    Greys: "linear-gradient(90deg,#ffffff,#969696,#000000)",
    terrain: "linear-gradient(90deg,#333399,#00b2b2,#99e57f,#d2bb85,#ffffff)",
  };
  const TRAP = { Structural: "--color-trap-structural", Stratigraphic: "--color-trap-stratigraphic", Combination: "--color-trap-combination" };
  const BAR_PX = 64, GRID_STEP = 8, CROSS = 3, WELL_R = 6, STEP = 5;
  const ALPHA = { base: 0.14, hover: 0.3, sel: 0.4 };
  const st = { hover: null, pin: null, cursor: null, link: null, query: null, querySel: null, g: null, sub: "" };
  const els = {};
  let $, esc, fmt, css, icon, plural;

  // ------------------------------------------------------------------ helpers
  const S = () => EC.S;
  const trapVar = (d) => TRAP[d.trap_type] || "--color-trap-unclassified";
  const hiddenWell = () => S().blind?.well || null;
  const minus = (s) => String(s).replace(/^-/, "−");
  const attrLabel = (k) => (ATTRS.find((a) => a[0] === k) || [])[1] || String(S().meta?.maps?.[k]?.label || k).replace(/\s*\(.*\)$/, "");
  const il = (i) => S().meta.il_values?.[Math.round(i)] ?? S().meta.ilines[0] + Math.round(i);
  const xl = (j) => S().meta.xl_values?.[Math.round(j)] ?? S().meta.xlines[0] + Math.round(j);
  const ilxl = (p) => `IL ${esc(il(p[0]))} · XL ${esc(xl(p[1]))}`;
  const money = (v) => `${v < 0 ? "−" : "+"}$${fmt(Math.abs(v), 1)}M`;
  const lead = (id) => S().leads.find((d) => d.id === id);
  const well = (name) => S().wells.find((w) => w.name === name);
  const wellPoint = (w) => (w && w.i != null ? [w.i, w.j] : null);
  const unitText = (u) => (u === "km2" ? "km²" : u || "");
  function inPoly(i, j, poly) {
    let inside = false;
    for (let a = 0, b = poly.length - 1; a < poly.length; b = a++) {
      const [ia, ja] = poly[a], [ib, jb] = poly[b];
      if ((ia > i) !== (ib > i) && j < ((jb - ja) * (i - ia)) / (ib - ia) + ja) inside = !inside;
    }
    return inside;
  }
  const leadAt = (i, j) => S().leads.find((d) => inPoly(i, j, d.polygon)) || null;

  // ------------------------------------------------------------------ geometry: bin (i, j) → stage px, matching object-fit: cover
  function geom() {
    const m = S().meta, stage = els.stage, c = els.canvas;
    if (!m || !stage || !c) return null;
    const W = stage.clientWidth, H = stage.clientHeight;
    if (!W || !H) return null;
    const [ni, nj] = m.shape, s = Math.max(W / nj, H / ni), dpr = window.devicePixelRatio || 1;
    const pw = Math.round(W * dpr), ph = Math.round(H * dpr);
    if (c.width !== pw || c.height !== ph) { c.width = pw; c.height = ph; }
    const ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return (st.g = { W, H, s, ox: (W - nj * s) / 2, oy: (H - ni * s) / 2, ni, nj, ctx, bin: m.bin_area_m2 ? Math.sqrt(m.bin_area_m2) : null });
  }
  const P = (g, i, j) => [g.ox + (j + 0.5) * g.s, g.oy + (i + 0.5) * g.s];
  const toBin = (g, x, y) => [(y - g.oy) / g.s - 0.5, (x - g.ox) / g.s - 0.5];
  const mToPx = (g, metres) => (g.bin ? (metres / g.bin) * g.s : 0);

  // ------------------------------------------------------------------ canvas
  function draw() {
    const g = geom(); if (!g) return;
    const { ctx, W, H } = g;
    ctx.clearRect(0, 0, W, H);
    drawGrid(g); drawLeads(g); drawLink(g); drawWells(g); drawGuides(g);
    renderLabels(g); scaleText(g); describe();
  }
  function drawGrid(g) {
    const { ctx } = g;
    ctx.strokeStyle = css("--color-instrument-grid"); ctx.lineWidth = 1; ctx.setLineDash([]);
    ctx.beginPath();
    for (let i = 0; i < g.ni; i += GRID_STEP) for (let j = 0; j < g.nj; j += GRID_STEP) {
      const [x, y] = P(g, i, j); const px = Math.round(x) + 0.5, py = Math.round(y) + 0.5;
      ctx.moveTo(px - CROSS, py); ctx.lineTo(px + CROSS + 1, py); ctx.moveTo(px, py - CROSS); ctx.lineTo(px, py + CROSS + 1);
    }
    ctx.stroke();
  }
  function tracePoly(g, poly) {
    g.ctx.beginPath();
    poly.forEach(([i, j], n) => { const [x, y] = P(g, i, j); n ? g.ctx.lineTo(x, y) : g.ctx.moveTo(x, y); });
    g.ctx.closePath();
  }
  function drawLeads(g) {
    const { ctx } = g;
    for (const d of S().leads) {
      const col = css(trapVar(d)), sel = S().sel === d.id, hi = st.pin?.lead === d.id, hov = st.hover?.lead === d.id;
      tracePoly(g, d.polygon);
      ctx.globalAlpha = sel || hi ? ALPHA.sel : hov ? ALPHA.hover : ALPHA.base; ctx.fillStyle = col; ctx.fill(); ctx.globalAlpha = 1;
      ctx.lineJoin = "round"; ctx.setLineDash([]);
      const w = sel ? 3 : 2;
      ctx.lineWidth = w + 2; ctx.strokeStyle = css("--map-halo"); ctx.stroke();
      ctx.lineWidth = w; ctx.strokeStyle = col; ctx.setLineDash(d.drilled ? [] : [8, 5]); ctx.stroke(); ctx.setLineDash([]);
      if (sel && g.bin) {  // equivalent-radius ring: the diameter carries the area
        const [cx, cy] = P(g, d.centroid[0], d.centroid[1]);
        const r = mToPx(g, Math.sqrt((d.area_km2 * 1e6) / Math.PI));
        ctx.strokeStyle = css("--color-instrument-ring"); ctx.lineWidth = 1.5; ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = css("--color-instrument-ring"); ctx.beginPath(); ctx.arc(cx, cy, 2.5, 0, Math.PI * 2); ctx.fill();
      }
    }
  }
  function drawLink(g) {
    const a = st.link && lead(st.link.from), b = st.link && lead(st.link.to);
    if (!a || !b) return;
    const { ctx } = g, [x1, y1] = P(g, a.centroid[0], a.centroid[1]), [x2, y2] = P(g, b.centroid[0], b.centroid[1]);
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
    ctx.lineWidth = 4; ctx.strokeStyle = css("--map-halo"); ctx.setLineDash([]); ctx.stroke();
    ctx.lineWidth = 2; ctx.strokeStyle = css("--color-instrument-measure"); ctx.setLineDash([6, 4]); ctx.stroke(); ctx.setLineDash([]);
  }
  function drawWells(g) {
    const { ctx } = g, hidden = hiddenWell();
    for (const w of S().wells) {
      if (w.i == null) continue;
      const [wx, wy] = P(g, w.i, w.j), hid = w.name === hidden;
      const x = Math.min(Math.max(wx, 8), g.W - 120), y = Math.min(Math.max(wy, 92), g.H - 40);
      const r = st.hover?.well === w.name || S().selWell === w.name ? WELL_R + 2 : WELL_R;
      ctx.setLineDash([]); ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = !hid && w.result === "discovery" ? css("--color-status-discovery") : css("--map-halo"); ctx.fill();
      ctx.strokeStyle = hid ? css("--color-accent-solid") : css("--map-ink"); ctx.stroke();
      if (!hid && w.result === "dry") {
        ctx.strokeStyle = css("--color-status-dry"); const k = r + 2;
        ctx.beginPath(); ctx.moveTo(x - k, y - k); ctx.lineTo(x + k, y + k); ctx.moveTo(x + k, y - k); ctx.lineTo(x - k, y + k); ctx.stroke();
      }
    }
  }
  function guides(g, x, y, dash) {
    const { ctx } = g; ctx.strokeStyle = css("--color-instrument-guide"); ctx.lineWidth = 1; ctx.setLineDash(dash);
    const px = Math.round(x) + 0.5, py = Math.round(y) + 0.5;
    ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(g.W, py); ctx.moveTo(px, 0); ctx.lineTo(px, g.H); ctx.stroke(); ctx.setLineDash([]);
  }
  function drawGuides(g) {
    const { ctx } = g;
    if (st.cursor) { const [x, y] = P(g, st.cursor.i, st.cursor.j); guides(g, x, y, [3, 3]); }
    if (st.pin?.point) {
      const [x, y] = P(g, st.pin.point[0], st.pin.point[1]); guides(g, x, y, []);
      ctx.beginPath(); ctx.moveTo(x, y - 8); ctx.lineTo(x + 8, y); ctx.lineTo(x, y + 8); ctx.lineTo(x - 8, y); ctx.closePath();
      ctx.fillStyle = css("--color-accent-solid"); ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = css("--map-ink"); ctx.setLineDash([]); ctx.stroke();
    }
  }

  // ------------------------------------------------------------------ DOM labels (real buttons, so the keyboard reaches them)
  function renderLabels(g) {
    g = g || st.g; if (!els.labels || !g) return;
    const exec = S().audience === "executive", { cost, value } = S().assumptions || {}, hidden = hiddenWell();
    const parts = [];
    for (const d of S().leads) {
      const [x0, y0] = P(g, d.centroid[0], d.centroid[1]);
      // keep the label inside the stage and below the title/tab band (88 px), so it never covers the chrome
      const x = Math.min(Math.max(x0, 96), g.W - 96), y = Math.min(Math.max(y0, 92), g.H - 104);
      let row2;
      if (exec) {
        row2 = `<span class="num-sm faint">odds</span><span class="num-sm acc">${esc(Math.round(d.gcos * 100))} %</span>`;
        if (typeof cost === "number" && typeof value === "number") {
          const emv = d.gcos * value - (1 - d.gcos) * cost;
          row2 = `<span class="num-sm faint">EMV</span><span class="num-sm ${emv < 0 ? "res-dry" : "res-discovery"}">${esc(money(emv))}</span>` + row2;
        }
      } else {
        row2 = `<span class="num-sm faint">GCoS</span><span class="num-sm acc">${esc(fmt(d.gcos, 3))}</span><span class="num-sm">${esc(fmt(d.area_km2, 2))} km²</span>`;
      }
      parts.push(`<button type="button" class="lead-label t-${esc(d.trap_type)}${S().sel === d.id ? " is-sel" : ""}" style="--c:var(${trapVar(d)});left:${x}px;top:${y}px" data-lead="${esc(d.id)}" aria-pressed="${S().sel === d.id}"><span class="l1"><span class="num">${esc(d.id)}</span><span class="tt">${esc(d.trap_type)}</span></span><span class="l2">${row2}</span></button>`);
    }
    for (const w of S().wells) {
      if (w.i == null) continue;
      const [wx, wy] = P(g, w.i, w.j), hid = w.name === hidden;
      const x = Math.min(Math.max(wx, 8), g.W - 120), y = Math.min(Math.max(wy, 92), g.H - 40);
      parts.push(`<button type="button" class="well-label num-sm${hid ? " is-hidden-well" : ""}" style="left:${x}px;top:${y}px" data-well="${esc(w.name)}">${esc(w.name)}${hid ? " · hidden" : ""}</button>`);
    }
    const a = st.link && lead(st.link.from), b = st.link && lead(st.link.to);
    if (a && b) {
      const [x1, y1] = P(g, a.centroid[0], a.centroid[1]), [x2, y2] = P(g, b.centroid[0], b.centroid[1]);
      const text = st.link.sim == null ? "analog" : `${esc(fmt(st.link.sim, 2))} match`;
      parts.push(`<span class="analog-badge num-sm" style="left:${(x1 + x2) / 2}px;top:${(y1 + y2) / 2}px">${icon("layers")}${text}</span>`);
    }
    if (st.query) {
      const [x, y] = P(g, st.query[0], st.query[1]);
      parts.push(`<span class="query-chip num-sm" style="left:${x}px;top:${y}px">${icon("triangle-alert")}${ilxl(st.query)} · no lead</span>`);
    }
    els.labels.innerHTML = parts.join("");
    contents();
  }
  function contents() {
    const c = els.contents; if (!c) return;
    const hidden = hiddenWell(), items = [];
    for (const d of S().leads) items.push(`<li><button type="button" data-lead="${esc(d.id)}">${esc(d.id)}, ${esc(d.trap_type.toLowerCase())}, ${d.drilled ? "drilled" : "undrilled"}, GCoS ${esc(fmt(d.gcos, 3))}</button></li>`);
    for (const w of S().wells) {
      if (w.i == null) continue;
      const res = w.name === hidden ? "result hidden for the blind test" : w.result || "result unknown";
      items.push(`<li><button type="button" data-well="${esc(w.name)}">${esc(w.name)}, ${esc(res)}</button></li>`);
    }
    c.innerHTML = `<p class="label">Map contents</p><ul>${items.join("")}</ul>`;
  }
  function describe() {
    const p = els.desc, m = S().meta; if (!p || !m) return;
    const sel = S().sel ? `${S().sel} is selected` : "no lead is selected";
    p.textContent = `Opportunity map showing ${attrLabel(S().attr)} over the survey, ${plural(S().leads.length, "lead outline", "lead outlines")} and ${plural(S().wells.length, "well", "wells")}; ${sel}.`;
  }
  function onLabelClick(e) {
    const b = e.target.closest("[data-lead], [data-well]"); if (!b) return;
    if (b.dataset.lead) EC.app?.selectLead(b.dataset.lead); else EC.app?.selectWell(b.dataset.well);
  }

  // ------------------------------------------------------------------ attribute tabs, legend, scale, image
  function buildTabs() {
    const bar = els.bar; if (!bar) return;
    bar.innerHTML = "";
    for (const [k, label] of ATTRS) {
      if (!S().meta?.maps?.[k]) continue;
      const b = document.createElement("button");
      b.type = "button"; b.setAttribute("role", "tab"); b.setAttribute("aria-selected", "false"); b.tabIndex = -1;
      b.dataset.attr = k; b.textContent = label;
      b.addEventListener("click", () => setAttr(k));
      bar.append(b);
    }
    bar.addEventListener("keydown", (e) => {
      const tabs = [...bar.children]; if (!tabs.length) return;
      const i = tabs.findIndex((t) => t.dataset.attr === S().attr);
      let n = null;
      if (e.key === "ArrowRight") n = tabs[(i + 1) % tabs.length];
      else if (e.key === "ArrowLeft") n = tabs[(i - 1 + tabs.length) % tabs.length];
      else if (e.key === "Home") n = tabs[0];
      else if (e.key === "End") n = tabs[tabs.length - 1];
      if (!n) return;
      e.preventDefault(); setAttr(n.dataset.attr); n.focus();
    });
  }
  function setAttr(k) {
    const m = S().meta?.maps?.[k]; if (!m) return;
    S().attr = k;
    for (const b of els.bar?.children || []) { const on = b.dataset.attr === k; b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1; }
    if (els.img) els.img.src = EC.api.mapUrl(k);
    legend(k); readout(); describe();
    EC.bus.emit("attr", k);
  }
  function legend(k) {
    const el = els.legend, m = S().meta.maps[k]; if (!el || !m) return;
    const sw = [["Structural", "--color-trap-structural"], ["Stratigraphic", "--color-trap-stratigraphic"], ["Combination", "--color-trap-combination"], ["Fault", "--color-status-dry"]];
    let html = sw.map(([n, v]) => `<span><span class="sw" style="--c:var(${v})"></span>${n}</span>`).join("");
    if (k !== "sand") {
      const unit = m.unit && m.unit !== "0-1" ? ` ${unitText(m.unit)}` : "";
      html += `<span>${esc(attrLabel(k))}</span><span class="ramp" style="background:${CMAPS[m.cmap] || CMAPS.inferno}"></span><span class="num-sm">${esc(minus(fmt(m.vmin)))} → ${esc(minus(fmt(m.vmax)))}${esc(unit)}</span>`;
    }
    el.innerHTML = html;
  }
  function scaleText(g) {
    const t = els.scaleText; if (!t || !g || !g.bin) return;
    const metres = (BAR_PX * g.bin) / g.s;
    t.textContent = metres >= 1000 ? `${fmt(metres / 1000, 1)} km` : `${Math.round(metres)} m`;
  }
  function imageFailed() { if (els.sub) els.sub.textContent = "Map image didn't load. Reload to retry."; }
  function imageLoaded() { if (els.sub && st.sub && els.sub.textContent !== st.sub) els.sub.textContent = st.sub; }

  // ------------------------------------------------------------------ pin, readout, cursor, link
  function highlight(item) {
    if (!item) { st.pin = null; readout(); draw(); return; }
    const ref = item.ref || item;
    const d = ref.lead ? lead(ref.lead) : null, w = ref.well ? well(ref.well) : null;
    const point = ref.point || (d ? d.centroid : null) || wellPoint(w);
    if (ref.map && ref.map !== S().attr && S().meta?.maps?.[ref.map]) setAttr(ref.map);
    st.pin = point ? { id: item.id || "", label: item.label || "", value: item.value, unit: item.unit || "", lead: ref.lead || null, well: ref.well || null, map: ref.map || null, point, fromPoint: !!ref.point } : null;
    readout(); draw();
  }
  function readout() {
    const r = els.readout; if (!r) return;
    const pin = st.pin, cur = st.cursor;
    if (!pin && !cur) { r.hidden = true; r.innerHTML = ""; return; }
    let html;
    if (pin) {
      const where = pin.lead ? (pin.fromPoint ? pin.lead : `${pin.lead} centroid`) : pin.well || "point";
      html = `<span class="label">Pinned${pin.id ? ` · ${esc(pin.id)}` : ""} · ${esc(where)}</span>`;
      if (pin.point) {
        html += `<span class="num">${ilxl(pin.point)}</span>`;
        const lines = [];
        const isNum = typeof pin.value === "number";
        if (isNum || (typeof pin.value === "string" && pin.value && pin.value !== "none")) {
          const name = pin.map ? attrLabel(pin.map) : pin.label;
          lines.push(`${esc(name)} ${esc(isNum ? minus(fmt(pin.value, 3)) : pin.value)}${pin.unit ? " " + esc(unitText(pin.unit)) : ""}`);
        }
        const dl = S().detail?.lead, crest = dl && dl.id === pin.lead ? dl.structure?.crest_time_ms : null;
        if (typeof crest === "number") lines.push(`crest ${esc(crest.toLocaleString("en-MY", { minimumFractionDigits: 1, maximumFractionDigits: 1 }))} ms`);
        if (lines.length) html += `<span class="num-sm secondary">${lines.join(" · ")}</span>`;
      }
    } else {
      const d = leadAt(cur.i, cur.j), who = d ? `${esc(d.id)} · ${esc(d.trap_type)}` : "no lead here";
      html = `<span class="label">Cursor</span><span class="num">${ilxl([cur.i, cur.j])}</span><span class="num-sm secondary">${who}</span>`;
    }
    r.innerHTML = html; r.hidden = false;
  }
  function focusPoint(i, j) {
    const m = S().meta; if (!m) return;
    st.cursor = { i: Math.min(m.shape[0] - 1, Math.max(0, Math.round(i))), j: Math.min(m.shape[1] - 1, Math.max(0, Math.round(j))) };
    readout(); draw();
  }
  function link(from, to, sim) {
    st.link = from && to ? { from, to, sim: typeof sim === "number" ? sim : null, sel: S().sel } : null;
    draw();
  }

  // ------------------------------------------------------------------ hover, click, keyboard on the canvas
  function hit(ev) {
    const g = st.g || geom(); if (!g) return null;
    const r = els.canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
    for (const w of S().wells) {
      if (w.i == null) continue;
      const [wx, wy] = P(g, w.i, w.j);
      if (Math.hypot(wx - x, wy - y) < WELL_R + 4) return { well: w.name, x, y };
    }
    const [i, j] = toBin(g, x, y), d = leadAt(i, j);
    return d ? { lead: d.id, x, y } : null;
  }
  function onMove(ev) {
    const h = hit(ev), tip = els.tip;
    const key = h ? h.lead || h.well : null, prev = st.hover ? st.hover.lead || st.hover.well : null;
    if (key !== prev) { st.hover = h; draw(); }
    if (!tip) return;
    if (!h) { tip.hidden = true; return; }
    if (h.lead) {
      const d = lead(h.lead);
      tip.innerHTML = `<b>${esc(d.id)}</b> · ${esc(d.trap_type)}<br>${esc(d.subtype || "")}<br>GCoS ${esc(fmt(d.gcos, 3))} · ${esc(fmt(d.area_km2, 2))} km² · ${d.drilled ? "drilled" : "undrilled"}`;
    } else {
      const w = well(h.well), hid = w.name === hiddenWell();
      const res = hid ? "result hidden for the blind test" : w.result_text || w.result || "result unknown";
      tip.innerHTML = `<b>${esc(w.name)}</b><br>${esc(res)}<br>IL ${esc(w.inline)} · XL ${esc(w.crossline)}`;
    }
    const g = st.g; tip.style.left = `${Math.min(h.x, g.W - 252)}px`; tip.style.top = `${Math.min(h.y, g.H - 72)}px`; tip.hidden = false;
  }
  function onLeave() { if (els.tip) els.tip.hidden = true; if (st.hover) { st.hover = null; draw(); } }
  function onClick(ev) {
    const h = hit(ev); if (!h) return;
    if (h.lead) EC.app?.selectLead(h.lead); else EC.app?.selectWell(h.well);
  }
  function onKey(e) {
    const m = S().meta; if (!m) return;
    const moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    if (moves[e.key]) {
      e.preventDefault();
      if (!st.cursor) {
        const d = S().sel && lead(S().sel), p = d ? d.centroid : [m.shape[0] / 2, m.shape[1] / 2];
        focusPoint(p[0], p[1]); return;
      }
      const k = e.shiftKey ? 1 : STEP;
      focusPoint(st.cursor.i + moves[e.key][0] * k, st.cursor.j + moves[e.key][1] * k);
    } else if ((e.key === "Enter" || e.key === " ") && st.cursor) {
      e.preventDefault();
      const d = leadAt(st.cursor.i, st.cursor.j);
      if (d) EC.app?.selectLead(d.id);
    } else if (e.key === "Escape" && st.cursor) {
      st.cursor = null; readout(); draw();
    }
  }

  // ------------------------------------------------------------------ survey locator (blind test)
  function locator() {
    const el = els.locator, m = S().meta; if (!el) return;
    const hidden = hiddenWell();
    if (!hidden || !m) { el.hidden = true; el.innerHTML = ""; return; }
    const [ni, nj] = m.shape, X0 = 16, Y0 = 18, LW = 200, LH = 160, sx = LW / nj, sy = LH / ni;
    const px = (i, j) => [X0 + (j + 0.5) * sx, Y0 + (i + 0.5) * sy];
    const grid = css("--color-instrument-grid"), guide = css("--color-instrument-guide"), measure = css("--color-instrument-measure");
    let s = `<svg viewBox="0 0 232 196" width="232" height="196" role="img" aria-label="Survey locator: ${esc(plural(S().wells.length, "well", "wells"))}, ${esc(hidden)} hidden"><rect x="${X0}" y="${Y0}" width="${LW}" height="${LH}" fill="none" stroke="${esc(guide)}"/>`;
    for (let k = 1; k < 4; k++) {
      const gx = X0 + (LW * k) / 4, gy = Y0 + (LH * k) / 4;
      s += `<line x1="${gx}" y1="${Y0}" x2="${gx}" y2="${Y0 + LH}" stroke="${esc(grid)}"/><line x1="${X0}" y1="${gy}" x2="${X0 + LW}" y2="${gy}" stroke="${esc(grid)}"/>`;
    }
    const sec = S().detail?.section_inline;
    if (typeof sec === "number") { const y = Y0 + (sec - m.ilines[0] + 0.5) * sy; s += `<line x1="${X0}" y1="${y}" x2="${X0 + LW}" y2="${y}" stroke="${esc(measure)}" stroke-width="1.5"/>`; }
    for (const d of S().leads) {
      if (d.drilled) continue;
      const [x, y] = px(d.centroid[0], d.centroid[1]);
      s += `<circle cx="${x}" cy="${y}" r="4.5" fill="none" stroke="${esc(css("--color-accent-solid"))}" stroke-width="1.5"><title>${esc(d.id)}, undrilled</title></circle>`;
    }
    for (const w of S().wells) {
      if (w.i == null) continue;
      const [x, y] = px(w.i, w.j), hid = w.name === hidden;
      const col = hid ? css("--color-accent-solid") : w.result === "discovery" ? css("--color-status-discovery") : w.result === "dry" ? css("--color-status-dry") : css("--color-status-unknown");
      s += `<circle cx="${x}" cy="${y}" r="3" fill="${hid ? "none" : esc(col)}" stroke="${esc(col)}" stroke-width="1.5"><title>${esc(w.name)}${hid ? ", hidden" : ""}</title></circle>`;
    }
    const txt = `font-family:var(--f-data);font-size:12px;fill:var(--color-text-on-scrim-secondary)`;
    s += `<text x="${X0}" y="12" style="${txt}">IL ${esc(m.ilines[0])} · XL ${esc(m.xlines[0])}</text><text x="${X0 + LW}" y="192" text-anchor="end" style="${txt}">IL ${esc(m.ilines[1])} · XL ${esc(m.xlines[1])}</text></svg>`;
    el.innerHTML = s; el.hidden = false;
  }

  // ------------------------------------------------------------------ bus
  function onFact(item) {
    // an evidence item arrived in the stream: only the "no lead here" query point is worth drawing unasked
    if (item && item.ref?.point && /^lead at/i.test(item.label || "") && item.value === "none") { st.query = item.ref.point; st.querySel = S().sel; draw(); }
  }
  function onEvidence(item) { highlight(item); }
  function onLead(p) {
    if (st.link && p.id !== st.link.sel) st.link = null;
    if (st.query && p.id !== st.querySel) st.query = null;
    if (st.pin && st.pin.lead && p.id !== st.pin.lead) { st.pin = null; readout(); }
    draw(); locator();
  }

  // ------------------------------------------------------------------ init
  function init() {
    ({ $, esc, fmt, css, icon, plural } = EC.util);
    Object.assign(els, { stage: $("map-stage"), canvas: $("map"), img: $("map-img"), bar: $("attr-bar"), labels: $("map-labels"), readout: $("readout"), locator: $("locator"), legend: $("legend"), scaleText: $("scale-text"), tip: $("map-tip"), desc: $("map-desc"), contents: $("map-contents"), sub: $("map-sub") });
    if (!els.stage || !els.canvas || !S().meta) return;
    st.sub = els.sub?.textContent || "";
    buildTabs();
    els.img?.addEventListener("error", imageFailed);
    els.img?.addEventListener("load", imageLoaded);
    els.canvas.addEventListener("mousemove", onMove);
    els.canvas.addEventListener("mouseleave", onLeave);
    els.canvas.addEventListener("click", onClick);
    els.canvas.addEventListener("keydown", onKey);
    els.labels?.addEventListener("click", onLabelClick);
    els.contents?.addEventListener("click", onLabelClick);
    if (window.ResizeObserver) new ResizeObserver(() => draw()).observe(els.stage);
    else window.addEventListener("resize", draw);
    EC.bus.on("lead", onLead);
    EC.bus.on("well", () => draw());
    EC.bus.on("blind", () => { draw(); locator(); });
    EC.bus.on("audience", (aud) => {
      // D7: in Executive mode the map is a value view; the attribute tabs go and the subtitle says what the labels show
      if (els.bar) els.bar.hidden = aud === "executive";
      if (els.sub) els.sub.textContent = aud === "executive" ? "value view · labels show odds and expected value" : st.sub;
      draw();
    });
    EC.bus.on("evidence", onEvidence);
    EC.bus.on("fact", onFact);
    EC.bus.on("imagefail", imageFailed);
    setAttr(S().meta.maps?.[S().attr] ? S().attr : ATTRS.find((a) => S().meta.maps?.[a[0]])?.[0]);
    const first = () => draw();
    if (document.fonts?.ready) document.fonts.ready.then(first, first); else first();
  }

  EC.map = { init, draw, setAttr, highlight, focusPoint, link };
})();
