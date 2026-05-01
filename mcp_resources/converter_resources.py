"""Reusable MCP resources for DJL RiskWatch."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = BASE_DIR / "resources"


def risk_thresholds() -> Dict[str, Any]:
    """Risk classification rules and delay thresholds."""
    with open(RESOURCES_DIR / "risk_thresholds.json", "r", encoding="utf-8") as f:
        return json.load(f)


def port_risk_profiles() -> Dict[str, Any]:
    """Port congestion and delay risk profiles."""
    with open(RESOURCES_DIR / "port_risk_profiles.json", "r", encoding="utf-8") as f:
        return json.load(f)


def customer_data() -> Dict[str, Any]:
    """Customer contact data for communication drafts."""
    with open(RESOURCES_DIR / "customer_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


def kaggle_supply_chain_fallback() -> List[Dict[str, Any]]:
    """
    Return sample fallback records from the Kaggle dataset.

    The dataset is filtered to Singapore-related shipments because Singapore
    is used as the main hub for the MVP.
    """
    path = RESOURCES_DIR / "global_supply_chain_risk_2026.csv"
    filtered_rows: List[Dict[str, Any]] = []

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            origin = row.get("Origin_Port", "")
            destination = row.get("Destination_Port", "")

            if "Singapore" in origin or "Singapore" in destination:
                filtered_rows.append(row)

            if len(filtered_rows) >= 10:
                break

    return filtered_rows


RESOURCE_DEFINITIONS = [
    {
        "name": "risk_thresholds",
        "description": "JSON rules for risk classification, delay thresholds, cargo sensitivity, and recommended actions.",
        "mime_type": "application/json",
        "func": risk_thresholds,
    },
    {
        "name": "port_risk_profiles",
        "description": "JSON reference data for Singapore-based port congestion and delay risk profiles.",
        "mime_type": "application/json",
        "func": port_risk_profiles,
    },
    {
        "name": "customer_data",
        "description": "JSON customer contact data used for delay communication drafts.",
        "mime_type": "application/json",
        "func": customer_data,
    },
    {
        "name": "kaggle_supply_chain_fallback",
        "description": "CSV fallback dataset sample filtered for Singapore-related shipments when live API data is unavailable.",
        "mime_type": "text/csv",
        "func": kaggle_supply_chain_fallback,
    },
]