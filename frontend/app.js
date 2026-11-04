/* Exploration Copilot — boot and the contract between modules.
   Load order: js/api.js (also defines EC.util, EC.bus, EC.S), js/map.js, js/section.js, js/chat.js, js/views.js, app.js.

   Shared namespace window.EC:
     EC.api      — see js/api.js
     EC.S        — state (below). Modules read it; only the owners below write their slice.
     EC.util     — $, esc, fmt, num(), plural(), icon(), css()
     EC.bus      — tiny pub/sub: EC.bus.on("lead", fn) / EC.bus.emit("lead", payload)
       events: "meta" (boot data loaded) · "lead" ({id, detail}) · "well" ({name}) · "attr" (key)
               "fact" (an evidence item arrived in the stream) · "evidence" (item pinned by a tag click, or null = clear) · "audience" ("geoscientist"|"executive")
               "blind" ({well} | null) · "answer" ({cited, text, lead}) · "view" (name)
     Module owners:
       js/map.js      EC.map      { init(), draw(), setAttr(k), highlight(ref), focusPoint(i,j) }
       js/section.js  EC.bottom   { init(), show(name, payload), setLead(detail), setWell(well), setEvidence(item) }
       js/chat.js     EC.chat     { init(), ask(q), welcome(), banner(type, title, body), setSuggestions(lead, well) }
       js/views.js    EC.views    { init(), renderEvidence(detail), setTab(name), openMemo(), blind: {start(well), reveal(), stop()} }
   Every module must work when its DOM is missing (returns quietly) so the standalone file degrades. */
