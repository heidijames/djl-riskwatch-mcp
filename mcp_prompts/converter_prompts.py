"""Prompt templates for DJL RiskWatch (MCP-compatible)."""

from __future__ import annotations

from typing import List, Dict


# --- Prompt: Risk Briefing ---
def generate_risk_briefing_prompt() -> str:
    """
    Generate a clear operational risk briefing from shipment risk information.
    """
    return (
        "You are a logistics risk analyst. "
        "Generate a short shipment risk briefing using the shipment risk information "
        "provided by the operator or tool output. "
        "Explain the overall risk level, key contributing factors, possible delay impact, "
        "and recommended areas for operator attention. "
        "Do not make final decisions or claim that actions have already been taken."
    )


# --- Prompt: Escalation Alert ---
def escalation_alert_prompt() -> str:
    """
    Generate an escalation alert for high-risk shipment situations.
    """
    return (
        "You are an operations supervisor preparing an escalation alert. "
        "Create an urgent but professional escalation alert for a high-risk shipment "
        "using the information provided by the operator or tool output. "
        "Explain why escalation may be required, highlight possible business impact "
        "such as delay, cost, customer impact, or operational disruption, and identify "
        "what needs operator review. "
        "Do not approve actions, send communication, or assume decisions have already been made."
    )


# --- Register Prompts ---
PROMPT_DEFINITIONS = [
    {
        "name": "generate_risk_briefing",
        "description": "Generate a human-readable operational risk briefing.",
        "func": generate_risk_briefing_prompt,
    },
    {
        "name": "escalation_alert",
        "description": "Generate an escalation alert for high-risk shipment situations.",
        "func": escalation_alert_prompt,
    },
]