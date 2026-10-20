"""STEP 3 - DATA PIPELINE
extract (raw files) -> validate -> transform (harmonise units, map factors)
-> calculate -> load (SQLite star schema + JSON for the charts)
"""
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

from schema import DDL, STAGES, EmissionFactor, ImpactResult, InventoryRecord

ROOT = Path(__file__).parent
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"

# Illustrative factors - in production load these from ecoinvent / DEFRA / EPA.
FACTORS = {f.activity: f for f in [
    EmissionFactor("cotton", "kg", 5.90, "demo-db v1"),
    EmissionFactor("polyester", "kg", 6.40, "demo-db v1"),
    EmissionFactor("elastane", "kg", 13.0, "demo-db v1"),
    EmissionFactor("metal_trims", "kg", 8.20, "demo-db v1"),
    EmissionFactor("synthetic_rubber", "kg", 3.20, "demo-db v1"),
    EmissionFactor("eva_foam", "kg", 4.10, "demo-db v1"),
    EmissionFactor("leather", "kg", 17.0, "demo-db v1"),
    EmissionFactor("electricity", "kWh", 0.40, "demo-db v1"),
    EmissionFactor("natural_gas", "m3", 2.02, "demo-db v1"),
    EmissionFactor("sea_freight", "tkm", 0.016, "demo-db v1"),
    EmissionFactor("truck_freight", "tkm", 0.11, "demo-db v1"),
    EmissionFactor("air_freight", "tkm", 1.13, "demo-db v1"),
    EmissionFactor("landfill", "kg", 0.58, "demo-db v1"),
    EmissionFactor("recycling", "kg", 0.21, "demo-db v1"),
]}
TO_FACTOR_UNIT = {("g", "kg"): 0.001, ("kg", "kg"): 1, ("MWh", "kWh"): 1000,
                  ("kWh", "kWh"): 1, ("m3", "m3"): 1, ("tkm", "tkm"): 1}
log = {"rows_in": 0, "rows_rejected": 0, "issues": []}


# ---------- EXTRACT ----------
def extract():
    bom = pd.read_csv(RAW / "bill_of_materials.csv")
    meters = pd.json_normalize(json.loads((RAW / "utility_meters.json").read_text())["readings"])
    meters.columns = [c.replace(".", "_") for c in meters.columns]   # electricity.value -> electricity_value
    ships = pd.read_csv(RAW / "shipments.csv")
    weights = json.loads((RAW / "unit_weights.json").read_text())
    life = json.loads((RAW / "lifecycle_assumptions.json").read_text())
    products = json.loads((RAW / "products.json").read_text())
    log["rows_in"] = len(bom) + len(meters) + len(ships) + len(life)
    return bom, meters, ships, weights, life, products


# ---------- VALIDATE ----------
def validate(bom, meters, ships):
    bad = bom["qty_per_unit"].isna()
    for _, r in bom[bad].iterrows():
        log["issues"].append(f"BOM: {r.product_id}/{r.material} has no quantity -> rejected")
    bom = bom[~bad]
    bad = meters["units_produced"] <= 0
    meters = meters[~bad]
    unknown = ~ships["mode"].isin(["sea", "truck", "air"])
    ships = ships[~unknown]
    log["rows_rejected"] = int(bad.sum() + unknown.sum()) + len(log["issues"])
    return bom, meters, ships


# ---------- TRANSFORM: build harmonised InventoryRecords (per one product) ----------
def to_factor_unit(amount, unit, activity):
    return amount * TO_FACTOR_UNIT[(unit, FACTORS[activity].unit)]


