"""STEP 2 - DATA STRUCTURE
Typed records used inside the pipeline, plus the star schema the results are loaded into.

    dim_product ──┐
    dim_stage ────┼──< fact_impact >── dim_month
    dim_factor ───┘
"""
from dataclasses import dataclass
from typing import Optional

STAGES = ["raw_materials", "manufacturing", "transport", "use", "end_of_life"]


@dataclass(frozen=True)
class EmissionFactor:
    activity: str          # e.g. "cotton", "electricity", "sea_freight"
    unit: str              # unit the factor is expressed per (kg, kWh, tkm …)
    kgco2e_per_unit: float
    source: str            # database + version, needed for audit trails


@dataclass
class InventoryRecord:
    """One harmonised activity flow: 'product X used Y units of activity Z in stage S'."""
    product_id: str
    stage: str
    activity: str
    amount: float          # per functional unit (one product), already in factor unit
    unit: str
    month: Optional[str] = None
    source_file: str = ""

    def __post_init__(self):
        if self.stage not in STAGES:
            raise ValueError(f"unknown stage {self.stage!r}")
        if self.amount < 0:
            raise ValueError(f"negative amount for {self.activity}")


@dataclass
class ImpactResult:
    product_id: str
    stage: str
    activity: str
    month: Optional[str]
    kgco2e_per_unit: float     # footprint of ONE product for this flow
    units_produced: int = 0

    @property
    def kgco2e_total(self) -> float:
        return self.kgco2e_per_unit * self.units_produced


DDL = """
CREATE TABLE IF NOT EXISTS dim_product (product_id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS dim_stage   (stage TEXT PRIMARY KEY, stage_order INTEGER);
CREATE TABLE IF NOT EXISTS dim_month   (month TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS dim_factor  (activity TEXT PRIMARY KEY, unit TEXT,
                                        kgco2e_per_unit REAL, source TEXT);
CREATE TABLE IF NOT EXISTS fact_impact (
    product_id TEXT REFERENCES dim_product, stage TEXT REFERENCES dim_stage,
    activity TEXT REFERENCES dim_factor, month TEXT REFERENCES dim_month,
    kgco2e_per_unit REAL, units_produced INTEGER, kgco2e_total REAL);
"""
