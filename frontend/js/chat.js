/* Exploration Copilot — chat: the streaming answer, its step trail, evidence chips and the evidence dialog.
   Owns EC.chat and writes EC.S.evidence, EC.S.lastAnswer and EC.S.busy.
   EC.util and EC.bus are created by api.js; bind lazily for the standalone renderer. */
(() => {
  "use strict";
  const EC = (window.EC = window.EC || {});
  let $, esc, icon, fmt, num, plural;
  const bind = () => { if (!esc && EC.util) ({ $, esc, icon, fmt, num, plural } = EC.util); return !!esc; };

  let form, qInput, sendBtn, log, statusEl, suggestEl, bannersEl, pop;
  let ctrl = null;          // AbortController of the answer being streamed
  let openChip = null;      // the .ev chip whose evidence dialog is open
  const messageEvidence = new WeakMap(); // each answer owns its E1, E2, ... references

  // ------------------------------------------------------------------ small formatters
  const EM = "em";          // built at runtime so the template never holds a literal italic tag
  const unitTxt = (u) => (u === "km2" ? "km²" : String(u || ""));
  /* Evidence values keep the decimals the engine wrote (1.745 stays 1.745, so chips agree with the prose). */
  const dpOf = (v) => { const s = String(v), i = s.indexOf("."); return i < 0 ? 0 : Math.min(3, s.length - i - 1); };
  const fmtVal = (v) => (typeof v === "number" ? (Math.abs(v) >= 1000 ? fmt(v) : fmt(v, dpOf(v))) : String(v ?? "—"));
  const valueText = (it) => `${fmtVal(it.value)}${it.unit ? " " + unitTxt(it.unit) : ""}`;
  const capFirst = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  /* "L3 sand probability inside vs around" → "Sand probability" (at most 24 characters). */
  function shortLabel(label) {
    let s = String(label || "").replace(/\s*\([^)]*\)/g, "").replace(/\binside (lead|vs around)\b/gi, "")
      .replace(/^L\d+\s+/, "").replace(/\s+/g, " ").trim();
    if (s.length > 24) { const cut = s.slice(0, 23); s = (cut.includes(" ") ? cut.slice(0, cut.lastIndexOf(" ")) : cut) + "…"; }
    return capFirst(s);
  }
  /* Lower-case everything after the first character except ids and acronyms (L3, IL, AVO, GCoS, Vp/Vs). */
  const sentenceCase = (s) => capFirst(s.trim()).split(" ").map((w, i) => (i && /^[A-Z][a-z]*$/.test(w) ? w.toLowerCase() : w)).join(" ");

  const chipHtml = (id, evidence) => {
    const it = evidence[id];
    const label = it ? `${shortLabel(it.label)} ${valueText(it)}` : "";
    return `<button type="button" class="ev" aria-expanded="false" data-id="${esc(id)}"><b>${esc(id)}</b>${esc(label)}</button>`;
  };

  // ------------------------------------------------------------------ markdown
  const NUM = /(?<![A-Za-z\-\d.])\d[\d,]*(?:\.\d+)?(?:\s?(?:km²|ms|sd|m|%|σ|Ω·m|API))?(?![A-Za-z²])/g;
  /* Plain prose: escape, wrap numbers, then bold and emphasis. Never sees chips or code. */
  const prose = (t) => esc(t)
    .replace(NUM, (m) => `<span class="num">${m}</span>`)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, `$1<${EM}>$2</${EM}>`);
  /* Code spans and [E12] tags are cut out first so their digits are never wrapped. */
  function inline(s, evidence) {
    const re = /`([^`]+)`|\[(E\d+)\]/g; let out = "", last = 0, m;
    while ((m = re.exec(s))) { out += prose(s.slice(last, m.index)) + (m[1] != null ? `<code>${esc(m[1])}</code>` : chipHtml(m[2], evidence)); last = re.lastIndex; }
    return out + prose(s.slice(last));
  }
  const runIn = (t, evidence) => `<p class="run-in">${inline(sentenceCase(t), evidence)}</p>`;
  function paragraph(text, evidence) {
    const h = text.match(/^#{1,6}\s+(.+?)\s*#*$/);
    if (h) return runIn(h[1], evidence);
    const b = text.match(/^\*\*([^*]+?)\*\*\s*(?:[-–—]\s*([\s\S]+))?$/);
    if (b && b[1].trim().split(/\s+/).length <= 6 && !/[.:;]$/.test(b[1].trim())) return runIn(b[1], evidence) + (b[2] ? `<p>${inline(capFirst(b[2].trim()), evidence)}</p>` : "");
    return `<p>${inline(text, evidence)}</p>`;
  }
  function renderMd(src, evidence = EC.S.evidence) {
    const lines = String(src || "").split("\n"); let out = "", i = 0;
    const isList = (l) => /^\s*[-*] /.test(l) || /^\s*\d+\. /.test(l);
    const isHead = (l) => /^\s*#{1,6}\s+/.test(l) || /^\s*\*\*[^*]+\*\*\s*$/.test(l);
    while (i < lines.length) {
      const l = lines[i];
      if (/^\s*\|/.test(l)) {
        const rows = []; while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
        const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const body = rows.filter((r, k) => !(k === 1 && /^[\s|:-]+$/.test(r)));
        out += `<div class="tw"><table><thead><tr>${cells(body[0]).map((c) => `<th>${inline(c, evidence)}</th>`).join("")}</tr></thead><tbody>` +
          body.slice(1).map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c, evidence)}</td>`).join("")}</tr>`).join("") + "</tbody></table></div>";
      } else if (isList(l)) {
        const ordered = /^\s*\d+\. /.test(l); const items = [];
        while (i < lines.length && isList(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.) /, ""));
        out += `<${ordered ? "ol" : "ul"}>${items.map((t) => `<li>${inline(t, evidence)}</li>`).join("")}</${ordered ? "ol" : "ul"}>`;
      } else if (l.trim() === "") { i++; }
      else {
        const para = [];
        if (isHead(l)) para.push(lines[i++].trim());   // a heading line is its own block even without blank lines around it
        else while (i < lines.length && lines[i].trim() !== "" && !isList(lines[i]) && !/^\s*\|/.test(lines[i]) && !isHead(lines[i])) para.push(lines[i++].trim());
        out += paragraph(para.join(" "), evidence);
      }
    }
    return out;
  }

  // ------------------------------------------------------------------ log helpers
  const nearBottom = () => !log || log.scrollHeight - log.scrollTop - log.clientHeight < 48;
  const scrollDown = () => { if (log) log.scrollTop = log.scrollHeight; };
  function announce(text) {
    if (!statusEl) return;
    statusEl.textContent = "";
    setTimeout(() => { statusEl.textContent = text; }, 60);
  }
  function setBusy(on) {
    EC.S.busy = on;
    form?.classList.toggle("is-busy", on);
    if (sendBtn) { sendBtn.innerHTML = icon(on ? "square" : "arrow-up"); sendBtn.setAttribute("aria-label", on ? "Stop" : "Ask"); }
    for (const b of suggestEl?.children || []) b.setAttribute("aria-disabled", String(on));
  }

  // ------------------------------------------------------------------ ask
  async function ask(question) {
    if (!bind() || !log) return;
    const q = String(question || "").trim();
    if (!q || EC.S.busy) return;
    const selectedLead = EC.S.sel;
    const evidence = {};
    EC.S.evidence = evidence; // compatibility lookup for the current answer only
    setBusy(true);
    const stick = nearBottom();
    const u = document.createElement("div"); u.className = "msg msg-user"; u.textContent = q; log.append(u);
    const b = document.createElement("div"); b.className = "msg msg-bot";
    messageEvidence.set(b, evidence);
    const lead = EC.S.detail?.lead?.id === EC.S.sel ? EC.S.detail.lead : null;   // phone answer card head (CSS shows it ≤ 600 px)
    const head = lead ? `<div class="answer-head"><span class="trap t-${esc(lead.trap_type)}">${esc(lead.trap_type)}</span><span class="num-sm secondary">GCoS ${esc(fmt(lead.gcos, 3))}</span></div>` : "";
    b.innerHTML = head + `<details class="trail" open><summary>${icon("chevron-down")}<span>How this answer is built</span></summary><ol class="steps"></ol></details>` +
      `<div class="md"><p class="secondary">Reading the survey…</p></div>` +
      `<div data-facts hidden><p class="caption">Facts so far</p><div class="ev-row"></div></div><div class="done-line"></div>`;
    log.append(b);
    if (stick) scrollDown();
    const trail = b.querySelector("details.trail"), summary = trail.querySelector("summary span"), steps = trail.querySelector(".steps");
    const md = b.querySelector(".md"), facts = b.querySelector("[data-facts]"), evRow = facts.querySelector(".ev-row"), doneLine = b.querySelector(".done-line");
    let text = "", pending = false, nSteps = 0, seen = [], active = null, finished = false;
    const paint = () => { pending = false; if (!text && !finished) return; const s = nearBottom(); md.innerHTML = renderMd(text, evidence); if (s) scrollDown(); };
    const markDone = (li) => { if (li.className === "is-error") return; li.className = "is-done"; li.querySelector(".ind").innerHTML = icon("check"); };
    const finishSteps = () => { for (const li of steps.children) markDone(li); active = null; };
    const opts = { audience: EC.S.audience };
    if (EC.S.blind?.well) opts.hideWells = [EC.S.blind.well];
    ctrl = new AbortController(); opts.signal = ctrl.signal;
    try {
      for await (const ev of EC.api.chat(q, selectedLead, opts)) {
        if (ev.type === "status") {
          if (!text) md.innerHTML = `<p class="secondary">${esc(ev.text)}…</p>`;
        } else if (ev.type === "tool") {
          const n = ev.evidence_ids?.length || 0;
          if (active) markDone(active);
          const li = document.createElement("li"); li.className = ev.error ? "is-error" : "is-active"; nSteps++;
          li.innerHTML = `<span class="ind">${ev.error ? icon("triangle-alert") : ""}</span><span class="why">${esc(capFirst(ev.why || ev.name || "Looked at the data"))}</span>` +
            `<span class="what">${esc(ev.name || "tool")} · ${ev.error ? esc(ev.error) : esc(plural(n, "fact", "facts"))}</span>`;
          const s = nearBottom(); steps.append(li); active = ev.error ? null : li;
          if (s) scrollDown();
        } else if (ev.type === "evidence") {
          const s = nearBottom();
          for (const it of ev.items || []) {
            if (!it?.id) continue;
            evidence[it.id] = it; seen.push(it.id);
            evRow.insertAdjacentHTML("beforeend", chipHtml(it.id, evidence));
            EC.bus.emit("fact", it);   // arrival: stored and listed, never pins the map (a click on the tag does that)
          }
          if (ev.items?.length) facts.hidden = false;
          if (s) scrollDown();
        } else if (ev.type === "token") {
          if (!text) finishSteps();
          text += ev.text;
          if (!pending) { pending = true; requestAnimationFrame(paint); }
        } else if (ev.type === "reset") {
          /* The model stopped partway: drop its half answer so the replacement is the only one shown. */
          text = ""; pending = false;
          md.innerHTML = `<p class="secondary">${esc(ev.text || "Rewriting the answer")}…</p>`;
        } else if (ev.type === "done") {
          finished = true; paint(); finishSteps();
          trail.removeAttribute("open"); summary.textContent = `How this answer was built · ${plural(nSteps, "step", "steps")}`;
          if (!nSteps) trail.hidden = true;
          facts.querySelector(".caption").textContent = plural(seen.length, "fact measured", "facts measured");
          b.querySelector("details.trail")?.append(facts);   // the answer cites inline; the full list folds into the trail
          const cited = ev.cited || [], bad = ev.unverified_numbers || [];
          if (bad.length) doneLine.insertAdjacentHTML("beforebegin",
            `<div class="unverified" role="status">${icon("triangle-alert")}<div><b>${esc(plural(bad.length, "number isn’t", "numbers aren’t"))} in the evidence: ${esc(bad.join(", "))}</b><br>Check them before using this answer.</div></div>`);
          doneLine.innerHTML = `<span>${esc(cited.length)} of ${esc(plural(seen.length, "evidence item", "evidence items"))} cited</span>` +
            `<span>${ev.mode === "gemma" ? "Gemma 4" : "Offline reasoner"}${ev.cached ? " · recorded answer" : ""}</span><span>${num(ev.seconds, "s", 1)}</span>${ev.note ? `<span>${esc(ev.note)}</span>` : ""}`;
          announce(`Answer ready. ${plural(cited.length, "evidence item", "evidence items")} cited` + (bad.length ? `, ${plural(bad.length, "number", "numbers")} not in the evidence.` : "."));
          EC.S.lastAnswer = { text, cited, lead: ev.lead === undefined ? selectedLead : ev.lead, evidence: { ...evidence } };
          EC.bus.emit("answer", EC.S.lastAnswer);
          if (nearBottom()) scrollDown();
        }
      }
    } catch (e) {
      finishSteps();
      if (e?.name === "AbortError") {
        if (text) paint(); else md.innerHTML = "";
        doneLine.innerHTML = `<span>Stopped before the answer finished</span>`;
      } else {
        md.innerHTML = `<p>Couldn’t get an answer: ${esc(e?.message || e)}. Check the server is running, then try again.</p>`;
      }
      if (qInput && !qInput.value) qInput.value = q;
    } finally {
      if (!finished && trail.hasAttribute("open") && !nSteps) trail.hidden = true;
      ctrl = null; setBusy(false);
    }
  }

  // ------------------------------------------------------------------ evidence dialog
  function cmpRows(it) {
    const key = it.ref?.map, cal = EC.S.meta?.calibration;
    if (it.compare == null || typeof it.value !== "number" || typeof it.compare !== "number" || !key) return "";
    const disc = cal?.discovery?.[key], dry = cal?.dry?.[key];
    if (typeof disc !== "number" || typeof dry !== "number") return "";
    const closerToDisc = Math.abs(it.value - disc) <= Math.abs(it.value - dry);
    const rows = [["Measured", it.value, closerToDisc ? "good" : "bad"], ["Around", it.compare, ""], ["Discovery avg", disc, "good"], ["Dry-well avg", dry, "bad"]];
    const max = Math.max(...rows.map((r) => Math.abs(r[1]))) || 1;
    return rows.map(([label, v, cls]) =>
      `<span>${label}</span><span class="track ${cls}"><i style="width:${Math.round((Math.abs(v) / max) * 100)}%"></i></span><span class="num-sm">${esc(fmtVal(v))}</span>`).join("");
  }
  function placePop(chip) {
    const r = chip.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    const left = Math.max(16, Math.min(r.left, innerWidth - w - 16));
    let top = r.bottom + 6;
    if (top + h > innerHeight - 8) top = Math.max(8, r.top - 6 - h);
    pop.style.left = `${Math.round(left)}px`; pop.style.top = `${Math.round(top)}px`; pop.style.right = "auto";
  }
  function openPop(chip) {
    if (!pop || !bind()) return;
    const it = messageEvidence.get(chip.closest(".msg-bot"))?.[chip.dataset.id];
    if (!it) return;
    if (openChip === chip && pop.open) { closePop(); return; }
    if (pop.open) closePop(false);
    const ref = it.ref || {}, mapLabel = ref.map ? EC.S.meta?.maps?.[ref.map]?.label || ref.map : "lead_evidence";
    $("evpop-id").textContent = it.id;
    $("evpop-src").textContent = ref.lead ? `${ref.lead} · ${mapLabel}` : mapLabel;
    $("evpop-h").textContent = it.label || it.id;
    $("evpop-val").innerHTML = esc(valueText(it)) + (it.compare != null ? ` <span class="secondary">vs ${esc(fmtVal(it.compare))}</span>` : "");
    $("evpop-cmp").innerHTML = cmpRows(it);
    $("evpop-note").textContent = it.note || "";
    $("evpop-note").hidden = !it.note;
    pop.show(); placePop(chip);
    chip.setAttribute("aria-expanded", "true"); openChip = chip;
    EC.bus.emit("evidence", it);
  }
  function closePop(refocus = true) {
    if (!pop?.open) return;
    pop.close();
    const chip = openChip; openChip = null;
    chip?.setAttribute("aria-expanded", "false");
    if (refocus && chip?.isConnected) chip.focus();
    EC.bus.emit("evidence", null);
  }

  // ------------------------------------------------------------------ banners, welcome, suggestions
  function banner(type, title, body) {
    if (!bind() || !bannersEl) return () => {};
    const existing = [...bannersEl.children].find((el) => el.dataset.title === title);
    if (existing) return () => existing.remove();
    const el = document.createElement("div");
    el.className = `banner${type === "error" ? " banner-error" : ""}`;
    el.setAttribute("role", type === "error" ? "alert" : "status");
    el.dataset.title = title;
    el.innerHTML = `${icon("triangle-alert")}<div><b>${esc(title)}</b><span class="caption">${esc(body || "")}</span></div>`;
    bannersEl.prepend(el);
    return () => el.remove();
  }
  const clearBanners = () => { if (bannersEl) bannersEl.innerHTML = ""; };

  function welcome() {
    if (!bind() || !log) return;
    const m = document.createElement("div"); m.className = "msg msg-bot";
    m.innerHTML = `<div class="md"><p>I measured ${esc(plural(EC.S.leads.length, "lead", "leads"))} around ${esc(plural(EC.S.wells.length, "well", "wells"))} in this survey. ` +
      `Ask what the opportunity is, why a well failed, or which untested traps look like a discovery; tags like <code>E3</code> open the measurement behind each claim.</p></div>`;
    log.append(m); scrollDown();
  }
  const hasMessages = () => !!log?.children.length;

  function setSuggestions(lead, well) {
    if (!bind() || !suggestEl) return;
    const S = EC.S;
    const dry = S.wells.find((w) => w.result === "dry" && S.leads.some((d) => (d.wells_inside || []).includes(w.name)));
    const qs = [];
    if (well) {
      const result = S.wells.find((w) => w.name === well)?.result;
      qs.push(result === "dry" ? `Why did ${well} come up dry?` : result === "discovery" ? `Why did ${well} succeed?` : `What is known about ${well}?`);
    }
    qs.push(lead ? "What is the geological opportunity here, and why?" : "What is the geological opportunity, and why?");
    if (lead) qs.push(`What could make ${lead} wrong?`);
    qs.push("Find similar traps yet to be tested");
    if (!well && dry) qs.push(`Why did ${dry.name} come up dry?`);
    qs.push("Rank the leads");
    suggestEl.innerHTML = qs.slice(0, 4).map((q) => `<button type="button" class="btn" aria-disabled="${S.busy}">${esc(q)}</button>`).join("");
  }

  // ------------------------------------------------------------------ init
  function init() {
    if (!bind()) return;
    form = $("ask"); qInput = $("q"); sendBtn = $("send"); log = $("log");
    statusEl = $("chat-status"); suggestEl = $("suggest"); bannersEl = $("banners"); pop = $("evpop");
    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      if (EC.S.busy) return;                       // keep the typed text until the answer finishes
      const q = qInput?.value.trim();
      if (!q) return;
      qInput.value = ""; ask(q);
    });
    sendBtn?.addEventListener("click", (e) => { if (EC.S.busy) { e.preventDefault(); ctrl?.abort(); } });
    suggestEl?.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b || EC.S.busy) return;
      ask(b.textContent);
    });
    document.addEventListener("click", (e) => {
      const chip = e.target.closest(".ev[data-id]");
      if (chip) { e.preventDefault(); openPop(chip); return; }
      if (e.target.closest("[data-close]") && e.target.closest("#evpop")) { closePop(); return; }
      if (pop?.open && !e.target.closest("#evpop")) closePop(false);
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && pop?.open) { e.preventDefault(); closePop(); } });
    pop?.addEventListener("cancel", (e) => { e.preventDefault(); closePop(); });
    window.addEventListener("resize", () => { if (pop?.open && openChip?.isConnected) placePop(openChip); });
    EC.bus.on("lead", (p) => setSuggestions(p?.id, EC.S.selWell));
    EC.bus.on("well", (p) => setSuggestions(EC.S.sel, p?.well?.name));
  }

  EC.chat = { init, ask, welcome, hasMessages, banner, clearBanners, setSuggestions, renderMd: (src, evidence) => (bind() ? renderMd(src, evidence) : "") };
})();
