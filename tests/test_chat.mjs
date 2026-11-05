// Run: node --test tests/test_chat.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

function renderer(latestEvidence) {
  const esc = (value) => String(value ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const EC = { S: { evidence: latestEvidence }, util: { esc, fmt: String } };
  vm.runInNewContext(readFileSync(new URL("../frontend/js/chat.js", import.meta.url), "utf8"), { window: { EC } });
  return EC.chat.renderMd;
}

test("each answer renders its own E1 even after another answer reuses that label", () => {
  const first = { E1: { id: "E1", label: "L1 sand probability", value: 0.9 } };
  const second = { E1: { id: "E1", label: "L3 Vp/Vs", value: 1.745 } };
  const render = renderer(second);
  const html = render("The first lead has sand [E1].", first);
  assert.match(html, /Sand probability 0\.9/);
  assert.doesNotMatch(html, /Vp\/Vs/);
  assert.match(render("Second lead [E1].", second), /Vp\/Vs 1\.745/);
  assert.match(render("First answer again [E1].", first), /Sand probability 0\.9/);
});

test("answer evidence is used consistently in headings, paragraphs, lists and tables", () => {
  const render = renderer({ E1: { label: "Later measurement", value: 999 } });
  const evidence = { E1: { label: "Original measurement", value: 0.25 } };
  const html = render("# Evidence [E1]\n\nMeasured [E1].\n\n- Result [E1]\n\n| Fact |\n|---|\n| [E1] |", evidence);
  assert.equal((html.match(/Original measurement 0\.25/g) || []).length, 4);
  assert.doesNotMatch(html, /Later measurement|999/);
});

test("an absent citation cannot borrow a measurement from another answer", () => {
  const render = renderer({ E1: { label: "Unrelated measurement", value: 42 } });
  const html = render("Unknown citation [E1].", {});
  assert.doesNotMatch(html, /Unrelated measurement|42/);
});
