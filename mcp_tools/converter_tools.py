# RiskWatch logic and HTTP endpoints are defined here so they can be reused
# by both the FastAPI app and the MCP tool registrations.

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter

from mcp_resources.converter_resources import (
    risk_thresholds,
    port_risk_profiles,
    customer_data,
    kaggle_supply_chain_fallback,
)

router = APIRouter(prefix="", tags=["riskwatch"])


# --- Core helpers ------------------------------------------------------------

def assess_route_risk_value(
    origin: str,
    destination: str,
    cargo_type: str,
    weather_condition: str,
    geopolitical_risk: str,
    carrier_reliability: str,
) -> Dict[str, Any]:
    """
    Assess pre-dispatch shipment risk using rules, port profiles,
    external risk inputs, and historical fallback data.
    """

    valid_cargo = ["general", "critical", "temperature"]
    valid_weather = ["normal", "moderate", "severe"]
    valid_geo = ["low", "medium", "high"]
    valid_carrier = ["high", "medium", "low"]

    if cargo_type not in valid_cargo:
        return {"error": "Invalid cargo_type", "valid_options": valid_cargo}

    if weather_condition not in valid_weather:
        return {"error": "Invalid weather_condition", "valid_options": valid_weather}

    if geopolitical_risk not in valid_geo:
        return {"error": "Invalid geopolitical_risk", "valid_options": valid_geo}

    if carrier_reliability not in valid_carrier:
        return {"error": "Invalid carrier_reliability", "valid_options": valid_carrier}

    thresholds = risk_thresholds()
    ports = port_risk_profiles()

    score = 0

    origin_profile = ports.get(origin, {})
    destination_profile = ports.get(destination, {})

    origin_risk = origin_profile.get("risk_score", origin_profile.get("base_risk", 1))
    destination_risk = destination_profile.get("risk_score", destination_profile.get("base_risk", 1))

    score += origin_risk
    score += destination_risk

    cargo_weights = thresholds.get("cargo_weights", {
        "general": 1,
        "critical": 3,
        "temperature": 4,
    })

    score += cargo_weights.get(cargo_type, 1)

    weather_map = {"normal": 0, "moderate": 1, "severe": 2}
    geo_map = {"low": 0, "medium": 1, "high": 2}
    carrier_map = {"high": 0, "medium": 1, "low": 2}

    score += weather_map[weather_condition]
    score += geo_map[geopolitical_risk]
    score += carrier_map[carrier_reliability]

    historical_rows = kaggle_supply_chain_fallback()
    route_matches = [
        row for row in historical_rows
        if origin in row.get("Origin_Port", "")
        and destination in row.get("Destination_Port", "")
    ]

    if len(route_matches) >= 3:
        score += 1

    if score >= 8:
        risk_level = "high"
    elif score >= 4:
        risk_level = "medium"
    else:
        risk_level = "low"

    actions = thresholds.get("actions", {
        "low": "Proceed as planned.",
        "medium": "Proceed with caution and monitor closely.",
        "high": "Escalate and review alternative carrier, sailing schedule, or route.",
    })

    return {
        "origin": origin,
        "destination": destination,
        "risk_score": score,
        "risk_level": risk_level,
        "recommended_action": actions.get(risk_level),
        "contributing_factors": {
            "origin_port_risk": origin_risk,
            "destination_port_risk": destination_risk,
            "cargo_type": cargo_type,
            "weather_condition": weather_condition,
            "geopolitical_risk": geopolitical_risk,
            "carrier_reliability": carrier_reliability,
            "historical_route_matches": len(route_matches),
        },
        "input_guide": {
            "cargo_type": {
                "general": "Non-perishable cargo with low urgency.",
                "critical": "High-priority cargo where delays may disrupt operations.",
                "temperature": "Perishable or temperature-sensitive cargo with low shelf life.",
            },
            "weather_condition": {
                "normal": "No known weather disruption.",
                "moderate": "Heavy rain, wind, or rough sea causing possible delay.",
                "severe": "Storm, cyclone, port closure, or major weather warning.",
            },
            "geopolitical_risk": {
                "low": "Stable route with no known disruption.",
                "medium": "Minor advisory, tension, or possible disruption.",
                "high": "Conflict, sanctions, blocked route, or major security warning.",
            },
            "carrier_reliability": {
                "high": "Consistent on-time performance.",
                "medium": "Occasional delays.",
                "low": "Frequent delays or known schedule unreliability.",
            },
        },
    }


