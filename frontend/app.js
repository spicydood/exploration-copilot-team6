/* Exploration Copilot front end. Plain JS, no build step.
   Talks to the FastAPI backend (/api/...). When window.__STANDALONE__ is set (the
   clickable prototype), the same UI reads embedded data and replays recorded answers. */
(() => {
  "use strict";
  const SA = window.__STANDALONE__ || null;
  const $ = (id) => document.getElementById(id);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const ATTRS = [
    ["sand", "Sand probability"], ["vpvs", "Vp/Vs"], ["avo_diff", "Far − Near"],
    ["pimp", "P-impedance"], ["top_time", "Structure"], ["disc", "Faults"],
  ];
  const TRAP_VAR = { Structural: "--struct", Stratigraphic: "--strat", Combination: "--combo", Unclassified: "--uncls" };
  const CMAPS = {  // CSS gradients approximating the matplotlib colormaps used for the PNGs
    inferno: "linear-gradient(90deg,#000004,#56106e,#bb3754,#f98e09,#fcffa4)",
    viridis_r: "linear-gradient(90deg,#fde725,#35b779,#31688e,#440154)",
    cividis_r: "linear-gradient(90deg,#fee838,#a59c74,#575c6d,#00224e)",
    RdBu_r: "linear-gradient(90deg,#2166ac,#92c5de,#f7f7f7,#f4a582,#b2182b)",
    magma: "linear-gradient(90deg,#000004,#51127c,#b73779,#fc8961,#fcfdbf)",
    Greys: "linear-gradient(90deg,#ffffff,#969696,#000000)",
    terrain: "linear-gradient(90deg,#333399,#00b2b2,#99e57f,#d2bb85,#ffffff)",
  };

  const S = { meta: null, wells: [], leads: [], attr: "sand", sel: null, img: null, hover: null,
              evidence: {}, busy: false, flashLead: null, flashWell: null };

  // ------------------------------------------------------------------ API layer
  const api = {
    json: async (path) => {
      if (SA) {
        if (path === "/api/meta") return SA.meta;
        if (path === "/api/wells") return SA.wells;
        if (path === "/api/leads") return SA.leads;
        if (path === "/api/health") return SA.health;
        const m = path.match(/^\/api\/leads\/(\w+)/);
        if (m) return SA.details[m[1]];
      }
      const r = await fetch(path);
      if (!r.ok) throw new Error(`${path}: ${r.status}`);
      return r.json();
    },
    mapUrl: (name) => (SA ? SA.maps[name] : `/api/map/${name}.png`),
    sectionUrl: (il) => {
      if (!SA) return `/api/section.png?inline=${il}`;
      const keys = Object.keys(SA.sections).map(Number);
      const k = keys.reduce((a, b) => (Math.abs(b - il) < Math.abs(a - il) ? b : a), keys[0]);
      return SA.sections[k];
    },
    chat: async function* (message, lead) {
      if (SA) { yield* replay(message, lead); return; }
      const res = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, selected_lead: lead }),
      });
      if (!res.ok || !res.body) throw new Error(`chat failed: ${res.status}`);
      const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let cut;
        while ((cut = buf.indexOf("\n\n")) >= 0) {
          const chunk = buf.slice(0, cut); buf = buf.slice(cut + 2);
          for (const line of chunk.split("\n")) if (line.startsWith("data: ")) yield JSON.parse(line.slice(6));
        }
      }
    },
  };

  function saKey(msg, lead) {
    const m = msg.toLowerCase();
    const well = SA.wells.find((w) => m.includes(w.name));
    const lid = (msg.toUpperCase().match(/\bL\d+\b/) || [])[0] || lead;
    if (/inline|\bil\b/.test(m)) return "point";
    if (/similar|look.?alike|analog|yet to be|untested/.test(m)) return `${lid || "-"}|similar`;
    if (well) return `well|${well.name}`;
    if (/rank|\btop\b|\blist\b|all leads|overview/.test(m)) return "rank";
    if (lid && /wrong|alternative|risk|devil|uncertain/.test(m)) return `${lid}|risks`;
    if (lid) return `${lid}|opportunity`;
    return "-|opportunity";
  }
  async function* replay(msg, lead) {
    const key = saKey(msg, lead);
    let events = SA.answers[key];
    if (!events) {
      events = SA.answers["-|opportunity"];
      yield { type: "status", text: "Prototype: no recorded answer for that exact question, showing the closest one" };
    }
    for (const ev of events) {
      if (ev.type === "token") await new Promise((r) => setTimeout(r, 10));
      else if (ev.type === "tool") await new Promise((r) => setTimeout(r, 180));
      yield ev;
    }
  }

  // ------------------------------------------------------------------ boot
  async function boot() {
    try {
      [S.meta, S.wells, S.leads] = await Promise.all([api.json("/api/meta"), api.json("/api/wells"), api.json("/api/leads")]);
    } catch (e) {
      $("card").innerHTML = `<div class="empty">Couldn't load the survey (${esc(e.message)}). Run <code>python -m engine.precompute</code>, then restart the server.</div>`;
      return;
    }
    $("survey-pill").hidden = !S.meta.synthetic;
    $("map-sub").textContent = `IL ${S.meta.ilines[0]}–${S.meta.ilines[1]} · XL ${S.meta.xlines[0]}–${S.meta.xlines[1]} · window ${S.meta.window_ms[0]}–${S.meta.window_ms[1]} ms`;
    buildAttrBar(); renderTable(); setAttr("sand"); health(); setSuggestions();
    const firstUndrilled = S.leads.find((d) => !d.drilled) || S.leads[0];
    if (firstUndrilled) selectLead(firstUndrilled.id, { quiet: true });
    welcome();
  }

  async function health() {
    try {
      const h = await api.json("/api/health");
      const dot = $("llm-pill").querySelector(".dot");
      if (SA) { dot.className = "dot off"; $("llm-text").textContent = "Prototype · recorded answers"; return; }
      if (h.llm_mode === "gemma") {
        dot.className = "dot " + (h.llm_reachable ? "ok" : "bad");
        $("llm-text").textContent = h.llm_reachable ? "Gemma 4 connected" : "Gemma unreachable · rules fallback";
      } else { dot.className = "dot off"; $("llm-text").textContent = "Offline reasoner"; }
    } catch { $("llm-text").textContent = "Server not responding"; }
  }

  // ------------------------------------------------------------------ map
  function buildAttrBar() {
    const bar = $("attr-bar");
    for (const [k, label] of ATTRS) {
      if (!S.meta.maps[k]) continue;
      const b = document.createElement("button");
      b.className = "chip"; b.type = "button"; b.dataset.attr = k; b.textContent = label;
      b.setAttribute("aria-pressed", "false");
      b.onclick = () => setAttr(k);
      bar.append(b);
    }
  }
  function setAttr(k) {
    S.attr = k;
    for (const b of $("attr-bar").children) b.setAttribute("aria-pressed", String(b.dataset.attr === k));
    const m = S.meta.maps[k];
    $("ramp").innerHTML = `${fmt(m.vmin)} <i style="background:${CMAPS[m.cmap] || CMAPS.inferno}"></i> ${fmt(m.vmax)} <span>${esc(m.label)}</span>`;
    const img = new Image();
    img.onload = () => { S.img = img; drawMap(); };
    img.src = api.mapUrl(k);
  }
  function geom() {
    const c = $("map"); const [ni, nj] = S.meta.shape;
    const W = 900, H = Math.round((900 * ni) / nj);
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
    return { c, ctx: c.getContext("2d"), W, H, sx: W / nj, sy: H / ni };
  }
  const P = (g, i, j) => [(j + 0.5) * g.sx, (i + 0.5) * g.sy];
  function drawMap() {
    if (!S.meta) return;
    const g = geom(); const { ctx, W, H } = g;
    ctx.clearRect(0, 0, W, H);
    if (S.img) ctx.drawImage(S.img, 0, 0, W, H);
    for (const d of S.leads) {
      const col = css(TRAP_VAR[d.trap_type] || "--uncls");
      const sel = S.sel === d.id, hov = S.hover?.lead === d.id, fl = S.flashLead === d.id;
      ctx.beginPath();
      d.polygon.forEach(([i, j], n) => { const [x, y] = P(g, i, j); n ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.closePath();
      ctx.fillStyle = col + (sel || fl ? "40" : hov ? "30" : "14"); ctx.fill();
      ctx.lineJoin = "round";
      ctx.lineWidth = sel || fl ? 7 : 5; ctx.strokeStyle = "rgba(6,10,14,.75)"; ctx.stroke();   // dark halo
      ctx.lineWidth = sel || fl ? 3.5 : 2.5; ctx.strokeStyle = col; ctx.setLineDash(d.drilled ? [] : [8, 5]); ctx.stroke();
      ctx.setLineDash([]);
      const [cx, cy] = P(g, d.centroid[0], d.centroid[1]);
      label(ctx, d.id, cx, cy, col);
    }
    for (const w of S.wells) {
      if (w.i == null) continue;
      const [x, y] = P(g, w.i, w.j);
      const col = w.result === "discovery" ? css("--good") : w.result === "dry" ? css("--bad") : css("--uncls");
      const big = S.flashWell === w.name || S.hover?.well === w.name;
      ctx.beginPath(); ctx.arc(x, y, big ? 8 : 6, 0, 7);
      ctx.fillStyle = col; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = "#ffffff"; ctx.stroke();
      ctx.font = "600 13px 'Barlow Semi Condensed', 'Arial Narrow', sans-serif";
      ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "rgba(0,0,0,.75)"; ctx.lineWidth = 3;
      ctx.strokeText(w.name, x + 10, y + 4); ctx.fillText(w.name, x + 10, y + 4);
    }
  }
  function label(ctx, text, x, y, col) {
    ctx.font = "600 14px 'JetBrains Mono', monospace";
    const w = ctx.measureText(text).width + 12;
    ctx.fillStyle = "rgba(8,12,17,.85)"; roundRect(ctx, x - w / 2, y - 11, w, 22, 5); ctx.fill();
    ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.fillStyle = "#ffffff"; ctx.textAlign = "center"; ctx.fillText(text, x, y + 5); ctx.textAlign = "start";
  }
  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  function hit(ev) {
    const g = geom(); const r = g.c.getBoundingClientRect();
    const x = ((ev.clientX - r.left) / r.width) * g.W, y = ((ev.clientY - r.top) / r.height) * g.H;
    for (const w of S.wells) {
      if (w.i == null) continue;
      const [wx, wy] = P(g, w.i, w.j);
      if (Math.hypot(wx - x, wy - y) < 10) return { well: w.name, x: ev.clientX - r.left, y: ev.clientY - r.top };
    }
    const i = y / g.sy - 0.5, j = x / g.sx - 0.5;
    for (const d of S.leads) if (inPoly(i, j, d.polygon)) return { lead: d.id, x: ev.clientX - r.left, y: ev.clientY - r.top };
    return null;
  }
  function inPoly(i, j, poly) {
    let inside = false;
    for (let a = 0, b = poly.length - 1; a < poly.length; b = a++) {
      const [ia, ja] = poly[a], [ib, jb] = poly[b];
      if ((ia > i) !== (ib > i) && j < ((jb - ja) * (i - ia)) / (ib - ia) + ja) inside = !inside;
    }
    return inside;
  }
  $("map").addEventListener("mousemove", (ev) => {
    const h = hit(ev); const tip = $("map-tip");
    if (JSON.stringify(h?.lead || h?.well) !== JSON.stringify(S.hover?.lead || S.hover?.well)) { S.hover = h; drawMap(); }
    if (!h) { tip.hidden = true; $("map").style.cursor = "default"; return; }
    $("map").style.cursor = "pointer";
    if (h.lead) {
      const d = S.leads.find((x) => x.id === h.lead);
      tip.innerHTML = `<b>${d.id}</b> · ${esc(d.trap_type)}<br>${esc(d.subtype)}<br>GCoS ${d.gcos} · ${d.area_km2} km² · ${d.drilled ? "drilled" : "undrilled"}`;
    } else {
      const w = S.wells.find((x) => x.name === h.well);
      tip.innerHTML = `<b>${esc(w.name)}</b><br>${esc(w.result_text || w.result)}<br>IL ${w.inline} · XL ${w.crossline}`;
    }
    tip.style.left = h.x + "px"; tip.style.top = h.y + "px"; tip.hidden = false;
  });
  $("map").addEventListener("mouseleave", () => { $("map-tip").hidden = true; S.hover = null; drawMap(); });
  $("map").addEventListener("click", (ev) => {
    const h = hit(ev);
    if (h?.lead) selectLead(h.lead);
    else if (h?.well) selectWell(h.well);
  });

  // ------------------------------------------------------------------ table + card
  function renderTable() {
    $("lead-rows").innerHTML = S.leads.map((d) => `
      <tr data-id="${d.id}" class="${S.sel === d.id ? "sel" : ""}" tabindex="0">
        <td><b>${d.id}</b></td>
        <td><span class="trap t-${d.trap_type}">${esc(d.trap_type)}</span></td>
        <td class="num">${d.gcos.toFixed(3)}<span class="gbar"><i style="width:${Math.min(100, d.gcos * 250)}%"></i></span></td>
        <td class="num">${d.area_km2}</td>
        <td class="num">${d.risked_area_km2}</td>
        <td>${d.wells_inside.length ? d.wells_inside.map((n) => wellTag(n)).join(", ") : '<span style="color:var(--muted)">undrilled</span>'}</td>
      </tr>`).join("");
    for (const tr of $("lead-rows").children) {
      tr.onclick = () => selectLead(tr.dataset.id);
      tr.onkeydown = (e) => { if (e.key === "Enter") selectLead(tr.dataset.id); };
    }
  }
  const wellTag = (n) => {
    const w = S.wells.find((x) => x.name === n);
    return `<span class="res-${w?.result}">${esc(n)}</span>`;
  };

  async function selectLead(id, opts = {}) {
    S.sel = id; drawMap(); renderTable();
    const det = await api.json(`/api/leads/${id}`);
    renderCard(det);
    showSection(det.section_inline, `through ${id} crest`);
    setSuggestions(id);
    if (!opts.quiet) $("card-panel").classList.remove("flash"), void $("card-panel").offsetWidth, $("card-panel").classList.add("flash");
  }
  function selectWell(name) {
    const w = S.wells.find((x) => x.name === name);
    S.flashWell = name; drawMap();
    showSection(w.inline, `through ${name}`);
    setSuggestions(S.sel, name);
  }
  function showSection(il, why) {
    $("section").src = api.sectionUrl(il);
    $("sec-sub").textContent = `Inline ${il} · ${why}`;
  }

  function renderCard(det) {
    const d = det.lead, sc = d.scorecard;
    const weakest = Object.entries(sc).sort((a, b) => a[1] - b[1])[0][0];
    const rows = ["reservoir", "trap", "seal", "charge"].map((k) => `
      <span class="lbl ${k === weakest ? "weak" : ""}">${k[0].toUpperCase() + k.slice(1)}</span>
      <span class="bar ${k === weakest ? "weak" : ""}"><i style="width:${sc[k] * 100}%"></i></span>
      <span class="n">${sc[k].toFixed(2)}</span>`).join("");
    const wells = det.wells.length
      ? det.wells.map((w) => `${wellTag(w.well)} <span style="color:var(--muted)">${esc(w.result_text || "")}</span>`).join("<br>")
      : "None. This body is untested.";
    const simLabel = det.similar_pool === "drilled" ? "Closest drilled analog" : "Untested look-alikes";
    const sim = det.similar.length
      ? det.similar.map((r) => `<b>${r.id}</b> ${esc(r.trap_type)} · similarity ${r.similarity}`).join("<br>")
      : "None found";
    $("card").innerHTML = `
      <div class="card-body">
        <div class="lead-head">
          <div><h3>${d.id} <span class="trap t-${d.trap_type}" style="font-size:15px;vertical-align:3px">${esc(d.trap_type)}</span></h3>
          <div class="subtype">${esc(d.subtype)}</div></div>
          <div class="gcos"><div class="v">${d.gcos.toFixed(3)}</div><div class="l">Chance of success</div></div>
        </div>
        <div class="score" aria-label="Petroleum-system scorecard">${rows}</div>
        <dl class="facts">
          <dt>Area</dt><dd>${d.area_km2} km² · risked ${d.risked_area_km2} km²</dd>
          <dt>Shape</dt><dd>elongation ${d.shape.elongation} · sinuosity ${d.shape.sinuosity}</dd>
          <dt>Structure</dt><dd>closure ${d.structure.closure_ms ?? "–"} ms · fault contact ${Math.round(d.fault_contact_frac * 100)}%</dd>
          <dt>Wells</dt><dd>${wells}</dd>
          <dt>${simLabel}</dt><dd>${sim}</dd>
        </dl>
        <details class="alts"><summary>What could make this wrong (${det.alternatives.length})</summary>
          <ul>${det.alternatives.map((a) => `<li><b>${esc(a.risk)}:</b> ${esc(a.alternative)} <i>De-risk: ${esc(a.de_risk)}</i></li>`).join("")}</ul>
        </details>
        <div class="actions">
          <button class="btn primary" data-q="What is the geological opportunity here, and why?">Explain this lead</button>
          <button class="btn" data-q="What could make ${d.id} wrong?">Devil's advocate</button>
          <button class="btn" data-q="Find similar traps yet to be tested like ${d.id}">Find look-alikes</button>
        </div>
      </div>`;
    for (const b of $("card").querySelectorAll("[data-q]")) b.onclick = () => ask(b.dataset.q);
  }

  // ------------------------------------------------------------------ chat
  function setSuggestions(lead, well) {
    const dry = S.wells.find((w) => w.result === "dry" && S.leads.some((d) => d.wells_inside.includes(w.name)));
    const qs = [];
    if (well) qs.push(`Why did ${well} ${S.wells.find((w) => w.name === well)?.result === "dry" ? "fail" : "succeed"}?`);
    qs.push(lead ? "What is the geological opportunity here, and why?" : "What is the geological opportunity, and why?");
    if (lead) qs.push(`What could make ${lead} wrong?`);
    qs.push("Find similar traps yet to be tested");
    if (!well && dry) qs.push(`Why did ${dry.name} fail?`);
    qs.push("Rank the top leads");
    $("suggest").innerHTML = qs.slice(0, 4).map((q) => `<button type="button">${esc(q)}</button>`).join("");
    for (const b of $("suggest").children) b.onclick = () => ask(b.textContent);
  }
  function welcome() {
    const m = document.createElement("div"); m.className = "msg bot";
    m.innerHTML = `<div class="md"><p>I read the stacks, inversion volumes and wells for this survey and mapped <b>${S.leads.length} leads</b> around <b>${S.wells.length} wells</b>. Ask what the opportunity is, why a well failed, or which untested traps look like a discovery. Tags like <span class="ev">E3</span> open the measurement behind each claim.</p></div>`;
    $("log").append(m);
  }
  $("ask").addEventListener("submit", (e) => { e.preventDefault(); const q = $("q").value.trim(); if (q) { $("q").value = ""; ask(q); } });

  async function ask(q) {
    if (S.busy) return;
    S.busy = true;
    const log = $("log");
    const u = document.createElement("div"); u.className = "msg user"; u.textContent = q; log.append(u);
    const b = document.createElement("div"); b.className = "msg bot";
    b.innerHTML = `<div class="trail"></div><div class="md"><p style="color:var(--muted)">Thinking…</p></div><div class="meta-line"></div>`;
    log.append(b); log.scrollTop = log.scrollHeight;
    const trail = b.querySelector(".trail"), md = b.querySelector(".md"), meta = b.querySelector(".meta-line");
    let text = "", pending = false;
    const paint = () => { pending = false; md.innerHTML = renderMd(text); log.scrollTop = log.scrollHeight; };
    try {
      for await (const ev of api.chat(q, S.sel)) {
        if (ev.type === "status") { if (!text) md.innerHTML = `<p style="color:var(--muted)">${esc(ev.text)}…</p>`; }
        else if (ev.type === "tool") {
          const s = document.createElement("span");
          s.textContent = `${ev.name}(${Object.values(ev.args || {}).join(", ")})` + (ev.evidence_ids?.length ? ` → ${ev.evidence_ids.length} facts` : "");
          s.title = ev.why || ""; trail.append(s);
        } else if (ev.type === "evidence") { for (const it of ev.items) S.evidence[it.id] = it; }
        else if (ev.type === "token") { text += ev.text; if (!pending) { pending = true; requestAnimationFrame(paint); } }
        else if (ev.type === "done") {
          paint();
          const bad = ev.unverified_numbers?.length;
          meta.innerHTML = `${ev.cited.length} facts cited · <span class="${bad ? "warn" : ""}">${bad ? bad + " number(s) not found in evidence: " + esc(ev.unverified_numbers.join(", ")) : "every number traced to evidence"}</span> · ${ev.mode === "gemma" ? "Gemma 4" : "offline reasoner"} · ${ev.seconds}s${ev.note ? " · " + esc(ev.note) : ""}`;
        }
      }
    } catch (e) {
      md.innerHTML = `<p>Couldn't get an answer: ${esc(e.message)}. Check the server is running, then try again.</p>`;
    }
    S.busy = false;
  }

  // ------------------------------------------------------------------ evidence chips
  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".ev[data-id]");
    const pop = $("evpop");
    if (!chip) { if (!e.target.closest("#evpop")) pop.hidden = true; return; }
    const it = S.evidence[chip.dataset.id];
    if (!it) return;
    const val = `${it.value}${it.unit ? " " + it.unit : ""}${it.compare != null ? ` <span style="color:var(--muted)">vs ${it.compare}</span>` : ""}`;
    pop.innerHTML = `<div class="id">${it.id}</div><div>${esc(it.label)}</div><div class="val">${val}</div>${it.note ? `<div style="color:var(--muted)">${esc(it.note)}</div>` : ""}`;
    const r = chip.getBoundingClientRect();
    pop.style.left = Math.min(r.left, innerWidth - 336) + "px"; pop.style.top = r.bottom + 6 + "px"; pop.hidden = false;
    const ref = it.ref || {};
    if (ref.map && ref.map !== S.attr && S.meta.maps[ref.map]) setAttr(ref.map);
    if (ref.lead) { S.flashLead = ref.lead; if (ref.lead !== S.sel) selectLead(ref.lead, { quiet: true }); }
    if (ref.well) { S.flashWell = ref.well; }
    drawMap();
    setTimeout(() => { S.flashLead = null; S.flashWell = null; drawMap(); }, 1600);
  });

  // ------------------------------------------------------------------ tiny markdown
  function inline(s) {
    return esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\[(E\d+)\]/g, '<button type="button" class="ev" data-id="$1">$1</button>');
  }
  function renderMd(src) {
    const lines = src.split("\n"); let out = "", i = 0;
    while (i < lines.length) {
      const l = lines[i];
      if (/^\s*\|/.test(l)) {
        const rows = []; while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
        const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const body = rows.filter((r, k) => !(k === 1 && /^[\s|:-]+$/.test(r)));
        out += `<div class="tw"><table><thead><tr>${cells(body[0]).map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>` +
          body.slice(1).map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("") + "</tbody></table></div>";
      } else if (/^\s*[-*] /.test(l) || /^\s*\d+\. /.test(l)) {
        const ordered = /^\s*\d+\. /.test(l); const items = [];
        while (i < lines.length && (/^\s*[-*] /.test(lines[i]) || /^\s*\d+\. /.test(lines[i]))) items.push(lines[i++].replace(/^\s*([-*]|\d+\.) /, ""));
        out += `<${ordered ? "ol" : "ul"}>${items.map((t) => `<li>${inline(t)}</li>`).join("")}</${ordered ? "ol" : "ul"}>`;
      } else if (l.trim() === "") { i++; }
      else {
        const para = []; while (i < lines.length && lines[i].trim() !== "" && !/^\s*(\||[-*] |\d+\. )/.test(lines[i])) para.push(lines[i++].replace(/^#+\s*/, ""));
        out += `<p>${inline(para.join(" "))}</p>`;
      }
    }
    return out;
  }
  function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
  function fmt(v) { const a = Math.abs(v); return a >= 1000 ? Math.round(v).toString() : a >= 10 ? v.toFixed(1) : v.toFixed(2); }

  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", drawMap);
  new MutationObserver(drawMap).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  boot();
})();
