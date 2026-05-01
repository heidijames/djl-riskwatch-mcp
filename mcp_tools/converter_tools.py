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


INPUT_GUIDE = {
    "cargo_type": {
        "general": "Non-perishable cargo with low urgency.",
        "critical": "High-priority cargo where delays may disrupt operations or supply continuity.",
        "temperature": "Temperature-sensitive, perishable, or low shelf-life cargo.",
    },
    "weather_condition": {
        "normal": "No known weather disruption or normal operating conditions.",
        "moderate": "Heavy rain, strong wind, rough sea, or conditions that may cause minor delays.",
        "severe": "Storm, cyclone, port closure, vessel hold, or major weather warning.",
    },
    "geopolitical_risk": {
        "low": "Stable route with no known security, sanctions, or trade disruption.",
        "medium": "Regional tension, advisory warning, minor disruption, or possible route impact.",
        "high": "Conflict, sanctions, blocked route, piracy/security warning, or major disruption.",
    },
    "carrier_reliability": {
        "high": "Carrier has strong on-time performance and no known recent reliability issues.",
        "medium": "Carrier has occasional delays or mixed reliability history.",
        "low": "Carrier has frequent delays, cancellations, poor schedule reliability, or known service issues.",
    },
}


def pending_decision_log() -> Dict[str, Any]:
    return {
        "decision_status": "pending",
        "decision": None,
        "decision_by": None,
        "decision_reason": None,
        "timestamp": None,
    }


