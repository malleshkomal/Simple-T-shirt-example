"""STEP 1 - DATA COLLECTION
Simulates pulling LCA inventory data from four typical sources and lands the raw
files unchanged in data/raw/ (the "landing zone"). Swap each function body for a
real connector (ERP export, utility API, TMS database, survey form).
"""
import csv
import json
import random
from pathlib import Path

RAW = Path(__file__).parent / "data" / "raw"
random.seed(42)

PRODUCTS = {"TSHIRT": "Cotton T-shirt", "JEANS": "Denim jeans", "SNEAKER": "Running sneaker"}
FACTORIES = {"TSHIRT": "F-DHAKA", "JEANS": "F-DHAKA", "SNEAKER": "F-HANOI"}
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]


def collect_bill_of_materials():
    """Source A: supplier bill of materials (CSV export from ERP)."""
    rows = [
        ("TSHIRT", "cotton", 0.25, "kg", "SUP-01", "IN"),
        ("TSHIRT", "polyester", 50, "g", "SUP-02", "CN"),
        ("JEANS", "cotton", 0.80, "kg", "SUP-01", "IN"),
        ("JEANS", "elastane", 20, "g", "SUP-03", "CN"),
        ("JEANS", "metal_trims", 30, "g", "SUP-04", "TR"),
        ("SNEAKER", "synthetic_rubber", 0.35, "kg", "SUP-05", "VN"),
        ("SNEAKER", "polyester", 0.20, "kg", "SUP-02", "CN"),
        ("SNEAKER", "eva_foam", 150, "g", "SUP-05", "VN"),
        ("SNEAKER", "leather", None, "kg", "SUP-06", "BR"),   # missing value on purpose
    ]
    with open(RAW / "bill_of_materials.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "material", "qty_per_unit", "unit", "supplier_id", "origin"])
        w.writerows(rows)


def collect_utility_meters():
    """Source B: monthly factory meter readings (JSON from a utility API)."""
    readings = []
    for pid, factory in FACTORIES.items():
        base_units = {"TSHIRT": 40000, "JEANS": 18000, "SNEAKER": 12000}[pid]
        kwh_per_unit = {"TSHIRT": 1.2, "JEANS": 3.1, "SNEAKER": 4.4}[pid]
        gas_per_unit = {"TSHIRT": 0.4, "JEANS": 1.1, "SNEAKER": 0.6}[pid]
        for i, month in enumerate(MONTHS):
            season = 1 + 0.25 * (1 if i in (8, 9, 10) else 0) - 0.15 * (1 if i in (0, 1) else 0)
            units = int(base_units * season * random.uniform(0.92, 1.08))
            # efficiency program kicks in from July: -12 % electricity per unit
            eff = 0.88 if i >= 6 else 1.0
            readings.append({
                "meter_id": f"{factory}-{pid}",
                "product_id": pid,
                "month": month,
                "units_produced": units,
                "electricity": {"value": round(units * kwh_per_unit * eff * random.uniform(0.97, 1.03) / 1000, 2), "unit": "MWh"},
                "natural_gas": {"value": round(units * gas_per_unit * random.uniform(0.95, 1.05), 1), "unit": "m3"},
            })
    (RAW / "utility_meters.json").write_text(json.dumps({"source": "utility-api", "readings": readings}, indent=2))


def collect_shipments():
    """Source C: logistics shipment records (transport management system)."""
    modes = {"TSHIRT": [("sea", 16000), ("truck", 600)],
             "JEANS": [("sea", 16000), ("truck", 600)],
             "SNEAKER": [("sea", 12000), ("truck", 900), ("air", 9000)]}
    unit_weight_kg = {"TSHIRT": 0.3, "JEANS": 0.9, "SNEAKER": 0.95}
    with open(RAW / "shipments.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["shipment_id", "product_id", "month", "mode", "distance_km", "units"])
        n = 0
        for pid, legs in modes.items():
            for month in MONTHS:
                units = random.randint(10000, 40000)
                for mode, km in legs:
                    if mode == "air" and random.random() < 0.7:
                        continue  # air freight only for urgent orders
                    n += 1
                    w.writerow([f"SHP-{n:05d}", pid, month, mode, km, units if mode != "air" else units // 10])
    (RAW / "unit_weights.json").write_text(json.dumps(unit_weight_kg))


def collect_lifecycle_assumptions():
    """Source D: use-phase and end-of-life assumptions (sustainability team survey)."""
    data = {
        "TSHIRT": {"washes": 50, "kwh_per_wash": 0.07, "landfill_share": 0.6, "recycle_share": 0.4},
        "JEANS": {"washes": 40, "kwh_per_wash": 0.10, "landfill_share": 0.7, "recycle_share": 0.3},
        "SNEAKER": {"washes": 0, "kwh_per_wash": 0.0, "landfill_share": 0.9, "recycle_share": 0.1},
    }
    (RAW / "lifecycle_assumptions.json").write_text(json.dumps(data, indent=2))
    (RAW / "products.json").write_text(json.dumps(PRODUCTS, indent=2))


if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    collect_bill_of_materials()
    collect_utility_meters()
    collect_shipments()
    collect_lifecycle_assumptions()
    print("Collected raw files:", sorted(p.name for p in RAW.iterdir()))
