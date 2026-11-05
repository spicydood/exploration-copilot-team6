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
from unittest.mock import patch

os.environ["MOCK"] = "1"

import numpy as np
from fastapi.testclient import TestClient

import config
from backend import llm
from backend.agent import Agent, is_ranking
from backend.render import section_png
from backend.store import InvalidLocationError, Store
from engine import leads, mock_data, precompute


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


if __name__ == "__main__":
    unittest.main()
