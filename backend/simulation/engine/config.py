"""
Simulation engine configuration.
Loads delegation CSV, defines SCENARIOS and SCALE_PRESETS.
All monetary values are TND/m².
"""
import csv
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path to delegation data
# ---------------------------------------------------------------------------
_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "delegations.csv"

# Coastal governorates — used by climate_stress scenario
COASTAL_GOVERNORATES = {
    "Tunis", "Ariana", "Ben Arous", "La Manouba",
    "Nabeul", "Bizerte", "Béja",
    "Sfax", "Mahdia", "Monastir",
    "Sousse", "Gabès", "Médenine",
}

# ---------------------------------------------------------------------------
# Load delegation data from CSV once at import time
# ---------------------------------------------------------------------------
def _parse_pct(value: str) -> float:
    """Convert '−8%' / '-8%' / '2%' to float −0.08 / 0.02."""
    if not value:
        return 0.0
    try:
        cleaned = value.strip().replace("−", "-").replace("%", "")
        return float(cleaned) / 100.0
    except ValueError:
        return 0.0


def _parse_float(value: str) -> float:
    try:
        return float(value.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return 0.0


def _parse_int(value: str) -> int:
    try:
        return int(value.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return 0


def load_delegations() -> list:
    """
    Returns a list of dicts, one per delegation row in the CSV.
    Keys: delegation, governorate, population,
          apartment_min, apartment_avg, apartment_max, apartment_trend,
          house_min,     house_avg,     house_max,     house_trend,
          commercial_min, commercial_avg, commercial_max, commercial_trend,
          land_min,      land_avg,      land_max,      land_trend,
    """
    rows = []
    csv_path = _CSV_PATH
    if not csv_path.exists():
        logger.warning("Delegation CSV not found at %s; using fallback data.", csv_path)
        return _fallback_delegations()
    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for raw in reader:
                row = {
                    "delegation":       raw.get("Delegation", "").strip(),
                    "governorate":      raw.get("Governorate", "").strip(),
                    "population":       _parse_int(raw.get("Population_2024", "0")),
                    "apartment_min":    _parse_float(raw.get("Apartment_Min_TND", "0")),
                    "apartment_avg":    _parse_float(raw.get("Apartment_Avg_TND", "0")),
                    "apartment_max":    _parse_float(raw.get("Apartment_Max_TND", "0")),
                    "apartment_trend":  _parse_pct(raw.get("Apartment_Trend_Percent", "0")),
                    "house_min":        _parse_float(raw.get("House_Min_TND", "0")),
                    "house_avg":        _parse_float(raw.get("House_Avg_TND", "0")),
                    "house_max":        _parse_float(raw.get("House_Max_TND", "0")),
                    "house_trend":      _parse_pct(raw.get("House_Trend_Percent", "0")),
                    "commercial_min":   _parse_float(raw.get("Commercial_Min_TND", "0")),
                    "commercial_avg":   _parse_float(raw.get("Commercial_Avg_TND", "0")),
                    "commercial_max":   _parse_float(raw.get("Commercial_Max_TND", "0")),
                    "commercial_trend": _parse_pct(raw.get("Commercial_Trend_Percent", "0")),
                    "land_min":         _parse_float(raw.get("Land_Min_TND", "0")),
                    "land_avg":         _parse_float(raw.get("Land_Avg_TND", "0")),
                    "land_max":         _parse_float(raw.get("Land_Max_TND", "0")),
                    "land_trend":       _parse_pct(raw.get("Land_Trend_Percent", "0")),
                    "is_coastal":       raw.get("Governorate", "").strip() in COASTAL_GOVERNORATES,
                }
                if row["delegation"]:
                    rows.append(row)
    except Exception as exc:
        logger.error("Failed to load delegations CSV: %s", exc)
        return _fallback_delegations()
    logger.info("Loaded %d delegation rows from CSV.", len(rows))
    return rows


def _fallback_delegations() -> list:
    """Minimal hard-coded fallback so the engine never crashes without the CSV."""
    return [
        {
            "delegation": "Tunis Centre", "governorate": "Tunis",
            "population": 650000,
            "apartment_min": 1800, "apartment_avg": 2800, "apartment_max": 4200,
            "apartment_trend": -0.05,
            "house_min": 2000, "house_avg": 3200, "house_max": 5000,
            "house_trend": -0.04,
            "commercial_min": 2500, "commercial_avg": 4000, "commercial_max": 6000,
            "commercial_trend": -0.03,
            "land_min": 800, "land_avg": 1500, "land_max": 2500,
            "land_trend": -0.06,
            "is_coastal": True,
        },
        {
            "delegation": "Sfax Ville", "governorate": "Sfax",
            "population": 340000,
            "apartment_min": 900, "apartment_avg": 1400, "apartment_max": 2000,
            "apartment_trend": 0.02,
            "house_min": 800, "house_avg": 1200, "house_max": 1800,
            "house_trend": 0.01,
            "commercial_min": 1200, "commercial_avg": 1800, "commercial_max": 2800,
            "commercial_trend": 0.02,
            "land_min": 250, "land_avg": 500, "land_max": 900,
            "land_trend": 0.01,
            "is_coastal": True,
        },
    ]


# Load once on module import
DELEGATION_DATA: list = load_delegations()


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
SCENARIOS: dict = {
    "baseline": {
        "id":                   "baseline",
        "label":                "Baseline",
        "description":          "Normal market conditions with moderate growth and standard credit access.",
        "icon":                 "TrendingUp",
        "color":                "#6366f1",
        "type":                 "neutral",
        "category":             "macro",
        # Engine params
        "monthly_drift":        0.004,     # +0.4% / month
        "demand_multiplier":    1.0,
        "credit_approval_rate": 0.55,
        "bct_rate":             0.08,      # 8% base BCT rate
        "developer_activity":   1.0,
        "speculator_activity":  1.0,
        "investor_multiplier":  1.0,
        "coastal_penalty":      0.0,
        "price_volatility":     0.012,
    },
    "infrastructure_push": {
        "id":                   "infrastructure_push",
        "label":                "Infrastructure Push",
        "description":          "Major government investment in roads, utilities, and public transport drives demand.",
        "icon":                 "Building2",
        "color":                "#10b981",
        "type":                 "positive",
        "category":             "policy",
        "monthly_drift":        0.008,
        "demand_multiplier":    1.25,
        "credit_approval_rate": 0.60,
        "bct_rate":             0.08,
        "developer_activity":   1.4,
        "speculator_activity":  1.2,
        "investor_multiplier":  1.3,
        "coastal_penalty":      0.0,
        "price_volatility":     0.015,
    },
    "interest_rate_hike": {
        "id":                   "interest_rate_hike",
        "label":                "Interest Rate Hike",
        "description":          "BCT raises rates aggressively to fight inflation, cooling mortgage demand.",
        "icon":                 "TrendingDown",
        "color":                "#f59e0b",
        "type":                 "negative",
        "category":             "monetary",
        "monthly_drift":        -0.002,
        "demand_multiplier":    0.75,
        "credit_approval_rate": 0.35,
        "bct_rate":             0.13,
        "developer_activity":   0.7,
        "speculator_activity":  0.6,
        "investor_multiplier":  0.7,
        "coastal_penalty":      0.0,
        "price_volatility":     0.018,
    },
    "liquidity_crunch": {
        "id":                   "liquidity_crunch",
        "label":                "Liquidity Crunch",
        "description":          "Banks restrict lending sharply; only cash buyers remain active.",
        "icon":                 "AlertTriangle",
        "color":                "#ef4444",
        "type":                 "negative",
        "category":             "financial",
        "monthly_drift":        -0.004,
        "demand_multiplier":    0.65,
        "credit_approval_rate": 0.20,
        "bct_rate":             0.14,
        "developer_activity":   0.5,
        "speculator_activity":  0.4,
        "investor_multiplier":  0.5,
        "coastal_penalty":      0.0,
        "price_volatility":     0.022,
    },
    "policy_tightening": {
        "id":                   "policy_tightening",
        "label":                "Policy Tightening",
        "description":          "New regulations curb speculation: transaction taxes rise and flipping is restricted.",
        "icon":                 "Shield",
        "color":                "#8b5cf6",
        "type":                 "neutral",
        "category":             "policy",
        "monthly_drift":        0.001,
        "demand_multiplier":    0.90,
        "credit_approval_rate": 0.50,
        "bct_rate":             0.09,
        "developer_activity":   0.9,
        "speculator_activity":  0.45,
        "investor_multiplier":  0.8,
        "coastal_penalty":      0.0,
        "price_volatility":     0.010,
    },
    "monetary_easing": {
        "id":                   "monetary_easing",
        "label":                "Monetary Easing",
        "description":          "BCT cuts rates and loosens credit; home ownership becomes more accessible.",
        "icon":                 "Zap",
        "color":                "#06b6d4",
        "type":                 "positive",
        "category":             "monetary",
        "monthly_drift":        0.010,
        "demand_multiplier":    1.35,
        "credit_approval_rate": 0.70,
        "bct_rate":             0.055,
        "developer_activity":   1.3,
        "speculator_activity":  1.4,
        "investor_multiplier":  1.5,
        "coastal_penalty":      0.0,
        "price_volatility":     0.016,
    },
    "supply_expansion": {
        "id":                   "supply_expansion",
        "label":                "Supply Expansion",
        "description":          "Mass social housing programme floods the market with new units.",
        "icon":                 "Home",
        "color":                "#84cc16",
        "type":                 "neutral",
        "category":             "supply",
        "monthly_drift":        -0.001,
        "demand_multiplier":    1.05,
        "credit_approval_rate": 0.58,
        "bct_rate":             0.08,
        "developer_activity":   2.0,
        "speculator_activity":  0.8,
        "investor_multiplier":  0.9,
        "coastal_penalty":      0.0,
        "price_volatility":     0.010,
    },
    "speculative_boom": {
        "id":                   "speculative_boom",
        "label":                "Speculative Boom",
        "description":          "FOMO drives rapid price escalation as investors and speculators flood the market.",
        "icon":                 "Flame",
        "color":                "#f97316",
        "type":                 "volatile",
        "category":             "market",
        "monthly_drift":        0.015,
        "demand_multiplier":    1.50,
        "credit_approval_rate": 0.65,
        "bct_rate":             0.075,
        "developer_activity":   1.2,
        "speculator_activity":  2.5,
        "investor_multiplier":  2.0,
        "coastal_penalty":      0.0,
        "price_volatility":     0.030,
    },
    "climate_stress": {
        "id":                   "climate_stress",
        "label":                "Climate Stress",
        "description":          "Rising sea levels and extreme heat events depress coastal and southern property values.",
        "icon":                 "Waves",
        "color":                "#64748b",
        "type":                 "negative",
        "category":             "environmental",
        "monthly_drift":        -0.003,
        "demand_multiplier":    0.85,
        "credit_approval_rate": 0.48,
        "bct_rate":             0.085,
        "developer_activity":   0.85,
        "speculator_activity":  0.7,
        "investor_multiplier":  0.75,
        "coastal_penalty":      -0.010,   # additional −1% / month for coastal zones
        "price_volatility":     0.020,
    },
}

SCENARIO_IDS = list(SCENARIOS.keys())

# ---------------------------------------------------------------------------
# Scale presets
# ---------------------------------------------------------------------------
SCALE_PRESETS: dict = {
    "tiny": {
        "buyers":      20,
        "sellers":     10,
        "brokers":      2,
        "developers":   2,
        "banks":        1,
        "speculators":  3,
        "governments":  1,
        "label":       "Tiny (~40 agents)",
    },
    "medium": {
        "buyers":     100,
        "sellers":     50,
        "brokers":     10,
        "developers":   8,
        "banks":        4,
        "speculators":  20,
        "governments":  2,
        "label":       "Medium (~200 agents)",
    },
    "large": {
        "buyers":     260,
        "sellers":    130,
        "brokers":     25,
        "developers":  20,
        "banks":       10,
        "speculators":  50,
        "governments":   5,
        "label":       "Large (~500 agents)",
    },
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def get_scenario(name: str) -> dict:
    """Return scenario config dict or raise KeyError."""
    if name not in SCENARIOS:
        raise KeyError(f"Unknown scenario: {name!r}. Valid: {SCENARIO_IDS}")
    return SCENARIOS[name]


def get_scale(name: str) -> dict:
    """Return scale preset dict, falling back to 'tiny'."""
    return SCALE_PRESETS.get(name, SCALE_PRESETS["tiny"])


def national_avg_price() -> float:
    """Weighted average apartment price across all loaded delegations."""
    if not DELEGATION_DATA:
        return 2000.0
    total_w = sum(d["population"] for d in DELEGATION_DATA)
    if total_w == 0:
        total_w = len(DELEGATION_DATA)
        return sum(d["apartment_avg"] for d in DELEGATION_DATA) / total_w
    return sum(d["apartment_avg"] * d["population"] for d in DELEGATION_DATA) / total_w


def scenarios_list() -> list:
    """Return the public-facing scenario list (id, label, description, icon, color, type, category)."""
    return [
        {k: v for k, v in s.items() if k in ("id", "label", "description", "icon", "color", "type", "category")}
        for s in SCENARIOS.values()
    ]
