# # DJL RiskWatch – MCP-Based Shipment Risk System

DJL RiskWatch is a decision-support system designed to evaluate shipment risk at pre-dispatch and monitor delays during transit.

The system uses MCP tools, resources, and prompts to simulate real-world logistics decision-making. It combines port risk profiles, cargo sensitivity, and a fallback dataset to generate risk levels and recommended actions.

This is implemented as a Minimum Viable Product (MVP) using static data sources.


- builds the FastAPI app, wraps it with FastMCP, mounts MCP HTTP/SSE endpoints, registers resources and prompts, and starts uvicorn.
- requirements.txt – Python dependencies.

## Prerequisites

- Python 3.10+ (tested with 3.12).
- Virtual environment.
- npm inspector below.

⸻

## Setup from this folder

```bash
python -m venv .venv

# Mac or Gitbash
source .venv/bin/activate

# Windows powershell:
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

⸻

## Run the HTTP + MCP server

```bash
# start the server
python converter_streamable_http_server.py

# or
python -m converter_streamable_http_server

```

You’ll see:

- Swagger UI: http://localhost:8003/docs
- ReDoc: http://localhost:8003/redoc

MCP endpoints served by FastMCP:

- streamable-http: http://localhost:8003/mcp
- SSE: http://localhost:8003/sse

⸻

## Try the HTTP endpoints (curl)
Make sure the server is running:
     python converter_streamable_http_server.py
The API will be available at:
     http://localhost:8003


Headers (common to all requests)
-H "Content-Type: application/json"

Authentication is not required for this MVP.

```bash
# assess_route_risk
curl -X POST "http://localhost:8004/assess-route-risk" \
-H "Content-Type: application/json" \
-d '{
  "shipment_id": "SHP001",
  "planned_dispatch_date": "2026-05-10",
  "origin_port": "Singapore",
  "destination_port": "Dubai",
  "cargo_type": "temperature"
}'

```

```bash
# monitor_in_transit_risk
curl -X POST "http://localhost:8004/monitor-in-transit-risk" \
-H "Content-Type: application/json" \
-d '{
  "shipment_id": "SHP002",
  "original_eta": "2026-05-10",
  "revised_eta": "2026-05-12",
  "cargo_type": "critical"
}'
```

```bash
# prepare_delay_communication
curl -X POST "http://localhost:8004/prepare-delay-communication" \
-H "Content-Type: application/json" \
-d '{
  "shipment_id": "SHP003",
  "customer_id": "CUST001",
  "delay_hours": 48,
  "risk_level": "high",
  "revised_eta": "2026-05-12"
}'
```

```bash
# record_operational_action
curl -X POST "http://localhost:8004/record-operational-action" \
-H "Content-Type: application/json" \
-d '{
  "shipment_id": "SHP004",
  "stage": "in_transit",
  "action": "contact_carrier",
  "action_by": "operator",
  "action_reason": "Delay detected"
}'
```


Each endpoint returns structured JSON with the tool result and operation name, for example:

- `assess_route_risk` returns risk summary, risk drivers, historical context, decision guidance, and recommended actions.
- `monitor_in_transit_risk` returns ETA analysis, urgency level, impact assessment, escalation guidance, and recommended actions.
- `prepare_delay_communication` returns an internal alert, customer contact details, customer email draft, and recommended review actions.
- `record_operational_action` returns a structured action log with status, timestamp, action details, and system note.

Invalid inputs may return either:
- FastAPI validation errors, such as HTTP `422`, for missing required query parameters.
- Tool-level error messages, such as invalid `stage`, invalid `action`, invalid `risk_level`, or customer not found.

## Headers & Authentication (common to all)

### Headers

```bash
-H "Content-Type: application/json"

Our server doesn’t require auth yet, we can omit the **Authorization** header.

## Use with MCP (VS Code Example)

1. Start the server as above.
2. Point your MCP client to the process.

```json
// Example VS Code .vscode/mcp.json entry:
{
  "servers": {
    "RiskWatch": {
      "command": "python",
      "args": ["converter_streamable_http_server.py"]
    }
  }
}
```

3. From the MCP client, list artifacts. You should see:
Tools:
assess_route_risk
monitor_in_transit_risk
prepare_delay_communication
record_operational_action
Resources:
resource://risk_thresholds
resource://port_risk_profiles
resource://customer_data
resource://global_supply_chain_risk_2026
Prompts:
generate_risk_briefing
escalation_alert



⸻

## Inspect with the MCP Inspector

