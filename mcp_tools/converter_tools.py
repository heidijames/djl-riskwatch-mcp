from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

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
        "moderate": "Heavy rain, strong wind, rough sea, or possible minor delays.",
        "severe": "Storm, cyclone, port closure, vessel hold, or major weather warning.",
    },
    "geopolitical_risk": {
        "low": "Stable route with no known disruption.",
        "medium": "Regional tension, advisory warning, or possible route impact.",
        "high": "Conflict, sanctions, blocked route, piracy/security warning, or major disruption.",
    },
    "carrier_reliability": {
        "high": "Strong on-time performance.",
        "medium": "Occasional delays or mixed reliability history.",
        "low": "Frequent delays, cancellations, or known schedule unreliability.",
    },
}


def assess_route_risk_value(
    shipment_id: str,
    origin: str,
    destination: str,
    cargo_type: str,
    weather_condition: str,
    geopolitical_risk: str,
    carrier_reliability: str,
) -> Dict[str, Any]:
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

    origin_profile = ports.get(origin, {})
    destination_profile = ports.get(destination, {})

    origin_risk = origin_profile.get("risk_score", origin_profile.get("base_risk", 1))
    destination_risk = destination_profile.get("risk_score", destination_profile.get("base_risk", 1))

    cargo_weights = thresholds.get("cargo_weights", {"general": 1, "critical": 3, "temperature": 4})
    weather_map = {"normal": 0, "moderate": 1, "severe": 2}
    geo_map = {"low": 0, "medium": 1, "high": 2}
    carrier_map = {"high": 0, "medium": 1, "low": 2}

    score = (
        origin_risk
        + destination_risk
        + cargo_weights.get(cargo_type, 1)
        + weather_map[weather_condition]
        + geo_map[geopolitical_risk]
        + carrier_map[carrier_reliability]
    )

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
        message = "High pre-dispatch risk detected."
    elif score >= 4:
        risk_level = "medium"
        message = "Medium pre-dispatch risk detected."
    else:
        risk_level = "low"
        message = "Low pre-dispatch risk detected."

    if risk_level == "high":
        recommended_actions = [
            f"Review alternative carrier or sailing schedule for shipment {shipment_id} before loading.",
            f"Delay dispatch if {weather_condition} weather, {geopolitical_risk} geopolitical risk, or carrier reliability concerns remain unresolved.",
            "Prepare customer communication draft if the risk may affect the customer’s expected delivery timeline.",
        ]
    elif risk_level == "medium":
        recommended_actions = [
            f"Review current route conditions before confirming dispatch for shipment {shipment_id}.",
            "Proceed only if operations team is comfortable with current risk conditions.",
            "Increase monitoring frequency after dispatch.",
        ]
    else:
        recommended_actions = [
            f"Proceed with normal booking process for shipment {shipment_id}.",
            "Apply standard monitoring schedule after dispatch.",
        ]

    return {
        "summary": {
            "shipment_id": shipment_id,
            "origin": origin,
            "destination": destination,
            "risk_level": risk_level,
            "risk_score": score,
            "message": message,
        },
        "recommended_actions": recommended_actions,
        "details": {
            "origin_port_risk": origin_risk,
            "destination_port_risk": destination_risk,
            "cargo_type": cargo_type,
            "weather_condition": weather_condition,
            "geopolitical_risk": geopolitical_risk,
            "carrier_reliability": carrier_reliability,
            "historical_route_matches": len(route_matches),
        },
        "system_note": "The system provides recommendations only. It does not confirm dispatch, contact carriers, or send customer communication automatically.",
    }


