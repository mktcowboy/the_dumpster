"""Loads config.json (next to this file) over built-in defaults."""
import json, os
_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = {
    "commission_per_contract": 0.65, "entry_slippage_frac_of_half_spread": 0.5, "exit_slippage_frac_of_half_spread": 0.5,
    "exit_spread_multiplier": 1.0, "default_spread_pct_of_mid_if_unknown": 10.0,
    "liquidity_grades": {"A": {"min_oi": 5000, "min_volume": 1000, "max_spread_pct": 5.0},
                         "B": {"min_oi": 1000, "min_volume": 200, "max_spread_pct": 10.0},
                         "C": {"min_oi": 250, "min_volume": 25, "max_spread_pct": 20.0}},
    "rich_allowed_liquidity_grades": ["A", "B", "C"], "rich_min_score": 1.25, "rich_min_net_hit_rate": 70.0,
    "rich_min_quarters": 6, "nasdaq_calendar_horizon_days": 120, "morning_session_cutoff_hour_ct": 12}


def load():
    c = dict(DEFAULTS)
    p = os.path.join(_DIR, "config.json")
    if os.path.exists(p):
        c.update({k: v for k, v in json.load(open(p)).items() if not k.startswith("_")})
    return c


CFG = load()