def assess_route_risk_value(
    origin: str,
    destination: str,
    cargo_type: str,
    weather_condition: str,
    geopolitical_risk: str,
    carrier_reliability: str,
) -> Dict[str, Any]:
    """
    Assess pre-dispatch shipment risk using port profiles, cargo sensitivity,
    external risk inputs, and historical fallback data.
    """

    valid_cargo = ["general", "critical", "temperature"]
    valid_weather = ["normal", "moderate", "severe"]
    valid_geo = ["low", "medium", "high"]
    valid_carrier = ["high", "medium", "low"]

    if cargo_type not in valid_cargo:
        return {"error": "Invalid cargo_type", "valid_options": valid_cargo, "input_guide": INPUT_GUIDE}

    if weather_condition not in valid_weather:
        return {"error": "Invalid weather_condition", "valid_options": valid_weather, "input_guide": INPUT_GUIDE}

    if geopolitical_risk not in valid_geo:
        return {"error": "Invalid geopolitical_risk", "valid_options": valid_geo, "input_guide": INPUT_GUIDE}

    if carrier_reliability not in valid_carrier:
        return {"error": "Invalid carrier_reliability", "valid_options": valid_carrier, "input_guide": INPUT_GUIDE}

    thresholds = risk_thresholds()
    ports = port_risk_profiles()

    score = 0

    origin_profile = ports.get(origin, {})
    destination_profile = ports.get(destination, {})

    origin_risk = origin_profile.get("risk_score", origin_profile.get("base_risk", 1))
    destination_risk = destination_profile.get("risk_score", destination_profile.get("base_risk", 1))

    score += origin_risk
    score += destination_risk

    cargo_weights = thresholds.get(
        "cargo_weights",
        {"general": 1, "critical": 3, "temperature": 4},
    )
    score += cargo_weights.get(cargo_type, 1)

    weather_map = {"normal": 0, "moderate": 1, "severe": 2}
    geo_map = {"low": 0, "medium": 1, "high": 2}
    carrier_map = {"high": 0, "medium": 1, "low": 2}

    score += weather_map[weather_condition]
    score += geo_map[geopolitical_risk]
    score += carrier_map[carrier_reliability]

    historical_rows = kaggle_supply_chain_fallback()
    route_matches = [
        row
        for row in historical_rows
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

    actions = thresholds.get(
        "actions",
        {
            "low": "Proceed as planned.",
            "medium": "Proceed with caution and monitor closely.",
            "high": "Escalate and review alternative carrier, sailing schedule, or route before dispatch.",
        },
    )

    recommended_actions = [actions.get(risk_level)]

    if risk_level == "high":
        recommended_actions.extend(
            [
                "Escalate to operations manager before confirming dispatch.",
                "Review alternative carrier or sailing schedule before shipment is loaded.",
                "Prepare customer communication draft if delay risk remains high.",
            ]
        )
    elif risk_level == "medium":
        recommended_actions.extend(
            [
                "Proceed only after reviewing current conditions.",
                "Increase monitoring after dispatch.",
                "Prepare internal note for operations team.",
            ]
        )
    else:
        recommended_actions.extend(
            [
                "Proceed with normal booking process.",
                "Apply standard monitoring schedule.",
            ]
        )

    return {
        "origin": origin,
        "destination": destination,
        "risk_score": score,
        "risk_level": risk_level,
        "recommended_actions": recommended_actions,
        "contributing_factors": {
            "origin_port_risk": origin_risk,
            "destination_port_risk": destination_risk,
            "cargo_type": cargo_type,
            "weather_condition": weather_condition,
            "geopolitical_risk": geopolitical_risk,
            "carrier_reliability": carrier_reliability,
            "historical_route_matches": len(route_matches),
        },
        "approval": {
            "required": risk_level in ["medium", "high"],
            "required_role": "manager" if risk_level == "high" else "operations_staff",
            "status": "pending" if risk_level in ["medium", "high"] else "not_required",
        },
        "decision_log": pending_decision_log(),
        "system_note": "The system provides recommendations only. It does not execute bookings, rerouting, carrier contact, or customer communication automatically.",
        "input_guide": INPUT_GUIDE,
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

    valid_cargo = ["general", "critical", "temperature"]

    if cargo_type not in valid_cargo:
        return {
            "error": "Invalid cargo_type",
            "valid_options": valid_cargo,
            "input_guide": INPUT_GUIDE,
        }

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

    if delay_hours <= 0:
        risk_level = "low"
        alert_flag = False
        recommended_actions = [
            "Shipment is on schedule.",
            "Continue standard monitoring.",
        ]
    else:
        if cargo_type == "temperature":
            if delay_hours >= 24:
                risk_level = "high"
                alert_flag = True
                recommended_actions = [
                    "Escalate immediately to operations manager.",
                    "Request latest carrier status and reefer/temperature-control confirmation.",
                    "Prepare customer communication draft.",
                    "Prioritise unloading, clearance, or receiving arrangements on arrival.",
                    "Record decision and reason in the decision log.",
                ]
            elif delay_hours >= 12:
                risk_level = "medium"
                alert_flag = True
                recommended_actions = [
                    "Notify operations team.",
                    "Verify temperature-control status with carrier.",
                    "Increase monitoring frequency.",
                    "Prepare internal note for possible customer update.",
                ]
            else:
                risk_level = "low"
                alert_flag = False
                recommended_actions = [
                    "Continue monitoring due to temperature-sensitive cargo.",
                    "Check for further ETA changes.",
                ]

        elif cargo_type == "critical":
            if delay_hours >= 36:
                risk_level = "high"
                alert_flag = True
                recommended_actions = [
                    "Escalate to operations manager.",
                    "Request updated carrier status.",
                    "Review downstream operational impact.",
                    "Prepare customer communication draft.",
                    "Record decision and reason in the decision log.",
                ]
            elif delay_hours >= 18:
                risk_level = "medium"
                alert_flag = True
                recommended_actions = [
                    "Notify operations team.",
                    "Monitor revised ETA closely.",
                    "Prepare contingency note for affected internal teams.",
                ]
            else:
                risk_level = "low"
                alert_flag = False
                recommended_actions = [
                    "Continue monitoring.",
                    "Update internal ETA records.",
                ]

        else:  # general cargo
            if delay_hours >= 48:
                risk_level = "high"
                alert_flag = True
                recommended_actions = [
                    "Escalate to operations team.",
                    "Request updated carrier status.",
                    "Prepare customer update if delay affects delivery commitment.",
                    "Update receiving or warehouse schedule.",
                    "Record decision and reason in the decision log.",
                ]
            elif delay_hours >= 24:
                risk_level = "medium"
                alert_flag = True
                recommended_actions = [
                    "Notify operations team.",
                    "Update ETA records.",
                    "Continue monitoring.",
                ]
            else:
                risk_level = "low"
                alert_flag = False
                recommended_actions = [
                    "Continue standard monitoring.",
                    "No customer communication required yet.",
                ]

    return {
        "shipment_id": shipment_id,
        "original_eta": original_eta,
        "revised_eta": revised_eta,
        "delay_hours": delay_hours,
        "cargo_type": cargo_type,
        "risk_level": risk_level,
        "alert_flag": alert_flag,
        "recommended_actions": recommended_actions,
        "approval": {
            "required": alert_flag,
            "required_role": "manager" if risk_level == "high" else "operations_staff",
            "status": "pending" if alert_flag else "not_required",
        },
        "decision_log": pending_decision_log(),
        "system_note": "In-transit rerouting or carrier switching is usually limited. The system recommends escalation, carrier follow-up, ETA updates, handling prioritisation, and communication preparation only.",
    }


def prepare_delay_communication_value(
    shipment_id: str,
    customer_id: str,
    delay_hours: int,
    risk_level: str,
    revised_eta: str,
) -> Dict[str, Any]:
    """
    Generate an internal alert and customer-facing email draft for shipment delays.
    The system does not send messages automatically.
    """

    valid_risk = ["low", "medium", "high"]

    if risk_level not in valid_risk:
        return {
            "error": "Invalid risk_level",
            "valid_options": valid_risk,
        }

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
        "risk_level": risk_level,
        "delay_hours": delay_hours,
        "revised_eta": revised_eta,
        "internal_alert": internal_alert,
        "customer_email_draft": customer_email,
        "recommended_actions": [
            "Review internal alert.",
            "Manager reviews and edits customer email draft if required.",
            "Send customer update only after approval.",
            "Log final decision and communication outcome.",
        ],
        "approval": {
            "required": True,
            "required_role": "manager",
            "status": "pending",
        },
        "decision_log": pending_decision_log(),
        "system_note": "This tool generates drafts only. It does not send emails or execute communication automatically.",
    }


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
        "description": """
Monitor an in-transit shipment by comparing original ETA and revised ETA.

Input guide:
- original_eta: expected arrival date, format YYYY-MM-DD
- revised_eta: updated arrival date from carrier/shipping line, format YYYY-MM-DD
- cargo_type:
  general = standard cargo
  critical = high priority cargo
  temperature = perishable or temperature-sensitive cargo

Note:
- The tool does not reroute shipments in transit.
- It interprets delay impact and recommends follow-up actions.
""",
        "func": monitor_in_transit_risk_value,
        "tags": {"logistics", "monitoring", "delay"},
    },
    {
        "name": "prepare_delay_communication",
        "description": """
Generate internal alerts and customer email drafts for shipment delays.

Input guide:
- shipment_id: unique shipment reference
- customer_id: must match customer_data.json
- delay_hours: total delay duration in hours
- risk_level: low | medium | high
- revised_eta: updated arrival date, format YYYY-MM-DD

Note:
- This tool drafts messages only.
- Customer communication requires manager approval before sending.
""",
        "func": prepare_delay_communication_value,
        "tags": {"logistics", "communication", "delay"},
    },
]