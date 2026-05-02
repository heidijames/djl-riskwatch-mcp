"""RiskWatch MCP tools for DJL Logistics."""

from __future__ import annotations

import csv
from io import StringIO
from statistics import mean
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
    "origin_port": {
        "example": "Singapore",
        "description": "Starting port for the shipment route.",
    },
    "destination_port": {
        "example": "Port Klang",
        "description": "Destination port for the shipment route.",
    },
    "planned_dispatch_date": {
        "example": "2026-05-10",
        "description": "Planned shipment dispatch date in YYYY-MM-DD format.",
    },
}


def assess_route_risk(
    shipment_id: str,
    planned_dispatch_date: str,
    origin_port: str,
    destination_port: str,
    cargo_type: str
) -> dict:
    from mcp_resources.converter_resources import (
        port_risk_profiles,
        kaggle_supply_chain_fallback,
    )

    ports = port_risk_profiles()

    def clean(value):
        return str(value).strip()

    def norm(value):
        return clean(value).lower()

    def get_port_profile(port_name):
        for name, profile in ports.items():
            if norm(name) == norm(port_name):
                return name, profile
        return port_name, {}

    def score_port(profile):
        if not profile:
            return 0, []

        score = 0
        drivers = []

        congestion = norm(profile.get("congestion_level", ""))
        delay = float(profile.get("average_delay_days", 0) or 0)
        risk = norm(profile.get("risk_level", ""))

        if congestion in ["high", "severe"]:
            score += 25
            drivers.append(f"High congestion level recorded at port: {congestion}.")

        if delay >= 3:
            score += 25
            drivers.append(f"Average port delay is {delay} days.")
        elif delay >= 1.5:
            score += 15
            drivers.append(f"Moderate average port delay is {delay} days.")

        if risk == "high":
            score += 25
            drivers.append("Port profile is classified as high risk.")
        elif risk == "medium":
            score += 15
            drivers.append("Port profile is classified as medium risk.")

        return score, drivers

    def cargo_sensitivity(cargo):
        cargo = norm(cargo)

        if cargo == "critical":
            return 20, "critical", "Critical cargo has lower tolerance for dispatch disruption."

        if cargo == "temperature":
            return 25, "temperature-sensitive", (
                "Temperature-sensitive cargo may create storage, handling, "
                "or quality risks if delayed."
            )

        return 5, "general", "General cargo has more flexibility if minor dispatch delays occur."

    def classify(score):
        if score >= 70:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    def delay_window(level, cargo):
        cargo = norm(cargo)

        if level == "high":
            if cargo in ["critical", "temperature"]:
                return "Hold dispatch for 24–48 hours unless port and carrier readiness are confirmed."
            return "Consider delaying dispatch by 24 hours if port congestion is unresolved."

        if level == "medium":
            if cargo in ["critical", "temperature"]:
                return "Proceed only after same-day operational confirmation."
            return "Proceed with monitoring; delay is not required unless conditions worsen."

        return "Proceed as planned."

    origin_name, origin_profile = get_port_profile(origin_port)
    dest_name, dest_profile = get_port_profile(destination_port)

    origin_score, origin_drivers = score_port(origin_profile)
    dest_score, dest_drivers = score_port(dest_profile)
    cargo_score, derived_cargo_category, cargo_driver = cargo_sensitivity(cargo_type)

    historical_matches = []

    for row in kaggle_supply_chain_fallback():
        row_text = {norm(k): v for k, v in row.items()}

        row_origin = row_text.get("origin_port", "")
        row_dest = row_text.get("destination_port", "")
        row_product = row_text.get("product_category", "")

        route_match = (
            norm(origin_name) in norm(row_origin)
            or norm(dest_name) in norm(row_dest)
        )

        cargo_match = (
            norm(cargo_type) in norm(row_product)
            or norm(row_product) in norm(cargo_type)
        )

        if route_match or cargo_match:
            historical_matches.append(row)

    historical_score = 0

    if len(historical_matches) >= 10:
        historical_score = 20
    elif len(historical_matches) >= 5:
        historical_score = 12
    elif len(historical_matches) >= 1:
        historical_score = 6

    total_score = min(100, origin_score + dest_score + cargo_score + historical_score)
    risk_level = classify(total_score)

    risk_drivers = []

    risk_drivers.extend([f"Origin port: {driver}" for driver in origin_drivers])
    risk_drivers.extend([f"Destination port: {driver}" for driver in dest_drivers])

    if norm(cargo_type) in ["critical", "temperature"]:
        risk_drivers.append(cargo_driver)

    if historical_score > 0:
        risk_drivers.append(
            f"CSV historical data found {len(historical_matches)} related route or cargo records."
        )

    if not risk_drivers:
        risk_drivers.append(
            "No active high-risk driver detected from the connected CSV and port profiles."
        )

    if risk_level == "high":
        actions = [
            "Do not release shipment until the operations team confirms port readiness.",
            "Check whether dispatch can be moved outside the highest-risk delay window.",
            "Prepare customer-facing delay wording but do not send without approval.",
            "Confirm storage or holding arrangements before cargo reaches the port.",
        ]
    elif risk_level == "medium":
        actions = [
            "Proceed only after confirming port acceptance and booking status.",
            "Monitor the route again before dispatch.",
            "Flag shipment internally so operations can react quickly if delay increases.",
        ]
    else:
        actions = [
            "Proceed with planned dispatch.",
            "Record the assessment result for shipment traceability.",
            "Recheck only if port profile or planned dispatch date changes.",
        ]

    if norm(cargo_type) == "temperature":
        actions.insert(
            0,
            "Confirm temperature-control handling and storage availability before dispatch."
        )
    elif norm(cargo_type) == "critical":
        actions.insert(
            0,
            "Confirm latest acceptable delivery window with operations before dispatch."
        )

    return {
        "summary": {
            "shipment_id": shipment_id,
            "planned_dispatch_date": planned_dispatch_date,
            "origin_port": origin_name,
            "destination_port": dest_name,
            "cargo_type": cargo_type,
            "risk_level": risk_level,
            "risk_score": total_score,
            "message": (
                f"Pre-dispatch risk is {risk_level.upper()} based on port profiles, "
                "cargo sensitivity, and CSV historical context."
            ),
        },
        "risk_drivers": risk_drivers,
        "historical_context": {
            "csv_resource_used": "kaggle_supply_chain_fallback",
            "matching_records_found": len(historical_matches),
            "interpretation": (
                "Historical CSV records were used as supporting context only. "
                "Risk was not manually entered by the user."
            ),
        },
        "derived_risk_categories": {
            "origin_port_risk_score": origin_score,
            "destination_port_risk_score": dest_score,
            "cargo_sensitivity_category": derived_cargo_category,
            "historical_context_score": historical_score,
        },
        "decision_guidance": {
            "recommended_decision": delay_window(risk_level, cargo_type),
            "approval_required": risk_level == "high"
            or norm(cargo_type) in ["critical", "temperature"],
        },
        "recommended_actions": actions,
        "planning_warning": (
            "If dispatch is delayed or port dwell time increases, DJL should check possible port storage, "
            "detention, demurrage, or temperature-controlled holding costs before confirming the plan."
        ),
        "system_note": (
            "Risk is derived from connected MCP resources: JSON port profiles and the local CSV fallback dataset. "
            "No external API, weather feed, geopolitical feed, or carrier manual risk input was used."
        ),
    }