- Use the MCP Inspector to explore tools, resources, and prompts in a browser.
- Ensure the server is running at: http://localhost:8003

```bash
# Recommended (streamable HTTP)
npx @modelcontextprotocol/inspector@latest -e DUMMY=1 --url http://localhost:8003/mcp --transport streamable-http

# Alternative (HTTP transport)
npx @modelcontextprotocol/inspector@latest -e DUMMY=1 --url http://localhost:8003/mcp --transport http

# Deprecated (SSE transport)
npx @modelcontextprotocol/inspector@latest -e DUMMY=1 --url http://localhost:8003/sse --transport sse

## To run the STDIO server only

```bash
# If using virtual environment, adjust Python path if needed
npx @modelcontextprotocol/inspector python converter_stdio_server.py

## JSON-RPC Examples for Prompts & Resources
These examples use the MCP endpoint:
http://localhost:8003/mcp

1. List all prompts

```bash
curl -s -X POST http://localhost:8003/mcp \
-H "Content-Type: application/json" \
-d '{"jsonrpc":"2.0","method":"prompts/list","params":{},"id":1}'
```

⸻

2. Get a specific prompt

```bash
curl -s -X POST http://localhost:8003/mcp \
-H "Content-Type: application/json" \
-d '{"jsonrpc":"2.0","method":"prompts/get","params":{"name":"generate_risk_briefing"},"id":2}'
```

⸻

3. Render/execute a prompt with variables

```bash
curl -s -X POST http://localhost:8003/mcp \
-H "Content-Type: application/json" \
-d '{"jsonrpc":"2.0","method":"prompts/render","params":{"name":"generate_risk_briefing","variables":{"text":"Shipment SHP001 delay detected","tone":"neutral"}},"id":3}'
```

4. List available resources

```bash
curl -s -X POST http://localhost:8003/mcp \
-H "Content-Type: application/json" \
-d '{"jsonrpc":"2.0","method":"resources/list","params":{},"id":4}'
```

5. Read a resource by URI

```bash
curl -s -X POST http://localhost:8003/mcp \
-H "Content-Type: application/json" \
-d '{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"resource://port_risk_profiles"},"id":5}'
```

6. Search resources (if supported)

```bash
curl -s -X POST http://localhost:8003/mcp \
-H "Content-Type: application/json" \
-d '{"jsonrpc":"2.0","method":"resources/search","params":{"query":"Singapore OR delay OR temperature","limit":50},"id":6}'
```

⸻

## Handling errors

### JSON-RPC Errors (MCP)

- Parse error (-32700)  
- Invalid request (-32600)  
- Method not found (-32601)  
- Invalid params (-32602)  
- Internal error (-32603)  

### HTTP / FastAPI Errors

- **422 Unprocessable Entity**  
  Occurs when required query parameters are missing or incorrectly named.

### Tool-Level Errors (from implementation)

- Invalid `stage` → returns valid options (`pre_dispatch`, `in_transit`, `communication`)  
- Invalid `action` → returns list of allowed actions  
- Invalid `risk_level` → returns valid options (`low`, `medium`, `high`)  
- Customer not found → returns error with `customer_id`   

### Data Handling

- If a port is not matched in `port_risk_profiles`, a default score is applied  
- System continues processing instead of failing  

### Notes

- The system prioritizes graceful handling of errors  
- Most errors guide the user to correct the input rather than stopping execution  


## Notes

macOS/Linux (bash/zsh)
• The examples above will work as-is.

```bash
# Windows PowerShell
curl -Method POST http://localhost:8003/mcp `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{"jsonrpc":"2.0","method":"prompts/list","params":{},"id":1}'
```

Windows CMD

```bash
curl -s -X POST http://localhost:8003/mcp -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"prompts/list\",\"params\":{},\"id\":1}"
```


## Definition of Terms

**General Cargo**  
Non-perishable goods with low urgency. Delays have minimal operational impact and higher flexibility in handling.

**Critical Cargo**  
High-priority shipments where delays may disrupt operations, production schedules, or supply chain continuity.

**Temperature-Sensitive Cargo**  
Perishable or low shelf-life goods requiring controlled conditions. Highly vulnerable to delays and handling risks.

**Risk Score**  
A calculated value based on multiple factors such as port congestion, cargo sensitivity, and historical data.

**Risk Level**  
Classification of shipment risk based on predefined thresholds:
- Low
- Medium
- High

**Delay Impact**  
The operational consequence of shipment delays, influenced by cargo type, port conditions, and delay duration.