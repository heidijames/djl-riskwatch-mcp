import tkinter as tk
from tkinter import ttk
import json
import requests

API_BASE_URL = "http://127.0.0.1:8003"

PORTS = ["Singapore", "Port Klang", "Shanghai", "Dubai"]
CARGO_TYPES = ["general", "critical", "temperature"]
RISK_LEVELS = ["low", "medium", "high"]
STAGES = ["pre_dispatch", "in_transit", "communication"]
ACTIONS = [
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

TOOLS = {
    "assess_route_risk": {
        "endpoint": "/assess-route-risk",
        "fields": [
            ("shipment_id", "entry"),
            ("planned_dispatch_date", "entry"),
            ("origin_port", "port"),
            ("destination_port", "port"),
            ("cargo_type", "cargo"),
        ],
    },
    "monitor_in_transit_risk": {
        "endpoint": "/monitor-in-transit-risk",
        "fields": [
            ("shipment_id", "entry"),
            ("original_eta", "entry"),
            ("revised_eta", "entry"),
            ("cargo_type", "cargo"),
        ],
    },
    "prepare_delay_communication": {
        "endpoint": "/prepare-delay-communication",
        "fields": [
            ("shipment_id", "entry"),
            ("customer_id", "entry"),
            ("delay_hours", "entry"),
            ("risk_level", "risk"),
            ("revised_eta", "entry"),
        ],
    },
    "record_operational_action": {
        "endpoint": "/record-operational-action",
        "fields": [
            ("shipment_id", "entry"),
            ("stage", "stage"),
            ("action", "action"),
            ("action_by", "entry"),
            ("action_reason", "entry"),
            ("notes", "entry"),
            ("estimated_delay_cost", "entry"),
            ("currency", "entry"),
            ("cost_basis", "entry"),
        ],
    },
}


def create_widget(field_type):
    if field_type == "port":
        return ttk.Combobox(input_frame, values=PORTS, state="readonly")
    if field_type == "cargo":
        return ttk.Combobox(input_frame, values=CARGO_TYPES, state="readonly")
    if field_type == "risk":
        return ttk.Combobox(input_frame, values=RISK_LEVELS, state="readonly")
    if field_type == "stage":
        return ttk.Combobox(input_frame, values=STAGES, state="readonly")
    if field_type == "action":
        return ttk.Combobox(input_frame, values=ACTIONS, state="readonly")
    return ttk.Entry(input_frame, width=45)


def update_fields(event=None):
    for widget in input_frame.winfo_children():
        widget.destroy()

    field_widgets.clear()

    selected_tool = tool_var.get()
    fields = TOOLS[selected_tool]["fields"]

    for row, (field_name, field_type) in enumerate(fields):
        label_text = field_name.replace("_", " ").title()
        ttk.Label(input_frame, text=label_text).grid(row=row, column=0, sticky="w", padx=5, pady=4)

        widget = create_widget(field_type)
        widget.grid(row=row, column=1, sticky="ew", padx=5, pady=4)

        if field_type == "cargo":
            widget.set("general")
        elif field_type == "risk":
            widget.set("medium")
        elif field_type == "stage":
            widget.set("in_transit")
        elif field_type == "action":
            widget.set("contact_carrier")
        elif field_type == "port":
            widget.set(PORTS[0])

        field_widgets[field_name] = widget

    output_box.delete("1.0", tk.END)
    status_label.config(text="")


def get_payload():
    payload = {}

    for field_name, widget in field_widgets.items():
        value = widget.get().strip()

        if value == "":
            continue

        if field_name == "delay_hours":
            payload[field_name] = int(value)
        elif field_name == "estimated_delay_cost":
            payload[field_name] = float(value)
        else:
            payload[field_name] = value

    return payload


def run_tool():
    selected_tool = tool_var.get()
    endpoint = TOOLS[selected_tool]["endpoint"]
    url = f"{API_BASE_URL}{endpoint}"

    try:
        payload = get_payload()

        response = requests.post(url, json=payload)
        result = response.json()

        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, json.dumps(result, indent=2))

        if response.status_code == 200:
            status_label.config(text="Success", foreground="green")
        else:
            status_label.config(text=f"Error {response.status_code}", foreground="red")

    except ValueError as e:
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, f"Input error: {e}")
        status_label.config(text="Input Error", foreground="red")

    except requests.exceptions.RequestException as e:
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, f"Connection error: {e}")
        status_label.config(text="Connection Error", foreground="red")

    except Exception as e:
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, f"Error: {e}")
        status_label.config(text="Error", foreground="red")


root = tk.Tk()
root.title("DJL RiskWatch Dashboard")
root.geometry("950x750")

ttk.Label(
    root,
    text="DJL RiskWatch Dashboard",
    font=("Arial", 16, "bold")
).pack(pady=10)

tool_var = tk.StringVar(value="assess_route_risk")

tool_frame = ttk.Frame(root)
tool_frame.pack(fill="x", padx=15, pady=5)

ttk.Label(tool_frame, text="Select Tool").pack(side="left", padx=5)

tool_dropdown = ttk.Combobox(
    tool_frame,
    textvariable=tool_var,
    values=list(TOOLS.keys()),
    state="readonly",
    width=35
)
tool_dropdown.pack(side="left", padx=5)
tool_dropdown.bind("<<ComboboxSelected>>", update_fields)

input_frame = ttk.LabelFrame(root, text="Input Fields")
input_frame.pack(fill="x", padx=15, pady=10)

field_widgets = {}

ttk.Button(root, text="Run Tool", command=run_tool).pack(pady=10)

status_label = ttk.Label(root, text="", font=("Arial", 12, "bold"))
status_label.pack()

output_box = tk.Text(root, height=25, width=110)
output_box.pack(padx=15, pady=10)

update_fields()

root.mainloop()