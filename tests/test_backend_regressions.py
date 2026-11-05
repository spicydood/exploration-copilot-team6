"""Regression checks using a fresh synthetic store; no HPC data or model needed.

Run: python -m unittest discover -s tests -p "test_*.py" -v
"""
from __future__ import annotations

import importlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["MOCK"] = "1"

import numpy as np
from fastapi.testclient import TestClient

import config
from backend import llm
from backend.agent import Agent, is_ranking
from backend.render import section_png
from backend.store import InvalidLocationError, Store
from engine import leads, mock_data, precompute
from engine.outcomes import classify_result
from backend.validation import check_answer


class BackendRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="copilot-tests-")
        root = Path(cls.temp.name)
        volumes, _ = mock_data.build()
        inputs = mock_data.write_well_files(root / "inputs")
        cls.store_root = root / "store"
        precompute.run(volumes, inputs, cls.store_root, 1930, 2080,
                       leads.Params(), None, synthetic=True)
        # Import the API against this fixture, even if the caller configured a real store.
        with patch.object(config, "STORE_DIR", cls.store_root):
            cls.api = importlib.import_module("backend.app")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.store = Store(self.store_root)
        self.agent = Agent(self.store, mode="offline")

    def tearDown(self):
        # Windows cannot remove a fixture while a cached cube is memory-mapped.
        for key in ("cube_full", "cube_sand"):
            cube = self.store.__dict__.pop(key, None)
            if isinstance(cube, np.memmap):
                cube._mmap.close()

    def chat(self, question, selected=None):
        with patch.object(self.api, "store", self.store), \
                patch.object(self.api, "agent", self.agent), \
                patch.object(self.api, "CACHE_ON", False):
            response = TestClient(self.api.app).post(
                "/api/chat", json={"message": question, "selected_lead": selected})
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line[6:]) for line in response.text.splitlines()
                  if line.startswith("data: ")]
        return events

    def test_ranking_ignores_selection(self):
        for selected in (None, "L1", "L3", "L999"):
            with self.subTest(selected=selected):
                result = self.agent.answer("Rank the leads", selected)
                self.assertEqual(result["tools"], ["get_leads"])
                self.assertIn("| Lead | Trap |", result["text"])
                rows = [line for line in result["text"].splitlines() if re.match(r"^\| L\d+ \|", line)]
                self.assertEqual(len(rows), len(self.store.leads))
                for row, lead in zip(rows, self.store.leads):
                    self.assertTrue(row.startswith(f"| {lead['id']} |"))

    def test_ranking_filters_undrilled_and_respects_limit(self):
        result = self.agent.answer("Rank the top three undrilled opportunities", "L1")
        self.assertEqual(result["tools"], ["get_leads"])
        rows = [line for line in result["text"].splitlines() if re.match(r"^\| L\d+ \|", line)]
        expected = [lead for lead in self.store.leads if not lead["drilled"]][:3]
        self.assertEqual(len(rows), len(expected))
        self.assertTrue(all(row.startswith(f"| {lead['id']} |") for row, lead in zip(rows, expected)))

    def test_ranking_respects_top_two_and_trap_filter(self):
        result = self.agent.answer("Rank the top 2 structural leads", "L3")
        rows = [line for line in result["text"].splitlines() if re.match(r"^\| L\d+ \|", line)]
        expected = [lead for lead in self.store.leads if lead["trap_type"] == "Structural"][:2]
        self.assertEqual(len(rows), len(expected))
        self.assertTrue(all("| Structural |" in row for row in rows))

    def test_ranking_does_not_use_model_planner(self):
        self.agent.mode = "gemma"
        with patch.object(llm, "chat") as planner, \
                patch.object(llm, "stream", return_value=iter(["Ranked results"])):
            result = self.agent.answer("Rank the leads", "L3")
        planner.assert_not_called()
        self.assertEqual(result["tools"], ["get_leads"])

    def test_top_seal_is_not_a_ranking_request(self):
        self.assertFalse(is_ranking("What is the top seal for L3?"))
        self.assertFalse(is_ranking("List the risks for L3"))
        self.assertFalse(is_ranking("Rank similar traps to L1"))

    def test_selected_opportunity_still_uses_selected_evidence(self):
        result = self.agent.answer("What is the opportunity here?", "L3")
        self.assertIn("lead_evidence", result["tools"])
        self.assertTrue(result["text"].startswith("**Opportunity** - L3"))

    def test_valid_grid_edges_resolve_exactly(self):
        for axis, lookup in (("il", self.store.il_index), ("xl", self.store.xl_index)):
            values = self.store.meta[f"{axis}_values"]
            self.assertEqual(lookup(values[0]), 0)
            self.assertEqual(lookup(values[-1]), len(values) - 1)

    def test_outside_grid_does_not_snap_to_an_edge(self):
        for lookup, value in ((self.store.il_index, 999999), (self.store.il_index, -1),
                              (self.store.xl_index, 999999), (self.store.xl_index, -1)):
            with self.subTest(value=value), self.assertRaisesRegex(InvalidLocationError, "outside"):
                lookup(value)

    def test_missing_grid_number_does_not_snap_to_a_neighbour(self):
        self.store.meta["il_values"] = [1000, 1002, 1004]
        with self.assertRaisesRegex(InvalidLocationError, "not present"):
            self.store.il_index(1001)

    def test_fractional_and_nonfinite_coordinates_are_rejected(self):
        for value in (1000.5, "1000.5", float("nan"), float("inf"), True, "unknown"):
            with self.subTest(value=value), self.assertRaises(InvalidLocationError):
                self.store.il_index(value)

    def test_invalid_point_tool_returns_no_measurement(self):
        result = self.agent.tools.run("value_at", {"inline": 999999, "crossline": 2000})
        self.assertIn("outside", result["error"])
        self.assertEqual(result["evidence"], [])
        self.assertNotIn("result", result)

    def test_missing_trace_returns_no_measurement(self):
        sand = self.store.map("sand").copy()
        sand[0, 0] = np.nan
        self.store._maps["sand"] = sand
        result = self.agent.tools.run("value_at", {"inline": 1000, "crossline": 2000})
        self.assertIn("No survey data", result["error"])
        self.assertEqual(result["evidence"], [])

    def test_valid_point_preserves_actual_coordinate_and_value(self):
        result = self.agent.tools.value_at("1000", "2000")
        self.assertIn("IL 1000 / XL 2000", result["evidence"][0]["label"])
        self.assertEqual(result["result"]["values"]["sand"], round(float(self.store.map("sand")[0, 0]), 3))

    def test_invalid_location_chat_completes_without_citations(self):
        for coordinate in ("999999", "-1", "1000.5"):
            with self.subTest(coordinate=coordinate):
                events = self.chat(f"Is there oil at inline {coordinate}, crossline 2000?", "L3")
                text = "".join(event["text"] for event in events if event["type"] == "token")
                self.assertIn("Location unavailable", text)
                self.assertIn("No measurement was returned", text)
                self.assertEqual(next(event["items"] for event in events if event["type"] == "evidence"), [])
                self.assertEqual(events[-1]["type"], "done")
                self.assertEqual(events[-1]["cited"], [])
                self.assertEqual(events[-1]["unverified_numbers"], [])

    def test_metadata_preserves_grid_coordinates_for_frontend_labels(self):
        self.store.meta["il_values"] = [1000, 1002, 1004]
        with patch.object(self.api, "store", self.store):
            response = TestClient(self.api.app).get("/api/meta")
        self.assertEqual(response.json()["il_values"], [1000, 1002, 1004])

    def test_invalid_location_never_asks_model_to_invent_an_answer(self):
        self.agent.mode = "gemma"
        with patch.object(llm, "chat") as planner, patch.object(llm, "stream") as writer:
            result = self.agent.answer("Is there oil at inline -1, crossline 2000?", "L3")
        planner.assert_not_called()
        writer.assert_not_called()
        self.assertIn("Location unavailable", result["text"])
        self.assertEqual(result["evidence"], [])

    def test_invalid_section_is_rejected_even_if_old_image_is_cached(self):
        cache = self.store.root / "sections"
        cache.mkdir(exist_ok=True)
        (cache / "il999999.png").write_bytes(b"old incorrectly labelled image")
        with self.assertRaises(InvalidLocationError):
            section_png(self.store, inline=999999)

    def test_section_api_returns_clear_errors(self):
        with patch.object(self.api, "store", self.store):
            client = TestClient(self.api.app)
            for query in ("inline=999999", "crossline=-1", "inline=1000&crossline=2000", ""):
                with self.subTest(query=query):
                    response = client.get(f"/api/section.png?{query}")
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("detail", response.json())
            self.assertEqual(client.get("/api/section.png?inline=1000.5").status_code, 422)

    def test_section_api_still_renders_valid_location(self):
        with patch.object(self.api, "store", self.store):
            response = TestClient(self.api.app).get("/api/section.png?inline=1080")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"\x89PNG"))

    def test_cache_keys_distinguish_signed_and_fractional_locations(self):
        key = self.api._key
        self.assertNotEqual(key("inline -1000 crossline 2000", "L3"), key("inline 1000 crossline 2000", "L3"))
        self.assertNotEqual(key("inline 1000.5 crossline 2000", "L3"), key("inline 10005 crossline 2000", "L3"))
        self.assertNotEqual(key("Rank the leads", "L3"), "L3|rank the leads")

    def test_ambiguous_outcome_notes_remain_unknown(self):
        for text in (None, "", float("nan"), "unknown", "no gas", "gas shows", "P&A", "discussion", "oil and water", "no discovery"):
            with self.subTest(text=text):
                self.assertEqual(classify_result(text), "unknown")
        self.assertEqual(classify_result("Gas discovery"), "discovery")
        self.assertEqual(classify_result("Dry hole"), "dry")

    def test_explicit_synthetic_outcomes_are_preserved(self):
        self.assertEqual(self.store.well("kenari-1")["result"], "discovery")
        self.assertEqual(self.store.well("kenari-2")["result"], "dry")
        self.assertEqual(self.store.well("jati-1")["result"], "dry")
        self.assertEqual(self.store.meta["calibration"]["dry"]["n_wells"], 4)

    def test_unknown_well_is_not_explained_as_failure(self):
        well = self.store.well("kenari-1")
        well.update(result="unknown", result_text="unknown")
        result = self.agent.answer("Why did kenari-1 fail?", "L3")
        self.assertIn("recorded outcome is unknown", result["text"])
        self.assertNotIn("Most likely reason it failed", result["text"])
        self.assertNotIn("water-wet sand", result["text"])

    def test_unknown_lead_outcomes_do_not_trigger_downgrade(self):
        for name in self.store.lead("L1")["wells_inside"]:
            self.store.well(name).update(result="unknown", result_text=None)
        result = self.agent.answer("Explain L1", "L1")
        self.assertIn("verify the recorded well outcomes", result["text"])
        self.assertNotIn("downgrade", result["text"])
        self.assertNotIn("proven play", result["text"])

    def test_existing_store_reclassifies_ambiguous_labels_and_calibration(self):
        root = Path(self.temp.name) / "unknown-store"
        root.mkdir(exist_ok=True)
        wells = json.loads((self.store_root / "wells.json").read_text())
        for well in wells:
            well.update(result="dry", result_text="P&A")
        for name in ("meta.json", "leads.json"):
            (root / name).write_text((self.store_root / name).read_text(), encoding="utf-8")
        (root / "wells.json").write_text(json.dumps(wells), encoding="utf-8")
        store = Store(root)
        self.assertTrue(all(well["result"] == "unknown" for well in store.wells))
        self.assertEqual(store.meta["calibration"], {})

    def test_interrupted_model_discards_partial_text(self):
        self.agent.mode = "gemma"
        def broken(*args, **kwargs):
            yield "UNTRUSTED_PARTIAL_RESPONSE"
            raise llm.LLMError("simulated disconnection")
        with patch.object(llm, "chat", return_value='{"done":true}'), patch.object(llm, "stream", side_effect=broken):
            events = list(self.agent.stream("Explain L3", "L3"))
        text = "".join(event["text"] for event in events if event["type"] == "token")
        self.assertNotIn("UNTRUSTED_PARTIAL_RESPONSE", text)
        self.assertEqual(text.count("**Opportunity**"), 1)
        self.assertEqual(events[-1]["mode"], "offline")
        self.assertFalse(events[-1]["cacheable"])

    def test_model_failure_before_first_token_also_falls_back(self):
        self.agent.mode = "gemma"
        with patch.object(llm, "chat", return_value='{"done":true}'), \
                patch.object(llm, "stream", side_effect=llm.LLMError("timeout")):
            result = self.agent.answer("Explain L3", "L3")
        self.assertTrue(result["text"].startswith("**Opportunity**"))
        self.assertEqual(result["mode"], "offline")

    def test_empty_model_answer_falls_back(self):
        self.agent.mode = "gemma"
        with patch.object(llm, "chat", return_value='{"done":true}'), patch.object(llm, "stream", return_value=iter([])):
            result = self.agent.answer("Explain L3", "L3")
        self.assertIn("empty answer", result["rejected_issues"])
        self.assertEqual(result["mode"], "offline")

    def test_unknown_citation_or_invented_number_is_rejected_before_display(self):
        self.agent.mode = "gemma"
        for draft in ("Unsupported claim [E999].", "Sand probability is 98765 [E2]."):
            with self.subTest(draft=draft), patch.object(llm, "chat", return_value='{"done":true}'), \
                    patch.object(llm, "stream", return_value=iter([draft])):
                result = self.agent.answer("Explain L3", "L3")
                self.assertNotIn(draft, result["text"])
                self.assertEqual(result["mode"], "offline")
                self.assertTrue(result["rejected_issues"])

    def test_supported_model_answer_is_kept(self):
        self.agent.mode = "gemma"
        value = self.store.lead("L3")["attributes"]["sand"]["inside"]
        draft = f"Sand probability is {value} [E2]."
        with patch.object(llm, "chat", return_value='{"done":true}'), patch.object(llm, "stream", return_value=iter([draft])):
            result = self.agent.answer("Explain L3", "L3")
        self.assertEqual(result["text"], draft)
        self.assertEqual(result["mode"], "gemma")
        self.assertEqual(result["rejected_issues"], [])

    def test_failed_planner_tools_fall_back_without_crashing(self):
        self.agent.mode = "gemma"
        with patch.object(llm, "chat", side_effect=['{"tool":"not_a_tool","args":{}}', llm.LLMError("timeout")]):
            result = self.agent.answer("Explain L3", "L3")
        self.assertIn("**Opportunity**", result["text"])

    def test_tool_dispatch_only_accepts_registered_names_and_objects(self):
        for name, args in (("run", {}), ("_alternatives", {}), (["get_leads"], {}), ("get_leads", [1])):
            with self.subTest(name=name):
                result = self.agent.tools.run(name, args)
                self.assertIn("error", result)

    def test_unknown_outcome_claim_and_wrong_sign_fail_model_checks(self):
        evidence = [{"id": "E1", "value": 0.9}, {"id": "E2", "value": "unknown"}]
        self.assertTrue(check_answer("Measured -0.9 [E1].", evidence, []))
        self.assertTrue(check_answer("kenari-1 failed [E2].", evidence, [{"name": "kenari-1", "result": "unknown"}]))
        self.assertEqual(check_answer("kenari-1 outcome is unknown [E2].", evidence, [{"name": "kenari-1", "result": "unknown"}]), [])

    def test_model_numbers_must_match_the_citation_on_their_line(self):
        evidence = [{"id": "E1", "value": 0.9}, {"id": "E2", "value": 1.745}]
        self.assertTrue(check_answer("Measured 1.745 [E1].", evidence, []))
        self.assertEqual(check_answer("Measured 1.745 [E2].", evidence, []), [])

    def test_primary_lead_is_the_explained_lead_not_ui_selection(self):
        self.assertEqual(self.agent.answer("Explain L1", "L3")["lead"], "L1")
        self.assertIsNone(self.agent.answer("Rank the leads", "L3")["lead"])

    def test_blind_test_is_rejected_instead_of_leaking_outcome(self):
        client = TestClient(self.api.app)
        for body in ({"message": "Predict this well", "hide_wells": ["kenari-1"]}, {"message": "Blind test: hide kenari-1"}):
            response = client.post("/api/chat", json=body)
            self.assertEqual(response.status_code, 409)
        self.assertFalse(client.get("/api/health").json()["hide_wells"])

    def test_blank_question_bad_audience_and_unknown_selection_are_rejected(self):
        client = TestClient(self.api.app)
        for body, status in (({"message": "   "}, 422), ({"message": "hi", "audience": "other"}, 422),
                             ({"message": "hi", "selected_lead": "L999"}, 400)):
            self.assertEqual(client.post("/api/chat", json=body).status_code, status)

    def test_cache_key_changes_with_data_model_and_audience(self):
        key = self.api._key("Explain L3", "L3")
        with patch.object(self.api.store, "revision", "different-build"):
            self.assertNotEqual(key, self.api._key("Explain L3", "L3"))
        with patch.object(config, "LLM_MODEL", "different-model"):
            self.assertNotEqual(key, self.api._key("Explain L3", "L3"))
        self.assertNotEqual(key, self.api._key("Explain L3", "L3", "executive"))

    def test_completed_answers_cache_atomically_and_replay_is_labelled(self):
        path = Path(self.temp.name) / "answers.json"
        with patch.object(self.api, "CACHE_ON", True), patch.object(self.api, "_cache", {}), \
                patch.object(self.api, "CACHE_PATH", path), patch.object(self.api, "agent", self.agent):
            client = TestClient(self.api.app)
            first = client.post("/api/chat", json={"message": "Explain L3", "selected_lead": "L3"})
            second = client.post("/api/chat", json={"message": "Explain L3", "selected_lead": "L3"})
            self.assertEqual(first.status_code, 200)
            self.assertIn('"cached": true', second.text)
            self.assertTrue(json.loads(path.read_text()))

    def test_failed_model_answer_is_not_cached(self):
        self.agent.mode = "gemma"
        with patch.object(self.api, "CACHE_ON", True), patch.object(self.api, "_cache", {}) as cache, \
                patch.object(self.api, "agent", self.agent), patch.object(llm, "chat", return_value='{"done":true}'), \
                patch.object(llm, "stream", side_effect=llm.LLMError("timeout")):
            client = TestClient(self.api.app)
            response = client.post("/api/chat", json={"message": "Explain L3", "selected_lead": "L3"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(cache, {})

    def test_corrupt_cache_is_ignored(self):
        path = Path(self.temp.name) / "broken-cache.json"
        path.write_text("{broken", encoding="utf-8")
        self.assertEqual(self.api._load_cache(path), {})

    def test_output_store_is_never_deleted_on_rerun(self):
        with self.assertRaises(FileExistsError):
            precompute.run({}, Path(self.temp.name) / "inputs", self.store_root, 1930, 2080,
                           leads.Params(), None, synthetic=True)
        self.assertTrue((self.store_root / "meta.json").exists())

    def test_invalid_processing_window_does_not_create_output(self):
        output = Path(self.temp.name) / "invalid-window"
        with self.assertRaisesRegex(ValueError, "start < end"):
            precompute.run({}, Path(self.temp.name) / "inputs", output, 2080, 1930,
                           leads.Params(), None, synthetic=True)
        self.assertFalse(output.exists())

    def test_input_directory_cannot_be_used_as_output(self):
        source = Path(self.temp.name) / "inputs"
        with self.assertRaisesRegex(ValueError, "separate"):
            precompute.run({}, source, source, 1930, 2080, leads.Params(), None, synthetic=True)
        self.assertTrue(source.exists())

    def test_misaligned_volume_stops_before_output(self):
        from engine.io import Volume
        data = np.ones((2, 2, 2), dtype=np.float32)
        ref = Volume(data, np.array([1, 2]), np.array([1, 2]), np.array([0., 1.]), np.zeros((2, 2)), np.zeros((2, 2)))
        other = Volume(data, ref.ilines, ref.xlines, np.array([1., 2.]), ref.cdp_x, ref.cdp_y)
        output = Path(self.temp.name) / "misaligned"
        with self.assertRaisesRegex(ValueError, "reference grid"):
            precompute.run({"sand_prob": ref, "full": other}, Path(self.temp.name) / "inputs", output,
                           0, 1, leads.Params(), None, synthetic=True)
        self.assertFalse(output.exists())

    def test_cache_write_failure_does_not_break_completed_answer(self):
        path = Path(self.temp.name) / "protected-cache.json"
        path.write_text('{"previous":[]}', encoding="utf-8")
        with patch.object(self.api, "CACHE_ON", True), patch.object(self.api, "_cache", {}), \
                patch.object(self.api, "CACHE_PATH", path), patch.object(self.api, "agent", self.agent), \
                patch.object(self.api.os, "replace", side_effect=PermissionError("simulated")):
            response = TestClient(self.api.app).post("/api/chat", json={"message": "Explain L3", "selected_lead": "L3"})
            self.assertEqual(response.status_code, 200)
            self.assertIn('"type": "done"', response.text)
            self.assertEqual(json.loads(path.read_text()), {"previous": []})


    # ---------- Gemma interrupted mid-answer (one answer shown, never half + template)
    def _gemma_events(self, writer):
        self.agent.mode = "gemma"
        with patch.object(llm, "stream", writer):
            return self.chat("Rank the leads")

    @staticmethod
    def _shown_text(events):
        """What the chat bubble holds at the end: tokens after the last reset."""
        text = ""
        for event in events:
            if event["type"] == "reset":
                text = ""
            elif event["type"] == "token":
                text += event["text"]
        return text

    def test_gemma_dropping_mid_answer_never_displays_partial_draft(self):
        def broken(*args, **kwargs):
            yield "L2 is the best lead because its sand "
            raise llm.LLMError("connection dropped")
        events = self._gemma_events(broken)
        types = [event["type"] for event in events]
        self.assertNotIn("reset", types)
        shown = self._shown_text(events)
        self.assertNotIn("because its sand", shown)
        self.assertIn("Leads ranked", shown)
        self.assertEqual(events[-1]["mode"], "offline")
        self.assertIn("interrupted or unavailable", events[-1]["note"])

    def test_gemma_failing_before_any_token_needs_no_reset(self):
        def down(*args, **kwargs):
            raise llm.LLMError("refused")
            yield  # pragma: no cover
        events = self._gemma_events(down)
        self.assertNotIn("reset", [event["type"] for event in events])
        self.assertIn("Leads ranked", self._shown_text(events))
        self.assertIn("interrupted or unavailable", events[-1]["note"])

    def test_gemma_empty_answer_falls_back_to_offline(self):
        events = self._gemma_events(lambda *args, **kwargs: iter(["  "]))
        self.assertIn("Leads ranked", self._shown_text(events))
        self.assertEqual(events[-1]["mode"], "offline")

    def test_eval_answer_text_drops_the_interrupted_part(self):
        def broken(*args, **kwargs):
            yield "half a sentence "
            raise llm.LLMError("timeout")
        self.agent.mode = "gemma"
        with patch.object(llm, "stream", broken):
            result = self.agent.answer("Rank the leads")
        self.assertNotIn("half a sentence", result["text"])

    def test_fallback_answers_are_not_cached(self):
        def broken(*args, **kwargs):
            yield "partial "
            raise llm.LLMError("timeout")
        self.agent.mode = "gemma"
        cache = {}
        with patch.object(self.api, "store", self.store), patch.object(self.api, "agent", self.agent), \
                patch.object(self.api, "CACHE_ON", True), patch.object(self.api, "_cache", cache), \
                patch.object(self.api, "CACHE_PATH", self.store.root / "cache_test.json"), \
                patch.object(llm, "stream", broken):
            TestClient(self.api.app).post("/api/chat", json={"message": "Rank the leads"})
        self.assertEqual(cache, {})


class LLMProtocolTests(unittest.TestCase):
    def response(self, lines):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = iter(lines)
        return response

    def test_stream_requires_completion_marker(self):
        response = self.response(['data: {"choices":[{"delta":{"content":"partial"}}]}'])
        with patch.object(llm.requests, "post", return_value=response), self.assertRaises(llm.LLMError):
            list(llm.stream([]))

    def test_complete_stream_accepts_usage_chunk(self):
        response = self.response(['data: {"choices":[{"delta":{"content":"complete"}}]}',
                                  'data: {"choices":[],"usage":{}}', 'data: [DONE]'])
        with patch.object(llm.requests, "post", return_value=response):
            self.assertEqual(list(llm.stream([])), ["complete"])

    def test_length_limited_response_is_incomplete(self):
        response = self.response(['data: {"choices":[{"delta":{},"finish_reason":"length"}]}', 'data: [DONE]'])
        with patch.object(llm.requests, "post", return_value=response), self.assertRaises(llm.LLMError):
            list(llm.stream([]))

    def test_json_parser_handles_braces_inside_strings(self):
        self.assertEqual(llm.parse_json('```json\n{"tool":"get_leads","why":"a } in a string"}\n```')["tool"], "get_leads")




if __name__ == "__main__":
    unittest.main()
