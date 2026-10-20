# Garment LCA Pipeline

An example life cycle assessment (LCA) data pipeline for three products (T-shirt, jeans, sneakers).
It covers data collection, data structure, the pipeline itself, and animated charts.
The data is simulated and the emission factors are illustrative example values.

## Run

    pip install -r requirements.txt
    python collect.py      # 1. data collection   -> data/raw/
    python pipeline.py     # 2-3. structure + pipeline -> data/processed/lca.db, lca_summary.json
    python visualize.py    # 4. animated GIF charts -> output/*.gif
    python build_page.py   # 4. animated HTML page  -> output/lca_dashboard.html

## Files

| File | Purpose |
|---|---|
| collect.py | Simulates 4 sources (bill of materials CSV, meter JSON, shipments CSV, assumptions JSON) |
| schema.py | Dataclasses (InventoryRecord, EmissionFactor, ImpactResult) and the SQLite star schema |
| pipeline.py | Extract -> validate -> transform -> calculate -> load |
| visualize.py | matplotlib animations saved as GIFs |
| build_page.py, page_template.html | Interactive animated HTML page (open in any browser) |

To use real data, replace the functions in collect.py with connectors to your sources
and load real emission factors (ecoinvent, DEFRA, EPA) in pipeline.py.
