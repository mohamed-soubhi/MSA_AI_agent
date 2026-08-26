#!/usr/bin/env python3
"""
Generator script to build the complete Project Code Flow & Architecture Visualizer.
Generates:
  - 11 Standalone interactive SVG flow diagrams
  - Comprehensive modern CSS stylesheet
  - Interactive JavaScript controller (zoom/pan, search, simulator, file tree)
  - Full-featured index.html dashboard
  - README.md documentation
"""

import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent
SVG_DIR = OUTPUT_DIR / "svg"
SVG_DIR.mkdir(parents=True, exist_ok=True)

print(f"Building Code Flow Visualizer in: {OUTPUT_DIR}")
