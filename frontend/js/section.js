/* Exploration Copilot — bottom-left panel: a registry of views (section, volume, stack, compare,
   plus whatever views.js registers), the view toggle, the panel heading and the four built-ins.

   EC.bottom = {
     init(),                               bind DOM + bus, draw the empty state
     register(name, {label, icon, render(container, payload), when()}),
                                           add a view; when() → boolean decides whether it is in the toggle
                                           (default: always); render may return {title, sub} (HTML) for the head
     show(name, payload), current(),       switch views (falls back to the first applicable view)
     head(titleHtml, subHtml),             set the panel heading from a view (caller escapes)
     setLead(detail), setWell(well), setEvidence(item|null)
   }
   Bus: consumes "lead", "well", "evidence", "audience", "blind", "imagefail"; emits "view". */
(() => {
  "use strict";
  const EC = (window.EC = window.EC || {});
  const { $, esc, icon, fmt, num, plural } = EC.util;

  // CSS gradients approximating the matplotlib colormaps used for the PNGs (data, not chrome).
  const CMAPS = {
    inferno: "linear-gradient(90deg,#000004,#56106e,#bb3754,#f98e09,#fcffa4)",
    viridis_r: "linear-gradient(90deg,#fde725,#35b779,#31688e,#440154)",
    cividis_r: "linear-gradient(90deg,#fee838,#a59c74,#575c6d,#00224e)",
    RdBu_r: "linear-gradient(90deg,#2166ac,#92c5de,#f7f7f7,#f4a582,#b2182b)",
    magma: "linear-gradient(90deg,#000004,#51127c,#b73779,#fc8961,#fcfdbf)",
    Greys: "linear-gradient(90deg,#ffffff,#969696,#000000)",
    terrain: "linear-gradient(90deg,#333399,#00b2b2,#99e57f,#d2bb85,#ffffff)",
  };
  const MULTIPLES = [["vpvs", "Vp/Vs", "gas", "brine"], ["sand", "Sand probability", "shale", "sand"], ["avo_diff", "Far − Near", "", "gas"]];
  const ACCENT = "--c:var(--color-accent-solid)";

  const views = {}; const order = [];
  let cur = null, det = null, sec = null, ev = null, forcedFail = false, token = 0;
  const analogs = {};   // lead id -> detail (compare view)
  let dom = null;       // { h, sub, tog, view }

  const sgn = (v, dp) => (v == null ? "—" : (v > 0 ? "+" : "") + fmt(v, dp).replace(/^-/, "−"));
  const leadOf = (d) => d?.lead || null;
  const empty = (ic, html) => `<div class="view-empty">${icon(ic)}<p>${html}</p></div>`;
  const onImgError = (img, fn) => { if (img) img.addEventListener("error", fn, { once: true }); };
  const applicable = () => order.filter((n) => { try { return views[n].when(); } catch { return false; } });

  // ------------------------------------------------------------------ registry + toggle
  function register(name, def) {
    if (!name || !def || typeof def.render !== "function") return;
    if (!views[name]) order.push(name);
    views[name] = { label: def.label || name, icon: def.icon || "square", render: def.render, when: def.when || (() => true) };
    if (dom) buildToggle();
  }
  function buildToggle() {
    const names = applicable();
    const t = dom.tog; if (!t) return;
    t.hidden = names.length < 2;
    t.innerHTML = names.map((n) => `<button type="button" role="tab" data-view="${esc(n)}" aria-selected="${String(n === cur)}" tabindex="${n === cur ? 0 : -1}" aria-controls="bottom-view">${icon(views[n].icon)}<span>${esc(views[n].label)}</span></button>`).join("");
  }
  function onToggleKey(e) {
    const tabs = [...dom.tog.querySelectorAll("[role=tab]")]; if (!tabs.length) return;
    const i = tabs.indexOf(document.activeElement);
    let j = null;
    if (e.key === "ArrowRight") j = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") j = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") j = 0;
    else if (e.key === "End") j = tabs.length - 1;
    if (j == null) return;
    e.preventDefault(); show(tabs[j].dataset.view); tabs[j].focus();
  }
  function head(title, sub) {
    if (!dom) return;
    if (title != null) dom.h.innerHTML = title;
    if (sub != null) dom.sub.innerHTML = sub;
  }
  function show(name, payload) {
    if (!dom) return;
    const names = applicable();
    if (!names.includes(name)) name = names.includes(cur) ? cur : names[0];
    if (!name) return;
    cur = name; token += 1;
    buildToggle();
    dom.view.innerHTML = "";
    let r = null;
    try { r = views[name].render(dom.view, payload); } catch (e) { console.error("view", name, e); dom.view.innerHTML = empty("triangle-alert", `This view hit an error: ${esc(e.message)}`); }
    if (r && typeof r === "object") head(r.title, r.sub);
    EC.bus.emit("view", name);
  }

  // ------------------------------------------------------------------ 1. section
  function renderSection(box, payload) {
    if (payload && payload.il != null) sec = { il: payload.il, why: payload.why || "" };
    const m = EC.S.meta || {};
    if (!sec) {
      head("Seismic section", "no lead selected");
      box.innerHTML = empty("activity", "Pick a lead or a well to load its section");
      return;
    }
    head(`Seismic section · IL <span class="num">${esc(sec.il)}</span>`, esc(sec.why));
    if (forcedFail) { box.innerHTML = empty("activity", "Section image didn’t load. Reload to retry."); return; }
    const who = sec.why.replace(/^through /, "").replace(/ crest$/, "");
    box.innerHTML = `<div class="view-section"><img alt="Seismic full-stack section along inline ${esc(sec.il)} through ${esc(who)}" src="${esc(EC.api.sectionUrl(sec.il))}"><div class="sec-overlay">${secOverlay(m)}</div></div>`;
    onImgError(box.querySelector("img"), () => { box.innerHTML = empty("activity", "Section image didn’t load. Reload to retry."); });
  }
  /* Only what can be placed honestly: the PNG carries its own axes, so the evidence tag names the
     window instead of boxing pixels we do not know. */
  function secOverlay(m) {
    let h = `<span class="sec-tag num-sm" style="inset-inline-start:var(--space-3);inset-block-start:var(--space-3)">IL ${esc(sec.il)} · ${esc(sec.why)}</span>`;
    const lead = leadOf(det);
    if (ev && lead && ev.ref?.lead === lead.id && m.window_ms) {
      h += `<span class="sec-tag num-sm" style="${ACCENT};inset-inline-start:var(--space-3);inset-block-start:calc(var(--space-3) + 32px)">${esc(ev.id || ev.label || "Evidence")} · measured in the window ${esc(fmt(m.window_ms[0], 0))}–${esc(fmt(m.window_ms[1], 0))} ms</span>`;
      h += `<span class="sec-tag num-sm" style="inset-inline-start:var(--space-3);inset-block-end:var(--space-3)">the image carries its own axes · window shown in the tag above</span>`;
    }
    return h;
  }

  // ------------------------------------------------------------------ 2. volume
  /* Isometric placement of a lead tag on the volume render, in fractions of the render box.
     u = i / (n_il − 1) along inlines, v = j / (n_xl − 1) along crosslines (bin-grid indices from the
     lead centroid), t = (crest_time − t0) / (t1 − t0) down the time axis (0 if unknown).
       x = 0.5 + 0.40·(v − u)              corner (IL0, XL0) at the top centre, IL runs down-left, XL down-right
       y = 0.08 + 0.22·(u + v) + 0.35·t    the two plan axes foreshortened 0.22, time stretched 0.35
     This mirrors the Figma D2 layout (IL 1000 · XL 2000 · 1930 ms at the top, IL 1159 left, XL 2199 right,
     2080 ms bottom right); the renderer should use the same projection so tags sit on their bodies. */
  function iso(d, m) {
    const [ni, nj] = m.shape || [1, 1];
    const u = (d.centroid?.[0] ?? 0) / Math.max(1, ni - 1), v = (d.centroid?.[1] ?? 0) / Math.max(1, nj - 1);
    const [t0, t1] = m.window_ms || [0, 1];
    const ct = d.structure?.crest_time_ms;
    const t = ct == null ? 0 : Math.min(1, Math.max(0, (ct - t0) / (t1 - t0 || 1)));
    return { x: 0.5 + 0.4 * (v - u), y: 0.08 + 0.22 * (u + v) + 0.35 * t };
  }
  function renderVolume(box) {
    const m = EC.S.meta || {}; const sel = leadOf(det)?.id;
    const il = m.ilines || ["—", "—"], xl = m.xlines || ["—", "—"], w = m.window_ms || ["—", "—"];
    head("Survey volume", `IL ${esc(il[0])}–${esc(il[1])} · XL ${esc(xl[0])}–${esc(xl[1])} · ${esc(fmt(w[0], 0))}–${esc(fmt(w[1], 0))} ms`);
    const tags = (EC.S.leads || []).map((d) => {
      const p = iso(d, m);
      return `<span class="sec-tag num-sm" style="${d.id === sel ? ACCENT + ";" : ""}inset-inline-start:${(p.x * 100).toFixed(1)}%;inset-block-start:${(p.y * 100).toFixed(1)}%;translate:-50% -50%">${esc(d.id)} · ${esc(fmt(d.gcos, 3))}</span>`;
    }).join("");
    const ax = (txt, pos) => `<span class="num-sm ax" style="position:absolute;${pos}">${txt}</span>`;
    const axes = ax(`IL ${esc(il[0])} · XL ${esc(xl[0])} · ${esc(fmt(w[0], 0))} ms`, "inset-inline-start:50%;inset-block-start:0;translate:-50% 0")
      + ax(`IL ${esc(il[1])}`, "inset-inline-start:var(--space-2);inset-block-start:32%")
      + ax(`XL ${esc(xl[1])}`, "inset-inline-end:var(--space-2);inset-block-start:31%")
      + ax(`${esc(fmt(w[1], 0))} ms`, "inset-inline-end:var(--space-2);inset-block-end:var(--space-2)");
    const end = (v) => (v == null ? "—" : fmt(v, Math.abs(v) < 0.1 ? 3 : undefined).replace(/^-/, "−"));
    const tiles = MULTIPLES.map(([k, label, lo, hi]) => {
      const mm = m.maps?.[k] || {};
      return `<div class="tile"><img alt="${esc(mm.label || label)} map" src="${esc(EC.api.mapUrl(k))}"><span class="label">${esc(label)}</span><span class="ramp" style="background:${CMAPS[mm.cmap] || CMAPS.inferno}"></span><span class="ends num-sm"><span>${esc(end(mm.vmin))}${lo ? " " + esc(lo) : ""}</span><span>→ ${esc(end(mm.vmax))}${hi ? " " + esc(hi) : ""}</span></span></div>`;
    }).join("");
    const url = EC.api.renderUrl("volume");
    box.innerHTML = `<div class="view-grid"><div class="view-col"><div class="render">${url ? `<img alt="Wireframe survey volume with the reservoir-top horizon and the lead bodies" src="${esc(url)}">` : ""}${tags}${axes}</div>
      <p class="caption">Top: reservoir-top pseudo-horizon (top_time). Lower mesh: base where sand probability ≥ <span class="num">0.5</span>. Colour: Vp/Vs. Display smoothing σ = <span class="num">3</span> bins.</p></div>
      <div class="multiples">${tiles}</div></div>`;
    const fail = () => { const col = box.querySelector(".view-col"); if (col) col.innerHTML = renderMissing(); };
    if (!url) fail(); else onImgError(box.querySelector(".render img"), fail);
  }
  const renderMissing = () => empty("box", "Volume render not built yet. Run <code>python -m engine.render_instrument</code> on the store, then reload.");

  // ------------------------------------------------------------------ 3. stack
  function renderStack(box) {
    const d = leadOf(det); if (!d) { box.innerHTML = empty("layers", "Pick a lead to see its risk stack"); return; }
    const sc = d.scorecard || {}, a = d.attributes || {}, st = d.structure || {};
    head(`Risk stack · ${esc(d.id)}`, "each layer is one chance factor");
    const P = (k) => `P ${esc(fmt(sc[k], 2))}`;
    const layers = [
      ["Seal", `${P("seal")} · schematic surface`],
      ["Trap", `${P("trap")}${st.closure_ms != null ? ` · closure ${esc(fmt(st.closure_ms, 1))} ms` : ""}`],
      ["Reservoir", `${P("reservoir")}${a.sand?.inside != null ? ` · sand ${esc(fmt(a.sand.inside, 2))}` : ""}${a.vpvs?.inside != null ? ` · Vp/Vs ${esc(fmt(a.vpvs.inside, 3))}` : ""}`],
      ["Charge", `${P("charge")} · schematic surface`],
    ];
    const leaders = layers.map(([n, v], i) => `<div class="leader" style="inset-inline-start:calc(50% + 56px);inset-block-start:${16 + 19 * i}%"><span class="label">${n}</span><span class="num-sm secondary">${v}</span></div>`).join("");
    const keys = ["reservoir", "trap", "seal", "charge"];
    const product = keys.reduce((p, k) => p * (Number(sc[k]) || 0), 1);
    const weak = keys.filter((k) => sc[k] != null).sort((x, y) => sc[x] - sc[y])[0];
    let why = "";
    if (weak === "trap" && st.closure_ms != null && st.updip_sand_prob != null) why = `The engine measures ${num(st.closure_ms, "ms", 1)} of structural closure; gas stays only if the up-dip shale (sand ${num(st.updip_sand_prob, "", 2)}) seals the channel.`;
    else if (weak === "reservoir" && a.sand?.inside != null && a.sand?.outside != null) why = `Sand probability inside is ${num(a.sand.inside, "", 2)} against ${num(a.sand.outside, "", 2)} around it${a.vpvs?.inside != null ? `; Vp/Vs inside ${num(a.vpvs.inside, "", 3)}` : ""}.`;
    else if (weak === "seal" && st.updip_sand_prob != null) why = `Seal is a schematic factor; the engine measures up-dip sand ${num(st.updip_sand_prob, "", 2)} above the crest${st.updip_is_shale != null ? ` (${st.updip_is_shale ? "shale" : "sand"})` : ""}.`;
    else if (weak === "charge" && a.vpvs?.inside != null && a.avo_diff?.inside != null) why = `Charge is a schematic factor; the engine measures Vp/Vs ${num(a.vpvs.inside, "", 3)} and far − near <span class="num">${esc(sgn(a.avo_diff.inside, 3))}</span> inside the lead.`;
    const url = EC.api.renderUrl(`stack_${d.id}`);
    const gcosNote = Math.abs(product - (d.gcos ?? product)) > 0.0015 ? ` <span class="num-sm faint">· product ${esc(fmt(product, 3))}</span>` : "";
    box.innerHTML = `<div class="view-grid"><div class="render">${url ? `<img alt="Exploded risk stack for ${esc(d.id)}: seal, trap, reservoir and charge layers" src="${esc(url)}">` : ""}${leaders}</div>
      <div class="stack-side">
        <p class="label">${esc(d.id)} · ${esc(d.trap_type || "Unclassified")} · ${d.drilled ? "drilled" : "undrilled"}</p>
        <p class="num secondary">${keys.map((k) => esc(fmt(sc[k], 2))).join(" × ")}</p>
        <p class="num" style="font-size:1.75rem">GCoS ${esc(fmt(d.gcos, 3))}${gcosNote}</p>
        <p>${weak ? `Weakest element: ${esc(weak)}. ` : ""}${why}</p>
        <p class="num-sm faint">Trap, reservoir: engine surfaces. Seal, charge: schematic.</p>
      </div></div>`;
    const fail = () => { const r = box.querySelector(".render"); if (r) r.innerHTML = empty("layers", "Stack render not built yet. Run <code>python -m engine.render_instrument</code> on the store, then reload."); };
    if (!url) fail(); else onImgError(box.querySelector(".render img"), fail);
  }

  // ------------------------------------------------------------------ 4. compare
  /* Feature → engine FEATURES name (engine/leads.py similar(): close when |Δz| < 0.5). */
  const ROWS = [
    { key: "sand_in", label: "Sand probability inside", get: (d) => d.attributes?.sand?.inside, dp: 3, same: "reservoir quality" },
    { key: "vpvs_z", label: "Vp/Vs inside", get: (d) => d.attributes?.vpvs?.inside, dp: 3, same: "charge signature" },
    { key: "avo_z", label: "Far − Near inside", get: (d) => d.attributes?.avo_diff?.inside, dp: 3, signed: true, same: "brightening" },
    { key: "elongation", label: "Channel geometry", geom: true, same: "depositional system" },
    { key: "closure_ms", label: "Structural closure", closure: true, same: "structural control" },
    { key: null, label: "Fault contact", fault: true, same: "fault exposure" },
  ];
  function cell(r, d) {
    if (!d) return "—";
    if (r.geom) return `elongation ${esc(fmt(d.shape?.elongation, 2))} · sinuosity ${esc(fmt(d.shape?.sinuosity, 2))}`;
    if (r.closure) return d.structure?.closure_ms ? `${esc(fmt(d.structure.closure_ms, 1))} ms` : "none";
    if (r.fault) return `${esc(fmt((d.fault_contact_frac || 0) * 100, 0))} %`;
    const v = r.get(d);
    return r.signed ? esc(sgn(v, r.dp)) : esc(fmt(v, r.dp));
  }
  function verdict(r, t, a, match) {
    if (!a) return `<span class="secondary">loading ${esc(t.id)}’s analog…</span>`;
    let same, why = "";
    if (r.fault) {
      const x = t.fault_contact_frac || 0, y = a.fault_contact_frac || 0;
      same = Math.abs(x - y) <= 0.05;
      if (!same) why = `${esc(x > y ? t.id : a.id)} touches a fault on ${esc(fmt(Math.max(x, y) * 100, 0))} % of its outline`;
    } else {
      same = match.includes(r.key);
      if (!same) {
        if (r.geom) why = `elongation ${esc(fmt(t.shape?.elongation, 2))} vs ${esc(fmt(a.shape?.elongation, 2))}`;
        else if (r.closure) { const x = t.structure?.closure_ms || 0, y = a.structure?.closure_ms || 0; why = `${esc(x < y ? t.id : a.id)} relies on a stratigraphic seal (${esc(fmt(Math.min(x, y), 1))} vs ${esc(fmt(Math.max(x, y), 1))} ms)`; }
        else { const x = r.get(t), y = r.get(a); why = x != null && y != null ? `${esc(t.id)} ${x < y ? "lower" : "higher"} by ${esc(fmt(Math.abs(x - y), r.dp))}` : "not measured on both"; }
      }
    }
    return same ? `${icon("check")} same ${esc(r.same)}` : `${icon("x")} differs · ${why}`;
  }
  function renderCompare(box) {
    const t = leadOf(det), s = det?.similar?.[0];
    if (!t || !s) { box.innerHTML = empty("list", "No drilled analog to compare against"); return; }
    const a = analogs[s.id] || null;
    const wr = s.well_results || {}; const disc = Object.values(wr).filter((x) => x === "discovery").length;
    const wells = (s.wells_inside || []).length;
    const tag = disc ? plural(disc, "discovery", "discoveries") : wells ? plural(wells, "dry well", "dry wells") : "undrilled";
    head(`${esc(t.id)} vs drilled analog ${esc(s.id)}`, `standardised features · cosine similarity <span class="num-sm">${esc(fmt(s.similarity, 3))}</span>`);
    const match = s.matching_features || [];
    box.innerHTML = `<div class="table-wrap compare-wrap"><table class="compare-table"><thead><tr><th scope="col">Feature</th><th scope="col">${esc(t.id)} · ${t.drilled ? "drilled" : "undrilled"}</th><th scope="col">${esc(s.id)} · ${esc(tag)}</th><th scope="col">Verdict</th></tr></thead><tbody>${
      ROWS.map((r) => `<tr><th scope="row">${esc(r.label)}</th><td class="num">${cell(r, t)}</td><td class="num">${cell(r, a)}</td><td class="num-sm">${verdict(r, t, a, match)}</td></tr>`).join("")}</tbody></table></div>`;
    if (!a) {
      const my = token;
      EC.api.json(`/api/leads/${s.id}`).then((d) => { analogs[s.id] = d.lead || d; if (my === token && cur === "compare") show("compare"); })
        .catch((e) => { if (my === token) for (const c of box.querySelectorAll("td:last-child")) c.innerHTML = `<span class="secondary">couldn’t load ${esc(s.id)} (${esc(e.message)})</span>`; });
    }
  }

  // ------------------------------------------------------------------ state from the bus
  function setLead(detail) {
    det = detail || null;
    const d = leadOf(det);
    if (d) { sec = { il: det.section_inline, why: `through ${d.id} crest` }; if (ev && ev.ref?.lead !== d.id) ev = null; }
    else { sec = null; ev = null; }
    show(cur || "section");
  }
  function setWell(well) {
    if (!well || well.inline == null) return;
    sec = { il: well.inline, why: `through ${well.name}` };
    show("section");
  }
  function setEvidence(item) {
    ev = item || null;
    const o = dom?.view.querySelector(".sec-overlay");
    if (o && cur === "section" && sec) o.innerHTML = secOverlay(EC.S.meta || {});
  }
  function onLead(p) {
    if (!p) return;
    if (p.detail) return setLead(p.detail);
    if (p.error) { det = null; sec = null; show("section"); if (dom) dom.view.innerHTML = empty("triangle-alert", esc(p.error)); return; }
    if (!p.id) return setLead(null);
    if (dom && cur === "section") head(null, `loading ${esc(p.id)}…`);  // keep the last section while the detail loads
  }

  register("section", { label: "Section", icon: "activity", render: renderSection });
  register("volume", { label: "Volume", icon: "box", render: renderVolume, when: () => !!leadOf(det) });
  register("stack", { label: "Stack", icon: "layers", render: renderStack, when: () => !!leadOf(det) });
  register("compare", { label: "Compare", icon: "list", render: renderCompare, when: () => !!(det?.similar?.length) });

  function init() {
    const view = $("bottom-view"); if (!view) return;
    dom = { h: $("bottom-h"), sub: $("bottom-sub"), tog: $("view-toggle"), view };
    dom.tog?.addEventListener("click", (e) => { const b = e.target.closest("[data-view]"); if (b) show(b.dataset.view); });
    dom.tog?.addEventListener("keydown", onToggleKey);
    EC.bus.on("lead", onLead);
    EC.bus.on("well", (p) => setWell(p?.well));
    EC.bus.on("evidence", setEvidence);
    EC.bus.on("audience", (a) => { if (a === "executive" && views.business) show("business"); else if (a !== "executive" && cur === "business") show("section"); });
    EC.bus.on("blind", (p) => { if (p && views.blind) show("blind", p); else if (!p && cur === "blind") show("section"); });
    EC.bus.on("imagefail", () => { forcedFail = true; if (cur === "section") show("section"); });
    show("section");
  }

  EC.bottom = { init, register, show, current: () => cur, head, setLead, setWell, setEvidence };
})();