def monitor_in_transit_risk_value(
    shipment_id: str,
    original_eta: str,
    revised_eta: str,
    cargo_type: str,
) -> Dict[str, Any]:
    valid_cargo = ["general", "critical", "temperature"]

    if cargo_type not in valid_cargo:
        return {"error": "Invalid cargo_type", "valid_options": valid_cargo, "input_guide": INPUT_GUIDE}

    try:
        original = datetime.strptime(original_eta, "%Y-%m-%d")
        revised = datetime.strptime(revised_eta, "%Y-%m-%d")
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD.", "example": "2026-05-10"}

    delay_days = (revised - original).days
    delay_hours = delay_days * 24

    if delay_hours <= 0:
        risk_level = "low"
        alert_flag = False
        message = "Shipment is currently on schedule."
        recommended_actions = [
            f"Continue standard monitoring for shipment {shipment_id}.",
            "No customer communication is required at this stage.",
        ]
    elif cargo_type == "temperature":
        if delay_hours >= 24:
            risk_level = "high"
            alert_flag = True
            message = "High in-transit delay risk detected for temperature-sensitive cargo."
            recommended_actions = [
                f"Request latest carrier status due to {delay_hours}-hour delay.",
                "Confirm reefer or temperature-control status with the carrier.",
                "Prepare customer communication draft due to high delay risk.",
                "Prioritise unloading, clearance, or receiving arrangements on arrival.",
            ]
        elif delay_hours >= 12:
            risk_level = "medium"
            alert_flag = True
            message = "Medium in-transit delay risk detected for temperature-sensitive cargo."
            recommended_actions = [
                f"Notify operations team of {delay_hours}-hour delay.",
                "Verify temperature-control status with carrier.",
                "Increase monitoring frequency.",
            ]
        else:
            risk_level = "low"
            alert_flag = False
            message = "Minor delay detected for temperature-sensitive cargo."
            recommended_actions = [
                f"Continue monitoring shipment {shipment_id} due to cargo sensitivity.",
                "Check for further ETA changes.",
            ]
    elif cargo_type == "critical":
        if delay_hours >= 36:
            risk_level = "high"
            alert_flag = True
            message = "High in-transit delay risk detected for critical cargo."
            recommended_actions = [
                f"Request updated carrier status due to {delay_hours}-hour delay.",
                "Review downstream operational impact.",
                "Prepare customer communication draft if delay affects commitments.",
            ]
        elif delay_hours >= 18:
            risk_level = "medium"
            alert_flag = True
            message = "Medium in-transit delay risk detected for critical cargo."
            recommended_actions = [
                f"Notify operations team of {delay_hours}-hour delay.",
                "Monitor revised ETA closely.",
                "Prepare contingency note for affected internal teams.",
            ]
        else:
            risk_level = "low"
            alert_flag = False
            message = "Minor delay detected for critical cargo."
            recommended_actions = [
                f"Continue monitoring shipment {shipment_id}.",
                "Update internal ETA records.",
            ]
    else:
        if delay_hours >= 48:
            risk_level = "high"
            alert_flag = True
            message = "High in-transit delay risk detected for general cargo."
            recommended_actions = [
                f"Request updated carrier status due to {delay_hours}-hour delay.",
                "Prepare customer update if delay affects delivery commitment.",
                "Update receiving or warehouse schedule.",
            ]
        elif delay_hours >= 24:
            risk_level = "medium"
            alert_flag = True
            message = "Medium in-transit delay risk detected for general cargo."
            recommended_actions = [
                f"Notify operations team of {delay_hours}-hour delay.",
                "Update ETA records.",
                "Continue monitoring.",
            ]
        else:
            risk_level = "low"
            alert_flag = False
            message = "Minor delay detected for general cargo."
            recommended_actions = [
                f"Continue standard monitoring for shipment {shipment_id}.",
                "No customer communication is required yet.",
            ]

    return {
        "summary": {
            "shipment_id": shipment_id,
            "cargo_type": cargo_type,
            "risk_level": risk_level,
            "delay_hours": delay_hours,
            "message": message,
        },
        "eta_update": {
            "original_eta": original_eta,
            "revised_eta": revised_eta,
        },
        "recommended_actions": recommended_actions,
        "details": {
            "alert_flag": alert_flag,
            "delay_basis": "Revised ETA compared with original ETA.",
            "note": "In-transit carrier switching or rerouting is usually limited. The system recommends follow-up and preparation actions only.",
        },
    }


def prepare_delay_communication_value(
    shipment_id: str,
    customer_id: str,
    delay_hours: int,
    risk_level: str,
    revised_eta: str,
) -> Dict[str, Any]:
    valid_risk = ["low", "medium", "high"]

    if risk_level not in valid_risk:
        return {"error": "Invalid risk_level", "valid_options": valid_risk}

    customers = customer_data().get("customers", [])
    customer = next((item for item in customers if item.get("customer_id") == customer_id), None)

    if not customer:
        return {"error": "Customer not found", "customer_id": customer_id}

    contact_person = customer.get("contact_person", "Customer")
    customer_name = customer.get("name", "Customer")
    email = customer.get("email", "")

    internal_alert = (
        f"Shipment {shipment_id} is classified as {risk_level.upper()} risk with an estimated "
        f"{delay_hours}-hour delay. Revised ETA: {revised_eta}."
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
        "summary": {
            "shipment_id": shipment_id,
            "customer": customer_name,
            "risk_level": risk_level,
            "delay_hours": delay_hours,
            "message": "Delay communication draft generated.",
        },
        "customer_contact": {
            "customer_id": customer_id,
            "contact_person": contact_person,
            "email": email,
        },
        "internal_alert": internal_alert,
        "customer_email_draft": customer_email,
        "recommended_actions": [
            "Review internal alert.",
            "Edit customer email draft if required.",
            "Send customer update only after operator review.",
            "Record final action using record_operational_action.",
        ],
        "system_note": "This tool generates drafts only. It does not send emails automatically.",
    }


