"""Prompt templates for DJL RiskWatch."""

from __future__ import annotations

from typing import List, Dict


def generate_risk_briefing_prompt() -> List[Dict[str, str]]:
    """
    Generate a clear operational risk summary from tool output.
    """
    return [
        {
            "role": "system",
            "content": (
                "You are a logistics risk analyst. "
                "Summarize shipment risks clearly for internal operations. "
                "Keep it concise, professional, and easy to understand."
            ),
        },
        {
            "role": "user",
            "content": (
                "Using the following shipment risk data:\n\n"
                "{data}\n\n"
                "Provide a short briefing that:\n"
                "- Explains the overall risk level\n"
                "- Highlights key risk factors (weather, geopolitical, carrier, cargo)\n"
                "- Mentions delay impact if present\n"
                "- Does NOT make decisions or take actions"
            ),
        },
    ]


def escalation_alert_prompt() -> List[Dict[str, str]]:
    """
    Generate an escalation message for high-risk shipments.
    """
    return [
        {
            "role": "system",
            "content": (
                "You are an operations supervisor preparing an escalation alert. "
                "Your tone should be urgent but professional."
            ),
        },
        {
            "role": "user",
            "content": (
                "Using the following shipment risk data:\n\n"
                "{data}\n\n"
                "Create an escalation alert that:\n"
                "- Clearly explains why escalation is required\n"
                "- Highlights business impact (delay, cost, customer impact)\n"
                "- Suggests what needs attention (NOT decisions)\n"
                "- Does NOT assume actions have already been taken"
            ),
        },
    ]


PROMPT_DEFINITIONS = [
    {
        "name": "generate_risk_briefing",
        "description": "Generate a human-readable operational risk summary",
        "func": generate_risk_briefing_prompt,
    },
    {
        "name": "escalation_alert",
        "description": "Generate an escalation message for high-risk shipments",
        "func": escalation_alert_prompt,
    },
]