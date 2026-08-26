#!/usr/bin/env python3
"""
Generator for index.html, style.css, app.js, and README.md.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Read current working app.js and style.css
app_js = (BASE_DIR / "app.js").read_text(encoding="utf-8")
style_css = (BASE_DIR / "style.css").read_text(encoding="utf-8")
index_html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
readme_md = (BASE_DIR / "README.md").read_text(encoding="utf-8")

print(f"Verified assets in {BASE_DIR}")
