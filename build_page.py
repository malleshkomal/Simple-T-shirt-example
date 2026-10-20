"""Injects data/processed/lca_summary.json into page_template.html -> output/lca_dashboard.html"""
from pathlib import Path

ROOT = Path(__file__).parent
data = (ROOT / "data/processed/lca_summary.json").read_text()
html = (ROOT / "page_template.html").read_text().replace("__DATA__", data)
(ROOT / "output/lca_dashboard.html").write_text(html)
print("Wrote output/lca_dashboard.html")
