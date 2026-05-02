# DJL RiskWatch API + MCP (tools, resources, prompts)
from fastapi import FastAPI, APIRouter
from fastmcp import FastMCP

from mcp_tools.converter_tools import router as riskwatch_router
from mcp_resources.converter_resources import (
    risk_thresholds,
    port_risk_profiles,
    customer_data,
    kaggle_supply_chain_fallback,
)
from mcp_prompts.converter_prompts import (
    generate_risk_briefing_prompt,
    escalation_alert_prompt,
)

import platform
import datetime
import os
import time
import uvicorn

PORT = 8003

# FastAPI app
app = FastAPI(
    title="DJL RiskWatch MCP Server",
    description="RiskWatch logistics decision-support API with MCP tools, resources, and prompts.",
    version="1.0.0",
)

app.include_router(riskwatch_router)

# System health router
system_router = APIRouter(prefix="", tags=["system"])
_started_at = time.time()


@system_router.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "uptime_seconds": round(time.time() - _started_at, 2),
    }


app.include_router(system_router)

# FastMCP server generated from FastAPI OpenAPI
mcp = FastMCP.from_fastapi(
    app,
    name="DJL RiskWatch MCP Server",
    instructions=(
        "DJL RiskWatch provides shipment risk assessment, in-transit delay monitoring, "
        "delay communication drafting, and operational action logging."
    ),
)

# Resources
@mcp.resource("resource://risk_thresholds", name="Risk Thresholds", mime_type="application/json")
def _resource_risk_thresholds():
    return risk_thresholds()


@mcp.resource("resource://port_risk_profiles", name="Port Risk Profiles", mime_type="application/json")
def _resource_port_risk_profiles():
    return port_risk_profiles()


@mcp.resource("resource://customer_data", name="Customer Data", mime_type="application/json")
def _resource_customer_data():
    return customer_data()


@mcp.resource("resource://kaggle_supply_chain_fallback", name="Supply Chain Fallback Dataset", mime_type="text/csv")
def _resource_kaggle_supply_chain_fallback():
    return kaggle_supply_chain_fallback()


# Prompts
@mcp.prompt(name="generate_risk_briefing", description="Generate a human-readable operational risk briefing.")
def _prompt_generate_risk_briefing():
    return generate_risk_briefing_prompt()


@mcp.prompt(name="escalation_alert", description="Generate an escalation alert for high-risk shipment situations.")
def _prompt_escalation_alert():
    return escalation_alert_prompt()


# MCP HTTP apps
mcp_http_app = mcp.http_app(path="/", transport="streamable-http")
mcp_sse_app = mcp.http_app(path="/", transport="sse")

app.router.lifespan_context = mcp_http_app.lifespan

app.mount("/mcp", mcp_http_app)
app.mount("/sse", mcp_sse_app)


if __name__ == "__main__":
    print("Starting DJL RiskWatch API server (HTTP + MCP tools/resources/prompts)...")
    print(f"HTTP docs:    http://localhost:{PORT}/docs")
    print(f"HTTP redoc:   http://localhost:{PORT}/redoc")
    print(f"Health:       http://localhost:{PORT}/health")
    print(f"MCP HTTP:     http://localhost:{PORT}/mcp")
    print(f"MCP SSE:      http://localhost:{PORT}/sse")

    uvicorn.run(
        app,
        host="localhost",
        port=PORT,
        log_level="info",
    )