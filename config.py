"""Central settings. Everything can be overridden with environment variables.

On the HPC:
    export COPILOT_STORE_DIR=/data/epic20/APGCE/<your_team>/copilot_store
On a laptop (no data, fake survey):
    export MOCK=1
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# MOCK=1 -> synthetic survey + offline reasoner, so laptops can run the whole app.
MOCK = os.environ.get("MOCK", "0") == "1"

# Raw challenge data (read-only, never copied off the HPC).
DATA_DIR = Path(os.environ.get(
    "COPILOT_DATA_DIR", "/data/epic20/APGCE/input_data/challenge1_challenge2"))

# Where precompute writes maps, leads, wells and cubes for the app to read.
STORE_DIR = Path(os.environ.get(
    "COPILOT_STORE_DIR", str(ROOT / ("store_mock" if MOCK else "store"))))

# Seismic volumes for Challenge 1 (paths relative to DATA_DIR; matched case-insensitively).
VOLUMES = {
    "full":       "stack/Challenge1_Challenge2_Full_Stack_cropped.sgy",
    "near":       "stack/Challenge1_Challenge2_Near_Stack_cropped.sgy",
    "mid":        "stack/Challenge1_Challenge2_Mid_Stack_cropped.sgy",
    "far":        "stack/Challenge1_Challenge2_Far_Stack_cropped.sgy",
    "ultrafar":   "stack/Challenge1_Challenge2_UltraFar_Stack_cropped.sgy",
    "pimp":       "inversion/Challenge1_Challenge2_Inversion_P_Impedance_cropped.sgy",
    "simp":       "inversion/Challenge1_Challenge2_Inversion_S_Impedance_cropped.sgy",
    "vpvs":       "inversion/Challenge1_Challenge2_Inversion_VpVs_cropped.sgy",
    "sand_prob":  "inversion/Challenge1_Challenge2_Inversion_TotalSandProbability_cropped.sgy",
}
WELL_DIR = "well_data"

# SEG-Y header byte locations for inline / crossline (standard = 189 / 193).
ILINE_BYTE = int(os.environ.get("COPILOT_ILINE_BYTE", 189))
XLINE_BYTE = int(os.environ.get("COPILOT_XLINE_BYTE", 193))

# LLM: the shared Gemma 4 endpoint on the DUG HPC (OpenAI-compatible).
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://172.28.34.1:8000/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "google/gemma-4-26B-A4B-it")
# LLM=gemma -> call the endpoint; LLM=offline -> rule-based reasoner (no network).
LLM_MODE = os.environ.get("LLM", "offline" if MOCK else "gemma")
LLM_TIMEOUT_S = float(os.environ.get("LLM_TIMEOUT_S", 60))
MAX_TOOL_STEPS = int(os.environ.get("MAX_TOOL_STEPS", 4))

KNOWLEDGE_DIR = ROOT / "knowledge"
