/* Exploration Copilot — evidence panel (scorecard, devil's advocate, similar traps), the executive
   value list + business case, the blind well test, and the committee memo.
   Owns: #ev-tabs, #ev-body, #blind-btn, #memo-btn, <dialog id="memo">, bottom views "business" and "blind".
   Writes EC.S.blind and EC.S.assumptions only. Every number shown comes from the store or from the
   user's own cost / value inputs; anything missing renders "—" or is left out.
   EC.util / EC.bus / EC.S are created by app.js (loaded last), so they are bound inside init(). */
(() => {
  "use strict";
  const EC = (window.EC = window.EC || {});
  let $, esc, icon, fmt, num, plural, bus, S;

  const TABS = [
    { name: "scorecard", label: "Scorecard", icon: "layers" },
    { name: "devil", label: "Devil’s advocate", icon: "triangle-alert" },
    { name: "similar", label: "Similar traps", icon: "search" },
  ];
  const ELEMENTS = [
    { k: "reservoir", label: "Reservoir", icon: "layers" },
    { k: "trap", label: "Trap", icon: "box" },
    { k: "seal", label: "Seal", icon: "sliders-horizontal" },
    { k: "charge", label: "Charge", icon: "activity" },
  ];
  let tab = "scorecard";
  let cur = { id: null, detail: null, error: null };   // latest "lead" bus payload
  let choosing = false;                                 // blind test: picking a well
  let lastAnswer = null;                                // latest "answer" payload
  let bizEl = null, blindEl = null;                     // bottom-view containers we rendered into

  // ------------------------------------------------------------------ helpers
  const nf = new Intl.NumberFormat("en-MY", { maximumFractionDigits: 1 });
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const money = (v) => (isNum(v) ? `${v < 0 ? "−" : "+"}$${nf.format(Math.abs(v))}M` : "—");
  const signed = (v) => (isNum(v) ? `${v < 0 ? "−" : "+"}${Math.abs(v).toFixed(2)}` : "—");
  const cap = (s) => { s = String(s ?? ""); return s.charAt(0).toUpperCase() + s.slice(1); };
  const pct = (v) => (isNum(v) ? Math.round(v * 100) : null);
  const plain = (s) => String(s ?? "").replace(/[*_`#]+/g, "").replace(/\s+/g, " ").trim();
  const paragraphs = (t) => String(t ?? "").split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const mode = () => (S.blind || choosing ? "blind" : S.audience === "executive" ? "executive" : "geo");
  const assumed = () => isNum(S.assumptions?.cost) && isNum(S.assumptions?.value);
  const emv = (d) => (d && isNum(d.gcos) && assumed() ? d.gcos * S.assumptions.value - (1 - d.gcos) * S.assumptions.cost : null);
  const weakest = (sc) => ELEMENTS.map((e) => e.k).filter((k) => isNum(sc?.[k])).sort((a, b) => sc[a] - sc[b])[0] || null;
  const leadNow = () => { const id = S.sel ?? cur.id; return cur.detail?.lead?.id === id ? cur.detail.lead : S.detail?.lead?.id === id ? S.detail.lead : S.leads.find((d) => d.id === id) || null; };
  const wellOf = (name) => S.wells.find((w) => w.name === name) || null;
  const leadOfWell = (name) => S.leads.find((d) => (d.wells_inside || []).includes(name)) || null;
  const hidden = (name) => !!S.blind && S.blind.well === name;
  const wellResult = (name) => (hidden(name) ? "hidden" : wellOf(name)?.result || "unknown");
  const resClass = (name) => ({ discovery: "res-discovery", dry: "res-dry" }[wellResult(name)] || "res-unknown");
  const answerFor = (id) => { const a = S.lastAnswer || lastAnswer; return a && (!a.lead || !id || a.lead === id) ? a : null; };

  /* Discovery / dry / hidden summary of a lead's wells, e.g. "2 discoveries", "dry · kenari-2", "meranti-1 hidden". */
  function wellsSummary(d) {
    const names = d.wells_inside || [];
    if (!d.drilled || !names.length) return "undrilled";
    const disc = names.filter((n) => wellResult(n) === "discovery").length;
    const dry = names.filter((n) => wellResult(n) === "dry");
    const hid = names.filter(hidden);
    const parts = [];
    if (disc) parts.push(plural(disc, "discovery", "discoveries"));
    if (dry.length) parts.push(`dry · ${dry.join(", ")}`);
    if (hid.length) parts.push(`${hid.join(", ")} hidden`);
    return parts.join(" · ") || "drilled";
  }

  /* The reason line under each scorecard row, built only from engine fields. */
  function why(k, d) {
    const a = d.attributes || {}, st = d.structure || {};
    if (k === "reservoir") return a.sand ? `Sand ${num(a.sand.inside, "", 3)} inside vs ${num(a.sand.outside, "", 3)} around` : null;
    if (k === "trap") return st.closure_ms != null || d.subtype ? `closure ${num(st.closure_ms, "ms", 1)} · ${esc(d.subtype || "")}` : null;
    if (k === "seal") return st.updip_sand_prob != null ? `up-dip sand ${num(st.updip_sand_prob, "", 2)} — inferred, not imaged` : null;
    if (k === "charge") return a.vpvs ? `Vp/Vs ${num(a.vpvs.inside, "", 3)} vs ${num(a.vpvs.outside, "", 3)} around` : null;
    return null;
  }

  function scoreRows(d) {
    const sc = d.scorecard || {}, wk = weakest(sc);
    return `<div class="score" aria-label="Petroleum-system scorecard">${ELEMENTS.map((e) => {
      const v = sc[e.k], weak = e.k === wk, reason = why(e.k, d);
      const w = isNum(v) ? Math.round(Math.min(1, Math.max(0, v)) * 100) : 0;
      return `<div class="score-row${weak ? " is-weak" : ""}">
        <span class="light" aria-hidden="true"></span>${icon(e.icon)}<span class="label">${e.label}</span>
        <span class="track" aria-hidden="true"><i style="width:${w}%"></i></span><span class="v num">${esc(fmt(v, 2))}</span>
        ${weak || reason ? `<span class="why">${weak ? `<span class="weak-word">weakest</span>${reason ? " · " : ""}` : ""}${reason || ""}</span>` : ""}
      </div>`;
    }).join("")}</div>${scoreFormula(sc, d)}`;
  }
  /* P4: the product line under the rows (CSS shows it on the phone Leads tab only) */
  function scoreFormula(sc, d) {
    const vals = ELEMENTS.map((e) => sc[e.k]);
    if (!vals.every(isNum)) return "";
    return `<p class="score-formula num-sm secondary">${vals.map((x) => esc(fmt(x, 2))).join(" × ")} = ${esc(fmt(d.gcos, 3))}</p>`;
  }

  function wellButton(name) {
    const r = wellResult(name);
    return `<button type="button" class="well ${resClass(name)}" data-well="${esc(name)}"><span class="well-glyph" aria-hidden="true"></span>${esc(name)} <span class="caption">${esc(r)}</span></button>`;
  }

  const skeleton = () => `<div class="skeleton" aria-hidden="true"><i aria-hidden="true" class="tall"></i><i aria-hidden="true"></i><i aria-hidden="true"></i><i aria-hidden="true" class="box"></i><i aria-hidden="true"></i><i aria-hidden="true"></i></div><p class="vh" role="status">Loading ${esc(cur.id || "the lead")}</p>`;
  const empty = () => `<div class="empty">${icon("layers")}<h3>No lead selected</h3><p>Click an outline on the map or ask about a lead to see its petroleum-system scorecard.</p></div>`;

  // ------------------------------------------------------------------ tabs (geoscientist mode)
  function renderTabs() {
    const t = $("ev-tabs"); if (!t) return;
    if (mode() !== "geo") { t.hidden = true; t.innerHTML = ""; return; }
    t.hidden = false;
    t.innerHTML = TABS.map((x) => `<button type="button" role="tab" id="tab-${x.name}" aria-selected="${x.name === tab}" tabindex="${x.name === tab ? 0 : -1}" aria-controls="ev-body">${icon(x.icon)}${esc(x.label)}</button>`).join("");
    for (const b of t.children) b.addEventListener("click", () => setTab(b.id.slice(4)));
  }
  function setTab(name) {
    if (!TABS.some((x) => x.name === name)) return;
    tab = name;
    for (const b of $("ev-tabs")?.children || []) { const on = b.id === `tab-${name}`; b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1; }
    renderBody();
  }
  function onTabKey(e) {
    const step = { ArrowRight: 1, ArrowLeft: -1, Home: 0, End: 0 }[e.key];
    if (step === undefined) return;
    const i = TABS.findIndex((x) => x.name === tab);
    const n = e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1 : (i + step + TABS.length) % TABS.length;
    e.preventDefault(); setTab(TABS[n].name); $(`tab-${TABS[n].name}`)?.focus();
  }

  // ------------------------------------------------------------------ evidence body
  function renderBody() {
    const body = $("ev-body"); if (!body) return;
    const m = mode();
    if (m === "geo") { body.setAttribute("role", "tabpanel"); body.setAttribute("aria-labelledby", `tab-${tab}`); }
    else { body.removeAttribute("role"); body.removeAttribute("aria-labelledby"); }
    body.innerHTML = m === "blind" ? blindBody() : m === "executive" ? execBody() : geoBody();
  }
  function geoBody() {
    if (cur.error) return `<div class="error-inline"><p>${esc(cur.error)}</p><div><button type="button" class="btn" data-act="retry" data-lead="${esc(cur.id)}">Try again</button></div></div>`;
    if (cur.id && !cur.detail) return skeleton();
    if (!cur.detail?.lead) return empty();
    return tab === "devil" ? devilTab(cur.detail) : tab === "similar" ? similarTab(cur.detail) : scorecardTab(cur.detail);
  }

  function scorecardTab(det) {
    const d = det.lead, sc = d.scorecard || {}, wk = weakest(sc), sh = d.shape || {}, st = d.structure || {};
    const wells = (det.wells || []).length ? det.wells.map((w) => wellButton(w.well)).join(" ") : "None. This body is untested.";
    const simLabel = det.similar_pool === "drilled" ? "Drilled analogs" : "Look-alikes";
    const sim = (det.similar || []).length ? det.similar.map((r) => `<button type="button" class="row-btn" data-lead="${esc(r.id)}" data-sim="${esc(r.similarity)}">${esc(r.id)}</button> <span class="num-sm secondary">${esc(signed(r.similarity))}</span>`).join(" · ") : "none found";
    return `<div class="lead-head"><div><h3>${esc(d.id)} · ${esc(d.name)}</h3><p class="caption">Weakest element: ${esc(wk || "—")} ${num(sc[wk], "", 2)}</p></div><div class="fig"><div class="v">${esc(fmt(d.gcos, 3))}</div><div class="k">GCoS · ${d.drilled ? "drilled" : "undrilled"}</div></div></div>
      ${scoreRows(d)}
      <dl class="facts">
        <dt>Area</dt><dd>${num(d.area_km2, "km²", 2)} · risked ${num(d.risked_area_km2, "km²", 2)}</dd>
        <dt>Shape</dt><dd>elongation ${num(sh.elongation, "", 2)} · sinuosity ${num(sh.sinuosity, "", 2)}</dd>
        <dt>Structure</dt><dd>closure ${num(st.closure_ms, "ms", 1)} · fault contact ${num(pct(d.fault_contact_frac), "%", 0)}</dd>
        <dt>Wells</dt><dd class="well-list">${wells}</dd>
        <dt>${simLabel}</dt><dd>${sim}</dd>
      </dl>
      <div class="ev-actions">
        <button type="button" class="btn btn-primary" data-ask="What is the geological opportunity here, and why?">Explain this lead</button>
        <button type="button" class="btn" data-ask="What could make ${esc(d.id)} wrong?">Ask what could go wrong</button>
        <button type="button" class="btn" data-ask="Find similar traps yet to be tested like ${esc(d.id)}">Find look-alikes</button>
      </div>`;
  }

  function devilTab(det) {
    const alts = det.alternatives || [], id = det.lead.id;
    if (!alts.length) return `<div class="empty">${icon("triangle-alert")}<h3>No alternatives flagged</h3><p>The engine raised no competing explanation for ${esc(id)}.</p></div>`;
    const cards = alts.map((x, i) => `<div class="card${i === 0 ? " card-risk" : i === 1 ? " card-tint" : ""}">
        <p class="card-head">${icon("triangle-alert")}<b>${esc(cap(x.risk))}</b></p>
        <p>${esc(x.alternative)}</p>
        <p class="run-in">De-risk</p><p>${esc(x.de_risk)}</p>
      </div>`).join("");
    return `<p class="caption">What could make ${esc(id)} wrong · ${plural(alts.length, "alternative", "alternatives")} from the engine’s flags</p>${cards}
      <div class="card"><p class="card-head">${icon("check")}<b>De-risk before drilling</b></p><ol class="derisk">${alts.map((x) => `<li>${esc(x.de_risk)}</li>`).join("")}</ol></div>`;
  }

  function similarTab(det) {
    const id = det.lead.id, rows = det.similar || [];
    const head = det.similar_pool === "drilled" ? `Closest drilled analogs for ${esc(id)} · ranked by similarity` : `Look-alikes for ${esc(id)} · ranked by similarity`;
    if (!rows.length) return `<p class="caption">${head}</p><div class="empty">${icon("search")}<h3>No look-alikes found</h3><p>No ${det.similar_pool === "drilled" ? "drilled" : "undrilled"} lead shares enough measured features with ${esc(id)}.</p></div>`;
    const list = rows.map((r) => {
      const s = isNum(r.similarity) ? r.similarity : 0, half = Math.round(Math.min(1, Math.abs(s)) * 500) / 10;
      const left = s >= 0 ? 50 : 50 - half;
      return `<li><button type="button" class="sim-row" data-lead="${esc(r.id)}" data-sim="${esc(s)}">
        <div><b>${esc(r.id)} · ${esc(r.name || "")}</b><div class="caption">${esc(r.trap_type || "—")} · ${esc(wellsSummary(r))}</div></div>
        <span class="bar sim-bar${s < 0 ? " is-neg" : ""}" aria-hidden="true"><i style="margin-inline-start:${left}%;width:${half}%"></i></span>
        <span class="num">${esc(signed(r.similarity))}</span></button></li>`;
    }).join("");
    return `<p class="caption">${head}</p><ol class="sim-list">${list}</ol><p class="caption">Cosine similarity on standardised features · 1 = identical · select a row to compare on the map</p>`;
  }

  // ------------------------------------------------------------------ executive mode
  function execBody() {
    const set = assumed();
    const leads = [...S.leads].sort((a, b) => (set ? emv(b) - emv(a) : (b.gcos || 0) - (a.gcos || 0)));
    const rows = leads.map((d) => {
      const e = emv(d), disc = (d.wells_inside || []).filter((n) => wellResult(n) === "discovery").length;
      const sub = d.drilled ? `Drilled · ${disc ? `${plural(disc, "discovery", "discoveries")} · appraise` : "dry · drop"}` : "Undrilled · candidate";
      return `<li><button type="button" class="emv-row" data-lead="${esc(d.id)}" aria-current="${d.id === S.sel}">
        <div><b>${esc(d.id)} · ${esc(d.name)}</b><div class="caption">${esc(sub)}</div></div>
        <span class="num secondary">${esc(fmt(pct(d.gcos), 0))} %</span>
        <span class="num emv ${e == null ? "faint" : e < 0 ? "bad" : "good"}">${esc(money(e))}</span></button></li>`;
    }).join("");
    // P5: the best undrilled lead as a hero card (CSS shows it on the phone only; desktop D7 keeps the plain list)
    const best = leads.find((d) => !d.drilled);
    const hero = best ? `<div class="exec-hero card card-tint"><p class="label secondary">Best undrilled bet</p><h3>${esc(best.id)} · ${esc(best.name)}</h3>
        <p class="num" style="font-size:1.75rem;line-height:1">${esc(money(emv(best)))}</p>
        <p class="caption">${esc(isNum(best.gcos) && best.gcos > 0 ? `about 1 in ${Math.round(1 / best.gcos)} odds` : "odds unknown")}${set ? ` · ${esc(money(S.assumptions.cost))} at risk · worth ${esc(money(S.assumptions.value))} if it works` : " · enter cost and value in the Business case panel"}</p></div>` : "";
    return `<div class="ev-head"><h3>Leads by expected value</h3><p class="caption num-sm">odds · EMV</p></div>${hero}<ol class="emv-list">${rows}</ol>
      <p class="caption">${set ? "EMV from your figures · dry-hole cost and value in the Business case panel" : "Enter dry-hole cost and value in the Business case panel to see EMV"}</p>`;
  }

  function renderBusiness(el) {
    EC.bottom?.head?.("Business case", "economics from your figures");
    bizEl = el;
    const a = S.assumptions || {};
    el.innerHTML = `<div class="view-business">
      <div class="assumptions">
        <div class="field"><label for="as-cost">Dry-hole cost (USD M)</label><input class="input" id="as-cost" type="number" inputmode="decimal" min="0" step="0.1" value="${isNum(a.cost) ? esc(a.cost) : ""}"></div>
        <div class="field"><label for="as-value">Value if it works (USD M)</label><input class="input" id="as-value" type="number" inputmode="decimal" min="0" step="0.1" value="${isNum(a.value) ? esc(a.value) : ""}"></div>
      </div>
      <div class="biz-stats">${bizStats()}</div>
    </div>`;
    const read = (id) => { const v = parseFloat(el.querySelector(`#${id}`)?.value); return Number.isFinite(v) && v >= 0 ? v : null; };
    el.addEventListener("input", (e) => {
      if (!e.target.matches("#as-cost, #as-value")) return;
      S.assumptions = { cost: read("as-cost"), value: read("as-value") };
      try { localStorage.setItem("ec-assumptions", JSON.stringify(S.assumptions)); } catch {}
      refreshBiz(); if (mode() === "executive") renderBody(); EC.map?.draw?.();
    });
    el.addEventListener("click", onClick);
  }
  function bizStats() {
    const d = leadNow();
    if (!d) return `<p class="caption">Pick a lead on the map to see its business case.</p>`;
    const sc = d.scorecard || {}, wk = weakest(sc), e = emv(d), set = assumed(), a = S.assumptions;
    const odds = isNum(d.gcos) && d.gcos > 0 ? d.gcos : null;
    return `<div class="stats">
      <div class="stat"><span class="label secondary">Chance of success</span><div class="fig">${odds ? `${pct(odds)} %` : "—"}</div><p class="caption">GCoS ${num(d.gcos, "", 3)}${odds ? ` · about 1 in ${Math.round(1 / odds)}` : ""}</p></div>
      <div class="stat"><span class="label secondary">Expected value</span><div class="fig${e == null ? "" : e < 0 ? " bad" : " good"}">${esc(money(e))}</div><p class="caption">${set ? "from your figures" : "enter cost and value"}</p></div>
      <div class="stat"><span class="label secondary">Area</span><div class="fig">${esc(fmt(d.area_km2, 2))} km²</div><p class="caption">risked ${num(d.risked_area_km2, "km²", 2)}</p></div>
      <div class="stat"><span class="label secondary">The one risk</span><div class="fig">${esc(cap(wk || "—"))}</div><p class="caption">P ${num(sc[wk], "", 2)}</p></div>
    </div>
    <div class="formula"><span class="label">EMV</span><span class="num-sm secondary">= odds × value if it works − (1 − odds) × dry-hole cost</span>
      ${set && odds ? `<span class="num-sm">${esc(d.id)}: ${esc(fmt(odds, 3))} × $${esc(nf.format(a.value))}M − ${esc(fmt(1 - odds, 3))} × $${esc(nf.format(a.cost))}M = ${esc(money(e))} · from your figures</span>` : ""}
    </div>`;
  }
  function refreshBiz() { const box = bizEl?.isConnected ? bizEl.querySelector(".biz-stats") : null; if (box) box.innerHTML = bizStats(); }

  // ------------------------------------------------------------------ blind well test
  const DISC_RE = /\b(gas|hydrocarbon|discovery)\b/i, DRY_RE = /\b(dry|water)\b/i;
  function predicted(text) {
    const t = String(text || ""), disc = DISC_RE.test(t), dry = DRY_RE.test(t);
    return disc && !dry ? "discovery" : dry && !disc ? "dry" : disc ? "discovery" : null;
  }
  const stepLabel = { hide: "Hide", predict: "Predict", reveal: "Reveal" };

  function blindBody() {
    const b = S.blind;
    if (!b) {
      const wells = S.wells.filter((w) => w.inside_survey !== false);
      return `<div class="ev-head"><h3>Blind well test</h3><p class="caption">Pick a drilled well to hide; the copilot then predicts what it found from the seismic alone.</p></div>
        <div class="well-choice">${wells.map((w) => `<button type="button" class="btn" data-act="hide" data-well="${esc(w.name)}">${icon("eye-off")}Hide ${esc(w.name)}</button>`).join("")}</div>
        <div><button type="button" class="btn btn-quiet" data-act="stop">Cancel</button></div>`;
    }
    const w = wellOf(b.well), t = b.prediction?.text || "", pred = predicted(t), revealed = b.step === "reveal";
    const lead = leadOfWell(b.well);
    const pending = b.step === "hide" ? "not yet asked" : t ? "—" : "waiting for the answer";
    const rows = [
      ["Reservoir", /\bsand\b/i.test(t) ? "sand" : /\b(shale|mud)\b/i.test(t) ? "shale" : pending,
        revealed ? (w?.attributes_at_well?.sand != null ? `sand probability ${fmt(w.attributes_at_well.sand, 3)} at the well` : "—") : "hidden"],
      ["Charge", pred === "discovery" ? "hydrocarbon" : pred === "dry" ? "dry" : pending, revealed ? w?.result_text || w?.result || "—" : "hidden"],
      ["Lead", (t.match(/\bL\d+\b/) || [])[0] || b.prediction?.lead || (t ? "—" : pending), revealed ? (lead ? `${lead.id} · ${lead.trap_type}` : "outside every lead") : "hidden"],
    ];
    return `<div class="ev-head"><h3>What was checked</h3><p class="caption">${esc(b.well)} · predicted vs ${revealed ? "revealed" : "hidden"}</p></div>
      <dl class="facts">${rows.map(([k, p, a]) => `<dt>${k}</dt><dd>predicted <b>${esc(p)}</b> · ${revealed ? "found" : "actual"} <span class="${revealed ? "" : "faint"}">${esc(a)}</span></dd>`).join("")}</dl>
      <p class="caption">The scorecard tabs return when the test ends.</p>`;
  }

  function renderBlind(el) {
    EC.bottom?.head?.(`Blind well test · ${esc(S.blind?.well || "")}`, "well removed from all evidence before predicting");
    blindEl = el;
    const b = S.blind;
    if (!b) { el.innerHTML = ""; return; }
    const w = wellOf(b.well), p = b.prediction;
    const mask = S.health?.hide_wells === true ? "" : `<p class="caption">UI mask only · the server has not confirmed it dropped this well from the model’s evidence</p>`;
    let cards = "";
    if (b.step === "hide") {
      cards = `<div class="card"><p class="card-head">${icon("eye-off")}<b>${esc(b.well)} is hidden</b></p>
        <p>Its result and the seismic values at the well are masked on the map, in the scorecard and in the well list until you reveal them. The copilot must predict from the surrounding seismic alone.</p>${mask}
        <div><button type="button" class="btn btn-primary" data-act="predict">Predict what it found</button></div></div>`;
    } else {
      const first = p ? plain(paragraphs(p.text)[0] || "") : "";
      const tags = (p?.cited || []).map((id) => `<span class="ev"><b>${esc(id)}</b>${esc(p.evidence?.[id]?.label || "")}</span>`).join("");
      cards = `<div class="card"><p class="label secondary">Copilot prediction · before reveal</p>
        ${p ? `<p>${esc(first)}</p>${tags ? `<div class="ev-row">${tags}</div>` : ""}` : `<p class="caption">Waiting for the copilot’s answer…</p>`}
        ${b.step === "predict" && p ? `<div><button type="button" class="btn btn-primary" data-act="reveal">Reveal the log</button></div>` : ""}</div>`;
      if (b.step === "reveal") {
        const pred = predicted(p?.text), actual = w?.result || null, agree = pred && actual && pred === actual;
        const cls = !pred || !actual ? "card" : agree ? "card card-good" : "card card-risk";
        const title = !pred ? "Prediction unclear" : !actual ? "Result not on record" : agree ? "Prediction confirmed" : "Prediction missed";
        const logs = w?.logs || {}, at = w?.attributes_at_well || {}, facts = [];
        if (isNum(logs.sand_fraction)) facts.push(`sand fraction ${num(logs.sand_fraction, "", 2)}`);
        if (isNum(logs.res_in_sand_p90)) facts.push(`resistivity ${num(logs.res_in_sand_p90, "Ω·m", 2)}${isNum(logs.res_in_shale_median) ? ` vs ${num(logs.res_in_shale_median, "Ω·m", 2)} shale` : ""}`);
        if (isNum(at.sand)) facts.push(`sand probability ${num(at.sand, "", 3)} at the well`);
        if (isNum(at.vpvs)) facts.push(`Vp/Vs ${num(at.vpvs, "", 3)}`);
        cards += `<div class="${cls}"><h3 class="card-head">${icon(agree ? "check" : "triangle-alert")}${title}</h3>
          <p><b>${esc(w?.result_text || actual || "—")}</b>${facts.length ? ` · ${facts.join(" · ")}` : ""}</p>
          <p class="caption">${icon("eye")} Revealed from the well store · ${esc(b.well)}${pred ? ` · predicted ${esc(pred)}` : ""}</p></div>`;
      }
    }
    el.innerHTML = `<div class="view-blind">
      <div class="blind-head"><div><h3>Blind well test · ${esc(b.well)}</h3><p class="caption">well removed from all evidence before predicting</p></div>
        <ol class="stepper">${["hide", "predict", "reveal"].map((s, i) => `<li${s === b.step ? ' aria-current="step"' : ""}><span class="num-sm">${i + 1}</span>${stepLabel[s]}</li>`).join("")}</ol></div>
      <div class="blind-cards">${cards}</div>
      <div><button type="button" class="btn btn-quiet" data-act="stop">${icon("x")}End blind test</button></div>
    </div>`;
    el.addEventListener("click", onClick);
  }
  function refreshBlind() { if (blindEl?.isConnected && S.blind) renderBlind(blindEl); else EC.bottom?.show?.("blind"); }
  function setPressed(on) { $("blind-btn")?.setAttribute("aria-pressed", String(on)); }

  const blind = {
    start(well) {
      if (!well || !wellOf(well)) { choosing = true; setPressed(true); renderTabs(); renderBody(); return; }
      choosing = false;
      S.blind = { well, step: "hide", prediction: null };
      setPressed(true);
      bus.emit("blind", { well, step: "hide" });
      renderTabs(); renderBody();
      EC.bottom?.show?.("blind");
    },
    predict() {
      const b = S.blind; if (!b) return;
      b.step = "predict"; b.prediction = null;
      refreshBlind(); renderBody();
      EC.chat?.ask?.(`Blind test: hide ${b.well} and predict what it found`);
    },
    reveal() {
      const b = S.blind; if (!b) return;
      b.step = "reveal";
      bus.emit("blind", { well: b.well, step: "reveal" });
      refreshBlind(); renderBody();
    },
    stop() {
      S.blind = null; choosing = false;
      setPressed(false);
      bus.emit("blind", null);
      renderTabs(); renderBody();
      EC.bottom?.show?.(S.audience === "executive" ? "business" : "section");
    },
  };

  // ------------------------------------------------------------------ committee memo
  function recommendation(text) {
    // Prefer an explicit "Recommendation: …" sentence, then a "Next step" paragraph; never the analog line.
    const flat = plain(text || "");
    const m = flat.match(/recommendation:\s*([^.\n]+)\./i);
    let out = "";
    if (m) out = m[1].trim();
    else {
      const ps = paragraphs(text);
      const i = ps.findIndex((p) => /^[\s*_#]*next step/i.test(p));
      if (i >= 0) out = plain((ps[i].replace(/^[\s*_#]*next step[^\n]*\n?/i, "").trim()) || ps[i + 1] || "");
    }
    out = out.charAt(0).toUpperCase() + out.slice(1);
    return out.length > 180 ? out.slice(0, 177).replace(/\s+\S*$/, "") + "…" : out;
  }
  function openMemo() {
    const dlg = $("memo"); if (!dlg) return;
    const d = leadNow(), det = cur.detail?.lead?.id === d?.id ? cur.detail : null;
    const m = S.meta || {}, block = m.block_id || "SK3XX (synthetic)";
    const date = new Intl.DateTimeFormat("en-MY", { day: "numeric", month: "short", year: "numeric" }).format(new Date());
    const actions = `<div class="memo-actions"><button type="button" class="btn btn-primary" data-act="print">${icon("printer")}Export memo</button><button type="button" class="btn btn-quiet btn-round" data-act="close" aria-label="Close memo">${icon("x")}</button></div>`;
    const overline = `<p class="label secondary">Committee memo · ${esc(block)} · ${esc(date)}</p>`;
    if (!d) {
      dlg.innerHTML = `<div class="memo-body"><div class="memo-top"><div>${overline}<h1 id="memo-h">No lead selected</h1></div>${actions}</div>
        <div class="empty">${icon("layers")}<p>Select a lead on the map, then open the memo.</p></div></div>`;
    } else {
      const sc = d.scorecard || {}, wk = weakest(sc), e = emv(d), set = assumed(), a = answerFor(d.id);
      const odds = isNum(d.gcos) && d.gcos > 0 ? d.gcos : null;
      const rec = a ? recommendation(a.text) : "";
      const alt = det?.alternatives?.[0];
      const tags = (a?.cited || []).map((id) => `<span class="ev"><b>${esc(id)}</b>${esc(a.evidence?.[id]?.label || "")}</span>`).join("");
      dlg.innerHTML = `<div class="memo-body">
        <div class="memo-top"><div>${overline}<h1 id="memo-h">Lead ${esc(d.id)}${/^lead\s*\d+$/i.test(d.name || "") ? "" : " · " + esc(d.name)}</h1></div>${actions}</div>
        <div class="card card-tint"><p class="label secondary">Recommendation</p>
          <p class="memo-rec">${esc(rec || "Ask the copilot to explain this lead first; the recommendation comes from its cited answer.")}</p>
          <span class="trap t-${esc(d.trap_type)}">${esc(d.trap_type || "Unclassified")}${d.subtype ? ` <span class="caption">· ${esc(d.subtype)}</span>` : ""}</span></div>
        <div class="stats">
          <div class="stat"><span class="label secondary">Chance of success</span><div class="fig">${odds ? `${pct(odds)} %` : "—"}</div><p class="caption">GCoS ${num(d.gcos, "", 3)}${odds ? ` · about 1 in ${Math.round(1 / odds)}` : ""}</p></div>
          <div class="stat"><span class="label secondary">Expected value</span><div class="fig${e == null ? "" : e < 0 ? " bad" : " good"}">${esc(money(e))}</div><p class="caption">${set ? "from your figures" : "enter figures in Executive mode"}</p></div>
          <div class="stat"><span class="label secondary">Area</span><div class="fig">${esc(fmt(d.area_km2, 2))} km²</div><p class="caption">risked ${num(d.risked_area_km2, "km²", 2)}</p></div>
          <div class="stat"><span class="label secondary">The one risk</span><div class="fig">${esc(cap(wk || "—"))}</div><p class="caption">P ${num(sc[wk], "", 2)}</p></div>
        </div>
        <div class="memo-cols">
          <div><h3>Petroleum system</h3>${scoreRows(d)}</div>
          <div><h3>Main risk and how to retire it</h3>${alt
            ? `<p><b>${esc(cap(alt.risk))}</b> — ${esc(alt.alternative)}</p><p class="run-in">De-risk</p><p>${esc(alt.de_risk)}</p>`
            : `<p class="caption">${det ? "The engine flagged no alternative for this lead." : "Load the lead’s evidence first; the main risk comes from its alternatives."}</p>`}</div>
        </div>
        <div class="memo-foot"><p class="run-in">Evidence</p>
          ${tags ? `<div class="ev-row">${tags}</div>` : `<p class="caption">No cited answer yet for ${esc(d.id)}.</p>`}
          <p class="caption">Generated by Exploration Copilot · every number traced to measured evidence · ${m.synthetic ? "synthetic survey" : esc(block)} · economics from your figures</p>
        </div></div>`;
    }
    if (typeof dlg.showModal === "function") { if (!dlg.open) dlg.showModal(); } else dlg.setAttribute("open", "");
  }
  function closeMemo() { const dlg = $("memo"); if (dlg?.open) dlg.close(); }

  // ------------------------------------------------------------------ delegated clicks
  function onClick(e) {
    const t = e.target.closest("[data-act],[data-ask],[data-well],[data-lead]"); if (!t) return;
    const act = t.dataset.act;
    if (act === "retry") return void EC.app?.selectLead(t.dataset.lead);
    if (act === "hide") return void blind.start(t.dataset.well);
    if (act === "predict") return void blind.predict();
    if (act === "reveal") return void blind.reveal();
    if (act === "stop") return void blind.stop();
    if (act === "print") return void window.print();
    if (act === "close") return void closeMemo();
    if (t.dataset.ask) return void EC.chat?.ask?.(t.dataset.ask);
    if (t.dataset.well) return void EC.app?.selectWell(t.dataset.well);
    if (t.dataset.lead) {
      const from = cur.id, to = t.dataset.lead;
      EC.app?.selectLead(to);
      if (t.dataset.sim != null && from && typeof EC.map?.link === "function") EC.map.link(from, to, Number(t.dataset.sim));
    }
  }

  // ------------------------------------------------------------------ init
  function registerViews(tries = 0) {
    if (!EC.bottom?.register) { if (tries < 20) setTimeout(() => registerViews(tries + 1), 50); return; }
    EC.bottom.register("business", { label: "Business case", icon: "file-text", when: () => S.audience === "executive", render: (el) => renderBusiness(el) });
    EC.bottom.register("blind", { label: "Blind test", icon: "eye-off", when: () => !!S.blind, render: (el) => renderBlind(el) });
    // Phone "Wells" tab: every well with its outcome and a blind-test entry point (never shown in the desktop toggle)
    EC.bottom.register("wells", { label: "Wells", icon: "database", when: () => !!EC.app?.isPhone?.() && !S.blind, render: (el) => {
      EC.bottom.head("Wells", `${plural(S.wells.length, "well", "wells")} in the survey`);
      const rows = S.wells.map((w) => {
        const inLead = S.leads.find((d) => (d.wells_inside || []).includes(w.name));
        return `<li class="card"><div class="card-head">${wellButton(w.name)}<span class="caption">${inLead ? `in ${esc(inLead.id)}` : "outside the leads"}</span></div>
          <p class="caption">${esc(w.result_text || "")}${w.inline != null ? ` · IL ${esc(w.inline)} · XL ${esc(w.crossline)}` : ""}</p>
          ${w.result ? `<button type="button" class="btn" data-blind="${esc(w.name)}">${icon("eye-off")}Hide ${esc(w.name)} and predict</button>` : ""}</li>`;
      }).join("");
      el.innerHTML = `<div class="view-blind"><ol class="sim-list">${rows}</ol></div>`;
      el.querySelector(".view-blind")?.addEventListener("click", (e) => {
        const b = e.target.closest("[data-blind]"); if (b) { blind.start(b.dataset.blind); return; }
        const w = e.target.closest("[data-well]"); if (w) EC.app?.selectWell?.(w.dataset.well);
      });
    } });
  }
  function init() {
    ({ $, esc, icon, fmt, num, plural } = EC.util); bus = EC.bus; S = EC.S;
    try {
      const a = JSON.parse(localStorage.getItem("ec-assumptions") || "null");
      if (a) S.assumptions = { cost: isNum(a.cost) ? a.cost : null, value: isNum(a.value) ? a.value : null };
    } catch {}
    registerViews();
    $("ev-tabs")?.addEventListener("keydown", onTabKey);
    $("ev-body")?.addEventListener("click", onClick);
    $("blind-btn")?.addEventListener("click", () => (S.blind || choosing ? blind.stop() : blind.start()));
    $("memo-btn")?.addEventListener("click", openMemo);
    const dlg = $("memo");
    if (dlg) { dlg.addEventListener("click", onClick); dlg.addEventListener("close", () => $("memo-btn")?.focus()); }
    bus.on("lead", (p) => { cur = { id: p?.id ?? null, detail: p?.detail || null, error: p?.error || null }; renderBody(); refreshBiz(); });
    bus.on("audience", () => { renderTabs(); renderBody(); EC.bottom?.show?.(S.blind ? "blind" : S.audience === "executive" ? "business" : "section"); });
    bus.on("blind", () => { setPressed(!!S.blind || choosing); renderTabs(); renderBody(); });
    bus.on("answer", (p) => {
      if (p) lastAnswer = p;
      const b = S.blind;
      if (b && b.step === "predict" && p?.text) { b.prediction = { text: p.text, cited: p.cited || [], lead: p.lead || null, evidence: p.evidence || {} }; refreshBlind(); renderBody(); }
    });
    cur = { id: S.sel, detail: S.detail?.lead?.id === S.sel ? S.detail : null, error: null };
    if (S.audience === "executive" && document.documentElement.getAttribute("data-audience") !== "executive") document.documentElement.setAttribute("data-audience", "executive");
    renderTabs(); renderBody();
  }

  EC.views = {
    init, setTab, openMemo, closeMemo, blind, emv,
    renderEvidence(detail) { cur = { id: detail?.lead?.id ?? S.sel ?? null, detail: detail || null, error: null }; renderBody(); refreshBiz(); },
  };
})();