def record_operational_action_value(
    shipment_id: str,
    stage: str,
    action: str,
    action_by: str,
    action_reason: str,
    notes: Optional[str] = None,
    estimated_delay_cost: Optional[float] = None,
    currency: Optional[str] = None,
    cost_basis: Optional[str] = None,
) -> Dict[str, Any]:
    valid_stages = ["pre_dispatch", "in_transit", "communication"]
    valid_actions = [
        "proceed",
        "delay_dispatch",
        "escalate",
        "contact_carrier",
        "notify_customer",
        "no_action",
        "override",
        "customer_email_sent",
        "customer_email_not_sent",
    ]

    if stage not in valid_stages:
        return {"error": "Invalid stage", "valid_options": valid_stages}

    if action not in valid_actions:
        return {"error": "Invalid action", "valid_options": valid_actions}

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "summary": {
            "shipment_id": shipment_id,
            "stage": stage,
            "action": action,
            "status": "recorded",
            "message": "Operational action recorded successfully.",
        },
        "action_log": {
            "shipment_id": shipment_id,
            "stage": stage,
            "action": action,
            "action_by": action_by,
            "action_reason": action_reason,
            "notes": notes,
            "estimated_delay_cost": estimated_delay_cost,
            "currency": currency,
            "cost_basis": cost_basis,
            "timestamp": timestamp,
        },
        "system_note": "This tool records the action taken by the operator. It does not execute the action automatically.",
    }


@router.post("/assess-route-risk")
def assess_route_risk(
    shipment_id: str,
    origin: str,
    destination: str,
    cargo_type: str,
    weather_condition: str,
    geopolitical_risk: str,
    carrier_reliability: str,
):
    result = assess_route_risk_value(
        shipment_id,
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
    result = monitor_in_transit_risk_value(shipment_id, original_eta, revised_eta, cargo_type)
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


@router.post("/record-operational-action")
def record_operational_action(
    shipment_id: str,
    stage: str,
    action: str,
    action_by: str,
    action_reason: str,
    notes: Optional[str] = None,
    estimated_delay_cost: Optional[float] = None,
    currency: Optional[str] = None,
    cost_basis: Optional[str] = None,
):
    result = record_operational_action_value(
        shipment_id,
        stage,
        action,
        action_by,
        action_reason,
        notes,
        estimated_delay_cost,
        currency,
        cost_basis,
    )
    return {"result": result, "operation": "record_operational_action"}


TOOL_DEFINITIONS = [
    {
        "name": "assess_route_risk",
        "description": """
Evaluate pre-dispatch shipment risk and recommend actions.

Input guide:
- shipment_id: unique shipment reference, e.g. SHP001
- cargo_type: general | critical | temperature
- weather_condition: normal | moderate | severe
- geopolitical_risk: low | medium | high
- carrier_reliability: high | medium | low
""",
        "func": assess_route_risk_value,
        "tags": {"logistics", "risk", "pre-dispatch"},
    },
    {
        "name": "monitor_in_transit_risk",
        "description": """
Monitor an in-transit shipment by comparing original ETA and revised ETA.

Input guide:
- shipment_id: unique shipment reference
- original_eta: expected arrival date, format YYYY-MM-DD
- revised_eta: updated arrival date from carrier/shipping line, format YYYY-MM-DD
- cargo_type: general | critical | temperature
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
""",
        "func": prepare_delay_communication_value,
        "tags": {"logistics", "communication", "delay"},
    },
    {
        "name": "record_operational_action",
        "description": """
Record an operational action taken by the operator.

Input guide:
- shipment_id: unique shipment reference
- stage: pre_dispatch | in_transit | communication
- action: proceed | delay_dispatch | escalate | contact_carrier | notify_customer | no_action | override | customer_email_sent | customer_email_not_sent
- action_by: operator name or role
- action_reason: short reason for the action
- notes: optional supporting notes
- estimated_delay_cost: optional estimated financial impact
- currency: optional currency, e.g. USD, SGD, AUD
- cost_basis: optional explanation of the cost estimate
""",
        "func": record_operational_action_value,
        "tags": {"logistics", "audit", "action-log"},
    },
]