def monitor_in_transit_risk(
    shipment_id: str,
    original_eta: str,
    revised_eta: str,
    cargo_type: str
) -> dict:
    from datetime import datetime

    def norm(value):
        return str(value).strip().lower()

    def parse_date(value):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError("ETA dates must be in YYYY-MM-DD format, for example 2026-05-03.")

    original = parse_date(original_eta)
    revised = parse_date(revised_eta)

    delay_hours = int((revised - original).total_seconds() / 3600)

    cargo = norm(cargo_type)

    if delay_hours <= 0:
        status = "on_time_or_improved"
    elif delay_hours <= 24:
        status = "minor_delay"
    elif delay_hours <= 72:
        status = "moderate_delay"
    else:
        status = "major_delay"

    if cargo == "temperature":
        if delay_hours > 24:
            urgency = "high"
        elif delay_hours > 0:
            urgency = "medium"
        else:
            urgency = "low"
    elif cargo == "critical":
        if delay_hours > 48:
            urgency = "high"
        elif delay_hours > 0:
            urgency = "medium"
        else:
            urgency = "low"
    else:
        if delay_hours > 72:
            urgency = "high"
        elif delay_hours > 24:
            urgency = "medium"
        else:
            urgency = "low"

    if delay_hours <= 0:
        impact = "No delay impact detected. Revised ETA is on time or earlier than the original ETA."
        priority_actions = [
            "Record revised ETA in the shipment file.",
            "No escalation required."
        ]
        secondary_actions = [
            "Continue standard shipment monitoring."
        ]
    elif cargo == "temperature":
        impact = (
            "Delay may affect temperature-control planning, receiving arrangements, "
            "storage availability, and product quality risk."
        )
        priority_actions = [
            "Confirm temperature-control status with the carrier immediately.",
            "Check whether cold storage or priority receiving is required at destination.",
            "Notify operations manager if delay exceeds acceptable receiving window."
        ]
        secondary_actions = [
            "Prepare customer update draft for review.",
            "Record delay reason and revised ETA in the shipment log."
        ]
    elif cargo == "critical":
        impact = (
            "Delay may affect operational continuity, production planning, customer commitments, "
            "or downstream delivery schedules."
        )
        priority_actions = [
            "Escalate revised ETA to operations team.",
            "Check whether the receiving or production schedule needs adjustment.",
            "Confirm whether an alternative recovery action is required."
        ]
        secondary_actions = [
            "Prepare internal delay briefing.",
            "Prepare customer update draft if customer delivery commitment may be affected."
        ]
    else:
        impact = (
            "Delay affects delivery planning but is less sensitive than critical or temperature cargo."
        )
        if delay_hours <= 24:
            priority_actions = [
                "Update shipment record with revised ETA.",
                "Monitor for further ETA changes."
            ]
            secondary_actions = [
                "Inform operations only if the delay affects receiving schedule."
            ]
        elif delay_hours <= 72:
            priority_actions = [
                "Notify operations team of moderate delay.",
                "Check destination receiving availability for the revised ETA."
            ]
            secondary_actions = [
                "Prepare customer update only if delivery commitment is affected.",
                "Record carrier delay reason if available."
            ]
        else:
            priority_actions = [
                "Escalate to operations manager due to major delay.",
                "Review whether downstream delivery or customer commitment is affected."
            ]
            secondary_actions = [
                "Prepare customer communication draft for approval.",
                "Record delay and follow-up action in the decision log."
            ]

    if urgency == "high":
        escalation = {
            "required": True,
            "level": "manager",
            "guidance": "Escalate immediately because delay length and cargo sensitivity create high operational risk."
        }
    elif urgency == "medium":
        escalation = {
            "required": True,
            "level": "operations_team",
            "guidance": "Escalate internally so the team can adjust receiving, storage, or customer planning."
        }
    else:
        escalation = {
            "required": False,
            "level": "standard_monitoring",
            "guidance": "No formal escalation required unless ETA changes again."
        }

    return {
        "summary": {
            "shipment_id": shipment_id,
            "cargo_type": cargo_type,
            "original_eta": original_eta,
            "revised_eta": revised_eta,
            "message": f"In-transit monitoring shows {status.replace('_', ' ')} with {urgency.upper()} urgency."
        },
        "eta_analysis": {
            "delay_hours": delay_hours,
            "delay_days": round(delay_hours / 24, 2),
            "status": status
        },
        "urgency": {
            "level": urgency,
            "reason": f"Urgency is based on a {delay_hours}-hour ETA change and cargo type '{cargo_type}'."
        },
        "impact_assessment": impact,
        "recommended_actions": {
            "priority": priority_actions,
            "secondary": secondary_actions
        },
        "escalation_guidance": escalation,
        "details": {
            "revised_eta_is_user_provided": True,
            "prediction_used": False,
            "cargo_sensitivity_applied": cargo,
            "monitoring_stage": "in_transit"
        },
        "system_note": (
            "Revised ETA is treated as an input from carrier or operations update. "
            "The system does not predict ETA and does not use external APIs."
        )
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
def assess_route_risk_endpoint(
    shipment_id: str,
    planned_dispatch_date: str,
    origin_port: str,
    destination_port: str,
    cargo_type: str,
):
    result = assess_route_risk(
        shipment_id,
        planned_dispatch_date,
        origin_port,
        destination_port,
        cargo_type,
    )
    return {"result": result, "operation": "assess_route_risk"}


@router.post("/monitor-in-transit-risk")
def monitor_in_transit_risk_endpoint(
    shipment_id: str,
    original_eta: str,
    revised_eta: str,
    cargo_type: str,
):
    result = monitor_in_transit_risk(
        shipment_id,
        original_eta,
        revised_eta,
        cargo_type,
    )
    return {"result": result, "operation": "monitor_in_transit_risk"}


@router.post("/prepare-delay-communication")
def prepare_delay_communication_endpoint(
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
def record_operational_action_endpoint(
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
        "func": assess_route_risk,
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
        "func": monitor_in_transit_risk,
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