/* Exploration Copilot — API layer.
   Talks to the FastAPI backend (/api/...). When window.__STANDALONE__ is set (the clickable
   prototype built by build_standalone.py) the same calls read embedded data and replay answers.
   Everything attaches to window.EC so the files load as plain scripts (file:// safe). */
(() => {
  "use strict";
  const EC = (window.EC = window.EC || {});
  const SA = window.__STANDALONE__ || null;

  async function json(path) {
    if (SA) {
      if (path === "/api/meta") return SA.meta;
      if (path === "/api/wells") return SA.wells;
      if (path === "/api/leads") return SA.leads;
      if (path === "/api/health") return SA.health;
      const m = path.match(/^\/api\/leads\/(\w+)/);
      if (m) return SA.details[m[1]];
      throw new Error(`${path}: not recorded in the prototype`);
    }
    const r = await fetch(path);
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return r.json();
  }

  const mapUrl = (name) => (SA ? SA.maps[name] : `/api/map/${name}.png`);
  const renderUrl = (name) => (SA ? (SA.renders || {})[name] || null : `/api/render/${name}.png`);
  function sectionUrl(il) {
    if (!SA) return `/api/section.png?inline=${il}`;
    const keys = Object.keys(SA.sections).map(Number);
    const k = keys.reduce((a, b) => (Math.abs(b - il) < Math.abs(a - il) ? b : a), keys[0]);
    return SA.sections[k];
  }

  /* Streams {type, ...} events: status, tool, evidence, token, done. `opts.signal` aborts. */
  async function* chat(message, lead, opts = {}) {
    if (SA) { yield* replay(message, lead); return; }
    const body = { message, selected_lead: lead };
    if (opts.hideWells?.length) body.hide_wells = opts.hideWells;
    if (opts.audience) body.audience = opts.audience;
    const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: opts.signal });
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
  }

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

  // ---- shared helpers, event bus and state (defined here because this file loads first)
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const icon = (name, cls = "") => `<svg class="icon ${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const fmt = (v, dp) => {
    if (v == null || Number.isNaN(Number(v))) return "—";
    const a = Math.abs(v);
    if (dp != null) return Number(v).toFixed(dp);
    return a >= 1000 ? Math.round(v).toLocaleString("en-MY") : a >= 10 ? Number(v).toFixed(1) : Number(v).toFixed(2);
  };
  /* A number with its unit, always in mono. */
  const num = (v, unit = "", dp) => `<span class="num">${esc(fmt(v, dp))}${unit ? " " + esc(unit) : ""}</span>`;
  const pr = new Intl.PluralRules("en");
  const plural = (n, one, other) => `${n.toLocaleString("en-MY")} ${pr.select(n) === "one" ? one : other}`;

  const listeners = {};
  const bus = {
    on: (ev, fn) => ((listeners[ev] = listeners[ev] || []).push(fn), fn),
    emit: (ev, payload) => { for (const fn of listeners[ev] || []) { try { fn(payload); } catch (e) { console.error(ev, e); } } },
  };

  EC.util = { $, esc, css, icon, fmt, num, plural };
  EC.bus = bus;
  EC.S = {
    meta: null, wells: [], leads: [], health: null,
    attr: "sand", sel: null, detail: null, selWell: null,
    evidence: {},               // id -> evidence item from the current answer; earlier messages own theirs
    audience: document.documentElement.getAttribute("data-audience") === "executive" ? "executive" : "geoscientist",
    blind: null,                // { well, step: "hide"|"predict"|"reveal", prediction }
    assumptions: { cost: null, value: null },   // USD M, from the asset team (Executive mode)
    lastAnswer: null,           // { text, cited, lead, evidence }
    busy: false,
  };


  EC.api = { json, mapUrl, renderUrl, sectionUrl, chat, standalone: !!SA };
})();
