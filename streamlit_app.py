"""Free-host entrypoint for the real E. coli bundle and precomputed demo sample.

Streamlit Community Cloud cannot install AMRFinderPlus. This wrapper selects the packaged
bundle and precomputed-only UI before executing the normal application. Local and Docker
launches continue to use genome-firewall/app/streamlit_app.py with live FASTA analysis.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "genome-firewall"

os.environ.setdefault("GF_MODEL_BUNDLE", str(PROJECT / "models" / "ecoli-bundle"))
os.environ.setdefault("GF_PRECOMPUTED_ONLY", "1")
sys.path.insert(0, str(PROJECT))
os.chdir(PROJECT)
runpy.run_path(str(PROJECT / "app" / "streamlit_app.py"), run_name="__main__")