def monitor_in_transit_risk_value(
    shipment_id: str,
    original_eta: str,
    revised_eta: str,
    cargo_type: str,
) -> Dict[str, Any]:
    """
    Monitor an in-transit shipment by comparing original ETA and revised ETA.
    Date format expected: YYYY-MM-DD.
    """

    thresholds = risk_thresholds()

    try:
        original = datetime.strptime(original_eta, "%Y-%m-%d")
        revised = datetime.strptime(revised_eta, "%Y-%m-%d")
    except ValueError:
        return {
            "error": "Invalid date format. Use YYYY-MM-DD.",
            "example": "2026-05-10",
        }

    delay_days = (revised - original).days
    delay_hours = delay_days * 24

    delay_limits = thresholds.get("delay_thresholds", {
        "low": 6,
        "medium": 18,
        "high": 36,
    })

    if delay_hours >= delay_limits.get("high", 36):
        risk_level = "high"
        alert_flag = True
        recommendation = "Escalate immediately and prepare customer communication."
    elif delay_hours >= delay_limits.get("medium", 18):
        risk_level = "medium"
        alert_flag = True
        recommendation = "Monitor closely and notify operations team."
    elif delay_hours > 0:
        risk_level = "low"
        alert_flag = False
        recommendation = "Continue monitoring."
    else:
        risk_level = "low"
        alert_flag = False
        recommendation = "Shipment is on schedule."

    if cargo_type == "temperature" and delay_hours > 0:
        alert_flag = True
        recommendation = "Escalate due to temperature-sensitive cargo."

    return {
        "shipment_id": shipment_id,
        "original_eta": original_eta,
        "revised_eta": revised_eta,
        "delay_hours": delay_hours,
        "risk_level": risk_level,
        "alert_flag": alert_flag,
        "recommendation": recommendation,
    }


def prepare_delay_communication_value(
    shipment_id: str,
    customer_id: str,
    delay_hours: int,
    risk_level: str,
    revised_eta: str,
) -> Dict[str, Any]:
    """
    Generate internal alert and customer email draft for delayed shipments.
    """

    customers = customer_data().get("customers", [])
    customer = next(
        (item for item in customers if item.get("customer_id") == customer_id),
        None,
    )

    if not customer:
        return {
            "error": "Customer not found",
            "customer_id": customer_id,
        }

    contact_person = customer.get("contact_person", "Customer")
    customer_name = customer.get("name", "Customer")
    email = customer.get("email", "")

    internal_alert = (
        f"Shipment {shipment_id} is currently classified as {risk_level.upper()} risk. "
        f"Estimated delay is {delay_hours} hours. Revised ETA: {revised_eta}. "
        f"Manager review is recommended before customer notification."
    )

    customer_email = (
        f"Dear {contact_person},\n\n"
        f"We are writing to provide an update regarding shipment {shipment_id}. "
        f"The shipment is currently experiencing an estimated delay of {delay_hours} hours. "
        f"The revised ETA is {revised_eta}.\n\n"
        f"Our operations team is monitoring the shipment closely and will provide further updates "
        f"if the situation changes.\n\n"
        f"Kind regards,\n"
        f"DJL RiskWatch Operations Team"
    )

    return {
        "shipment_id": shipment_id,
        "customer": customer_name,
        "customer_email_address": email,
        "internal_alert": internal_alert,
        "customer_email_draft": customer_email,
        "approval_note": "Customer email draft requires manager approval before sending.",
    }


# --- FastAPI endpoints -------------------------------------------------------

@router.post("/assess-route-risk")
def assess_route_risk(
    origin: str,
    destination: str,
    cargo_type: str,
    weather_condition: str,
    geopolitical_risk: str,
    carrier_reliability: str,
):
    result = assess_route_risk_value(
        origin,
        destination,
        cargo_type,
        weather_condition,
        geopolitical_risk,
        carrier_reliability,
    )
    return {"result": result, "operation": "assess_route_risk"}


@router.post("/monitor-in-transit-risk")
def monitor_in_transit_risk(
    shipment_id: str,
    original_eta: str,
    revised_eta: str,
    cargo_type: str,
):
    result = monitor_in_transit_risk_value(
        shipment_id,
        original_eta,
        revised_eta,
        cargo_type,
    )
    return {"result": result, "operation": "monitor_in_transit_risk"}


@router.post("/prepare-delay-communication")
def prepare_delay_communication(
    shipment_id: str,
    customer_id: str,
    delay_hours: int,
    risk_level: str,
    revised_eta: str,
):
    result = prepare_delay_communication_value(
        shipment_id,
        customer_id,
        delay_hours,
        risk_level,
        revised_eta,
    )
    return {"result": result, "operation": "prepare_delay_communication"}


# --- Metadata for MCP tool registration -------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "assess_route_risk",
        "description": """
Evaluate pre-dispatch shipment risk and recommend actions.

Input guide:
- cargo_type:
  general = non-perishable cargo with low urgency
  critical = high-priority cargo where delays may disrupt operations
  temperature = temperature-sensitive, perishable, or low shelf-life cargo

- weather_condition:
  normal = no known weather disruption
  moderate = heavy rain, wind, rough sea, or possible minor delay
  severe = storm, cyclone, port closure, vessel hold, or major weather warning

- geopolitical_risk:
  low = stable route
  medium = regional tension, advisory warning, or possible disruption
  high = conflict, sanctions, blocked route, piracy/security warning, or major disruption

- carrier_reliability:
  high = strong on-time performance
  medium = occasional delays
  low = frequent delays or known schedule unreliability
""",
        "func": assess_route_risk_value,
        "tags": {"logistics", "risk", "pre-dispatch"},
    },
    {
        "name": "monitor_in_transit_risk",
        "description": "Monitor an in-transit shipment by comparing original ETA and revised ETA.",
        "func": monitor_in_transit_risk_value,
        "tags": {"logistics", "monitoring", "delay"},
    },
    {
        "name": "prepare_delay_communication",
        "description": "Generate internal alerts and customer email drafts for shipment delays.",
        "func": prepare_delay_communication_value,
        "tags": {"logistics", "communication", "delay"},
    },
]