def transform(bom, meters, ships, weights, life):
    records = []
    for r in bom.itertuples():
        records.append(InventoryRecord(r.product_id, "raw_materials", r.material,
                                       to_factor_unit(r.qty_per_unit, r.unit, r.material), "kg",
                                       source_file="bill_of_materials.csv"))
    for r in meters.itertuples():
        u = r.units_produced
        records.append(InventoryRecord(r.product_id, "manufacturing", "electricity",
                                       to_factor_unit(r.electricity_value, r.electricity_unit, "electricity") / u, "kWh", r.month, "utility_meters.json"))
        records.append(InventoryRecord(r.product_id, "manufacturing", "natural_gas",
                                       to_factor_unit(r.natural_gas_value, r.natural_gas_unit, "natural_gas") / u, "m3", r.month, "utility_meters.json"))
    # transport: tonne-km per product, weighted by how many units took each leg
    for (pid, month), g in ships.groupby(["product_id", "month"]):
        base_units = g.loc[g["mode"] == "sea", "units"].sum()
        for leg in g.itertuples():
            tkm = leg.distance_km * weights[pid] / 1000 * leg.units / base_units
            records.append(InventoryRecord(pid, "transport", f"{leg.mode}_freight", tkm, "tkm", month, "shipments.csv"))
    for pid, a in life.items():
        records.append(InventoryRecord(pid, "use", "electricity", a["washes"] * a["kwh_per_wash"], "kWh",
                                       source_file="lifecycle_assumptions.json"))
        records.append(InventoryRecord(pid, "end_of_life", "landfill", weights[pid] * a["landfill_share"], "kg",
                                       source_file="lifecycle_assumptions.json"))
        records.append(InventoryRecord(pid, "end_of_life", "recycling", weights[pid] * a["recycle_share"], "kg",
                                       source_file="lifecycle_assumptions.json"))
    return records


# ---------- CALCULATE: impact = amount x factor, spread over the 12 months ----------
def calculate(records, meters):
    units = {(r.product_id, r.month): r.units_produced for r in meters.itertuples()}
    months = sorted(meters["month"].unique())
    results = []
    for rec in records:
        per_unit = rec.amount * FACTORS[rec.activity].kgco2e_per_unit
        for m in ([rec.month] if rec.month else months):     # constant flows apply every month
            results.append(ImpactResult(rec.product_id, rec.stage, rec.activity, m,
                                        per_unit, units[(rec.product_id, m)]))
    return results


# ---------- LOAD ----------
def load(results, products, months):
    df = pd.DataFrame([{**r.__dict__, "kgco2e_total": r.kgco2e_total} for r in results])
    con = sqlite3.connect(OUT / "lca.db")
    con.executescript("DROP TABLE IF EXISTS fact_impact;" + DDL)
    con.executemany("INSERT OR REPLACE INTO dim_product VALUES (?,?)", products.items())
    con.executemany("INSERT OR REPLACE INTO dim_stage VALUES (?,?)", [(s, i) for i, s in enumerate(STAGES)])
    con.executemany("INSERT OR REPLACE INTO dim_month VALUES (?)", [(m,) for m in months])
    con.executemany("INSERT OR REPLACE INTO dim_factor VALUES (?,?,?,?)",
                    [(f.activity, f.unit, f.kgco2e_per_unit, f.source) for f in FACTORS.values()])
    df.to_sql("fact_impact", con, if_exists="append", index=False)
    con.commit()

    # Aggregates the visualisations need
    per_unit = (df.groupby(["product_id", "stage", "month"])["kgco2e_per_unit"].sum()
                  .groupby(["product_id", "stage"]).mean().unstack().reindex(columns=STAGES).fillna(0))
    monthly = (df.groupby(["product_id", "month"])["kgco2e_total"].sum() / 1000).unstack()   # tonnes
    mfg = (df[df.stage == "manufacturing"].groupby(["product_id", "month"])["kgco2e_per_unit"].sum().unstack())
    summary = {
        "products": products, "stages": STAGES, "months": months,
        "per_unit_by_stage": per_unit.round(3).to_dict(orient="index"),
        "monthly_tonnes": monthly.round(2).to_dict(orient="index"),
        "manufacturing_per_unit": mfg.round(3).to_dict(orient="index"),
        "pipeline_log": {**log, "impact_rows": len(results), "fact_rows": len(df)},
    }
    (OUT / "lca_summary.json").write_text(json.dumps(summary, indent=2))
    con.close()
    return summary


def run():
    bom, meters, ships, weights, life, products = extract()
    bom, meters, ships = validate(bom, meters, ships)
    records = transform(bom, meters, ships, weights, life)
    results = calculate(records, meters)
    s = load(results, products, sorted(meters["month"].unique()))
    print("Pipeline log:", json.dumps(s["pipeline_log"], indent=2))
    for pid, stages in s["per_unit_by_stage"].items():
        print(f"{products[pid]:<16} {sum(stages.values()):6.2f} kg CO2e/unit  ", {k: round(v, 2) for k, v in stages.items()})
    return s


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    run()