(() => {
  "use strict";
  const EC = (window.EC = window.EC || {});
  const { $, esc, css, icon, fmt, num, plural } = EC.util;
  const bus = EC.bus;

  // ------------------------------------------------------------------ theme + audience
  function setTheme(t) {
    const root = document.documentElement;
    root.classList.add("theme-switching");
    root.setAttribute("data-theme", t);
    void document.body.offsetHeight;
    requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("theme-switching")));
    try { localStorage.setItem("ec-theme", t); } catch {}
    const b = $("theme-btn");
    if (b) {
      b.setAttribute("aria-label", t === "dark" ? "Switch to light theme" : "Switch to dark theme");
      b.innerHTML = icon(t === "dark" ? "sun" : "moon");
    }
    EC.map?.draw();
  }
  function setAudience(a) {
    EC.S.audience = a;
    document.documentElement.toggleAttribute("data-audience", a === "executive");
    if (a === "executive") document.documentElement.setAttribute("data-audience", "executive");
    try { localStorage.setItem("ec-audience", a); } catch {}
    for (const b of $("audience")?.children || []) { const on = b.dataset.audience === a; b.setAttribute("aria-checked", String(on)); b.tabIndex = on ? 0 : -1; }
    bus.emit("audience", a);
  }

  // ------------------------------------------------------------------ boot
  async function boot() {
    $("theme-btn")?.addEventListener("click", () => setTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"));
    setTheme(document.documentElement.getAttribute("data-theme") || "dark");
    for (const b of $("audience")?.children || []) {
      b.tabIndex = b.dataset.audience === EC.S.audience ? 0 : -1;   // radiogroup: one tab stop, arrows move
      b.addEventListener("click", () => setAudience(b.dataset.audience));
      b.addEventListener("keydown", (e) => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { const n = b.dataset.audience === "executive" ? "geoscientist" : "executive"; setAudience(n); $("audience").querySelector(`[data-audience="${n}"]`).focus(); } });
    }
    matchMedia("(prefers-color-scheme: light)").addEventListener?.("change", (e) => { let stored = null; try { stored = localStorage.getItem("ec-theme"); } catch {} if (!stored) setTheme(e.matches ? "light" : "dark"); });

    try {
      [EC.S.meta, EC.S.wells, EC.S.leads] = await Promise.all([EC.api.json("/api/meta"), EC.api.json("/api/wells"), EC.api.json("/api/leads")]);
    } catch (e) {
      const w = $("welcome");
      if (w) w.querySelector(".hero").innerHTML = `<div class="error-inline"><b>Can't load the survey</b><p>${esc(e.message)}. Build the store with <code>MOCK=1 python -m engine.precompute</code>, start the server, then reload this page.</p></div>`;
      return;
    }
    const m = EC.S.meta;
    if ($("block-chip")) $("block-chip").textContent = m.block_id ? `Block ${m.block_id}${m.synthetic ? " · synthetic" : ""}` : `Block SK3XX · ${m.synthetic ? "synthetic" : "real data"}`;
    if ($("map-sub")) $("map-sub").textContent = `IL ${m.ilines[0]}–${m.ilines[1]} · XL ${m.xlines[0]}–${m.xlines[1]}`;
    if ($("map-window")) $("map-window").textContent = `Window ${m.window_ms[0]}–${m.window_ms[1]} ms`;

    EC.map?.init(); EC.bottom?.init(); EC.chat?.init(); EC.views?.init();
    health(); welcomeScreen(); phoneInit();
    const params = new URLSearchParams(location.search);
    const state = params.get("state");
    if (state) demoState(state);
    else if (params.get("lead")) enterWorkspace(params.get("lead"));
  }

  async function health() {
    const dot = $("health")?.querySelector(".dot"); const txt = $("health-text");
    if (!dot || !txt) return;
    try {
      const h = (EC.S.health = await EC.api.json("/api/health"));
      if (EC.api.standalone) { dot.className = "dot off"; txt.textContent = "Prototype · recorded answers"; return; }
      if (h.llm_mode === "gemma") {
        dot.className = "dot " + (h.llm_reachable ? "ok" : "bad");
        txt.textContent = h.llm_reachable ? "Gemma 4 connected" : "Gemma unreachable · offline reasoner";
        if (!h.llm_reachable) EC.chat?.banner("warning", "Gemma is unreachable, using the offline reasoner", "Same evidence, template wording. Answers say which reasoner wrote them.");
      } else { dot.className = "dot off"; txt.textContent = "Offline reasoner"; }
    } catch { dot.className = "dot bad"; txt.textContent = "Can't reach the server"; }
  }

  // ------------------------------------------------------------------ welcome (D1) → workspace
  function welcomeScreen() {
    const w = $("welcome"); if (!w) return;
    const m = EC.S.meta;
    $("welcome-bg").src = EC.api.mapUrl("sand");
    const undrilled = EC.S.leads.filter((d) => !d.drilled).length;
    const disc = m.calibration?.discovery?.n_wells ?? EC.S.wells.filter((x) => x.result === "discovery").length;
    const cells = [];
    if (m.n_volumes) cells.push([m.n_volumes, "seismic volumes"]);
    cells.push([EC.S.wells.length, `wells, ${plural(disc, "discovery", "discoveries")}`]);
    cells.push([EC.S.leads.length, "leads measured"]);
    cells.push([undrilled, plural(undrilled, "undrilled opportunity", "undrilled opportunities").replace(/^\d+\s/, ""), "acc"]);
    $("survey-stats").innerHTML = cells.map(([v, k, c]) => `<div><span class="v ${c || ""}">${esc(v)}</span><span class="k">${esc(k)}</span></div>`).join("");
    const dry = EC.S.wells.find((x) => x.result === "dry" && EC.S.leads.some((d) => d.wells_inside.includes(x.name)));
    const prompts = ["What is the geological opportunity, and why?", "Rank the leads", "Find similar traps yet to be tested"];
    if (dry) prompts.push(`Why did ${dry.name} come up dry?`);
    $("hero-prompts").innerHTML = prompts.map((q) => `<button type="button" class="btn">${esc(q)}</button>`).join("");
    for (const b of $("hero-prompts").children) b.addEventListener("click", () => { enterWorkspace(); EC.chat?.ask(b.textContent); });
    $("ask-hero").addEventListener("submit", (e) => { e.preventDefault(); const q = $("q-hero").value.trim(); if (!q) return; enterWorkspace(); EC.chat?.ask(q); });
  }
  function enterWorkspace(leadId) {
    const w = $("welcome"), s = $("shell");
    if (w && !w.hidden) { w.hidden = true; s.hidden = false; s.classList.add("enter"); EC.map?.draw(); }
    const first = leadId || EC.S.sel || (EC.S.leads.find((d) => !d.drilled) || EC.S.leads[0])?.id;
    if (first && EC.S.sel !== first) selectLead(first, { quiet: true });
    if (!EC.chat?.hasMessages()) EC.chat?.welcome();
  }

  // ------------------------------------------------------------------ selection
  async function selectLead(id, opts = {}) {
    EC.S.sel = id; EC.S.selWell = null;
    EC.map?.draw();
    bus.emit("lead", { id, detail: null });
    try {
      const det = await EC.api.json(`/api/leads/${id}`);
      if (EC.S.sel !== id) return;
      EC.S.detail = det;
      bus.emit("lead", { id, detail: det });
      EC.chat?.setSuggestions(id);
      if (!opts.quiet) { const p = document.querySelector(".panel-evidence"); p?.classList.add("is-updated"); setTimeout(() => p?.classList.remove("is-updated"), 1200); }
    } catch (e) {
      bus.emit("lead", { id, detail: null, error: `Couldn't load ${id} (${e.message}). Select it again to retry.` });
    }
  }
  function selectWell(name) {
    const w = EC.S.wells.find((x) => x.name === name); if (!w) return;
    EC.S.selWell = name;
    bus.emit("well", { well: w });
    EC.chat?.setSuggestions(EC.S.sel, name);
  }

  // ------------------------------------------------------------------ demo states (?state=...) for screenshots and the judges' walkthrough
  function demoState(name) {
    enterWorkspace();
    const map = {
      offline: () => EC.chat?.banner("warning", "Gemma is busy, using the offline reasoner", "Same evidence, template wording. Retrying in the background."),
      unreachable: () => { $("health").querySelector(".dot").className = "dot bad"; $("health-text").textContent = "Can't reach the server"; EC.chat?.banner("error", "Can't reach the server", "Check it is running, then reload this page."), $("send")?.setAttribute("aria-disabled", "true"); },
      refusal: () => EC.chat?.ask(`Is there oil at inline ${EC.S.meta.ilines[0] + 100}, crossline ${EC.S.meta.xlines[0] + 30}?`),
      empty: () => { EC.S.sel = null; EC.S.detail = null; EC.map?.draw(); bus.emit("lead", { id: null, detail: null }); },
      executive: () => setAudience("executive"),
      blind: () => EC.views?.blind.start(EC.S.wells.find((x) => x.result === "discovery")?.name),
      memo: () => EC.views?.openMemo(),
      imagefail: () => bus.emit("imagefail", true),
    };
    (map[name] || (() => {}))();
  }

  // ------------------------------------------------------------------ phone shell (≤ 600 px): tab bar, title block, sheet
  const phoneMq = matchMedia("(max-width: 600px)");
  const isPhone = () => phoneMq.matches;
  function phoneTitle() {
    const h = $("ptitle-h"), c = $("ptitle-c"); if (!h || !c) return;
    const m = EC.S.meta || {}, tab = document.documentElement.dataset.ptab || "map";
    const block = m.block_id ? `Block ${m.block_id}` : "Block SK3XX";
    const model = $("health-text")?.textContent || "";
    const attrLabel = $("attr-bar")?.querySelector('[aria-selected="true"]')?.textContent || "";
    const disc = m.calibration?.discovery?.n_wells ?? EC.S.wells.filter((x) => x.result === "discovery").length;
    const t = {
      map: [block, document.documentElement.dataset.pmap === "section" ? `Seismic section · ${EC.S.sel || ""}` : `Opportunity map · ${attrLabel.toLowerCase()}`],
      chat: ["Copilot", `${block} · ${model}`],
      leads: [EC.S.audience === "executive" ? "Leads by value" : "Leads", EC.S.sel ? `${EC.S.sel} selected · ${plural(EC.S.leads.length, "lead", "leads")}` : plural(EC.S.leads.length, "lead", "leads")],
      wells: [EC.S.blind ? "Blind test" : "Wells", EC.S.blind ? `${EC.S.blind.well} hidden from all evidence` : `${plural(EC.S.wells.length, "well", "wells")} · ${plural(disc, "discovery", "discoveries")}`],
    }[tab];
    h.textContent = t[0]; c.textContent = t[1];
  }
  function setPhoneTab(name) {
    const root = document.documentElement;
    root.dataset.ptab = name;
    for (const b of $("tabbar")?.children || []) { const on = b.dataset.ptab === name; if (on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); }
    if (name === "wells") EC.bottom?.show?.(EC.S.blind ? "blind" : "wells");
    else if (name === "map" && root.dataset.pmap === "section") EC.bottom?.show?.("section");
    phoneTitle();
    EC.map?.draw();
    const main = $("main"); if (main) main.scrollTop = 0; window.scrollTo(0, 0);
  }
  function phoneLayout() {
    const on = isPhone(), root = document.documentElement;
    $("tabbar").hidden = !on; $("ptitle").hidden = !on; $("sheet-actions").hidden = !on; $("pactions").hidden = !on;
    const pa = $("pactions"), actions = document.querySelector(".top .actions");
    if (on) { if (!root.dataset.ptab) root.dataset.ptab = "map"; pa.append($("blind-btn"), $("memo-btn")); }
    else { actions.append($("blind-btn"), $("memo-btn")); delete root.dataset.ptab; delete root.dataset.pmap; }
    EC.bottom?.show?.(EC.bottom.current?.());   // re-evaluates which views apply (the wells view is phone-only)
    phoneTitle(); EC.map?.draw();
  }
  function phoneInit() {
    for (const b of $("tabbar")?.children || []) b.addEventListener("click", () => setPhoneTab(b.dataset.ptab));
    $("sheet-ask")?.addEventListener("click", () => { setPhoneTab("chat"); EC.chat?.ask(EC.S.sel ? `What is the geological opportunity in ${EC.S.sel}, and why?` : "What is the geological opportunity, and why?"); });
    $("sheet-section")?.addEventListener("click", () => {
      const root = document.documentElement, on = root.dataset.pmap !== "section";
      if (on) root.dataset.pmap = "section"; else delete root.dataset.pmap;
      $("sheet-section").setAttribute("aria-pressed", String(on));
      $("sheet-section").lastChild.textContent = on ? "Map" : "Section";
      if (on) EC.bottom?.show?.("section"); phoneTitle(); EC.map?.draw();
    });
    bus.on("lead", phoneTitle); bus.on("attr", phoneTitle); bus.on("audience", phoneTitle); bus.on("blind", (p) => { phoneTitle(); if (isPhone() && p) setPhoneTab("wells"); });
    phoneMq.addEventListener?.("change", phoneLayout);
    phoneLayout();
  }

  EC.app = { selectLead, selectWell, enterWorkspace, setAudience, setTheme, setPhoneTab, isPhone };
  document.addEventListener("DOMContentLoaded", boot);
})();
