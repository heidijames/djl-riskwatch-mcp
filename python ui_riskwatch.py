import tkinter as tk
from tkinter import ttk
import requests

API_BASE_URL = "http://127.0.0.1:8004"

PORTS = ["Singapore", "Shanghai", "Port Klang", "Dubai"]


def run_operation():
    operation = operation_var.get()

    try:
        if operation == "Pre-Dispatch Risk Assessment":
            url = f"{API_BASE_URL}/assess-route-risk"
            data = {
                "shipment_id": shipment_id.get(),
                "planned_dispatch_date": dispatch_date.get(),
                "origin_port": origin_port.get(),
                "destination_port": destination_port.get(),
                "cargo_type": cargo_type.get(),
            }

        else:
            url = f"{API_BASE_URL}/monitor-in-transit-risk"
            data = {
                "shipment_id": shipment_id.get(),
                "original_eta": original_eta.get(),
                "revised_eta": revised_eta.get(),
                "cargo_type": cargo_type.get(),
            }

        response = requests.post(url, params=data)
        result = response.json()

        display_output(result)

    except Exception as e:
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, f"Error: {e}")


def display_output(result):
    output_box.delete("1.0", tk.END)

    data = result.get("result", {})

    if operation_var.get() == "Pre-Dispatch Risk Assessment":
        summary = data.get("summary", {})
        risk = summary.get("risk_level", "").upper()
        score = summary.get("risk_score", "")

        risk_label.config(text=f"Risk Level: {risk}", foreground=get_color(risk))

        text = f"""
Shipment: {summary.get('shipment_id')}
Route: {summary.get('origin_port')} → {summary.get('destination_port')}
Cargo: {summary.get('cargo_type')}

Risk Score: {score}

Key Drivers:
"""
        for driver in data.get("risk_drivers", []):
            text += f"- {driver}\n"

        text += "\nRecommended Actions:\n"
        for action in data.get("recommended_actions", []):
            text += f"- {action}\n"

    else:
        summary = data.get("summary", {})
        urgency_data = data.get("urgency", {})
        urgency = urgency_data.get("level", "").upper()

        risk_label.config(text=f"Urgency: {urgency}", foreground=get_color(urgency))

        eta = data.get("eta_analysis", {})

        text = f"""
Shipment: {summary.get('shipment_id')}

Delay Hours: {eta.get('delay_hours')}
Status: {eta.get('status')}

Impact:
{data.get("impact_assessment")}
"""

        text += "\nPriority Actions:\n"
        for action in data.get("recommended_actions", {}).get("priority", []):
            text += f"- {action}\n"

    output_box.insert(tk.END, text)


def get_color(level):
    if "HIGH" in level:
        return "red"
    elif "MEDIUM" in level:
        return "orange"
    else:
        return "green"


def update_fields(event=None):
    op = operation_var.get()

    # Clear previous output/status when switching tools
    output_box.delete("1.0", tk.END)
    risk_label.config(text="")

    # Hide all dynamic fields
    for widget in dynamic_widgets:
        widget.grid_remove()

    if op == "Pre-Dispatch Risk Assessment":
        dispatch_date_label.grid()
        dispatch_date.grid()
        origin_label.grid()
        origin_port.grid()
        destination_label.grid()
        destination_port.grid()

    elif op == "In-Transit Monitoring":
        original_eta_label.grid()
        original_eta.grid()
        revised_eta_label.grid()
        revised_eta.grid()


root = tk.Tk()
root.title("DJL RiskWatch")
root.geometry("800x700")

ttk.Label(
    root,
    text="DJL RiskWatch Dashboard",
    font=("Arial", 14, "bold")
).grid(row=0, column=0, columnspan=2, pady=10)

operation_var = tk.StringVar(value="Pre-Dispatch Risk Assessment")

ttk.Label(root, text="Select Operation").grid(row=1, column=0)

operation_dropdown = ttk.Combobox(
    root,
    textvariable=operation_var,
    values=["Pre-Dispatch Risk Assessment", "In-Transit Monitoring"],
    state="readonly"
)
operation_dropdown.grid(row=1, column=1)
operation_dropdown.bind("<<ComboboxSelected>>", update_fields)

ttk.Label(root, text="Shipment ID").grid(row=2, column=0)
shipment_id = ttk.Entry(root)
shipment_id.grid(row=2, column=1)

ttk.Label(root, text="Cargo Type").grid(row=3, column=0)
cargo_type = ttk.Combobox(
    root,
    values=["general", "critical", "temperature"],
    state="readonly"
)
cargo_type.grid(row=3, column=1)
cargo_type.set("general")

dispatch_date_label = ttk.Label(root, text="Dispatch Date")
dispatch_date = ttk.Entry(root)

origin_label = ttk.Label(root, text="Origin Port")
origin_port = ttk.Combobox(root, values=PORTS, state="readonly")

destination_label = ttk.Label(root, text="Destination Port")
destination_port = ttk.Combobox(root, values=PORTS, state="readonly")

original_eta_label = ttk.Label(root, text="Original ETA")
original_eta = ttk.Entry(root)

revised_eta_label = ttk.Label(root, text="Revised ETA")
revised_eta = ttk.Entry(root)

dispatch_date_label.grid(row=4, column=0)
dispatch_date.grid(row=4, column=1)

origin_label.grid(row=5, column=0)
origin_port.grid(row=5, column=1)

destination_label.grid(row=6, column=0)
destination_port.grid(row=6, column=1)

original_eta_label.grid(row=4, column=0)
original_eta.grid(row=4, column=1)

revised_eta_label.grid(row=5, column=0)
revised_eta.grid(row=5, column=1)

dynamic_widgets = [
    dispatch_date_label,
    dispatch_date,
    origin_label,
    origin_port,
    destination_label,
    destination_port,
    original_eta_label,
    original_eta,
    revised_eta_label,
    revised_eta,
]

ttk.Button(
    root,
    text="Run Operation",
    command=run_operation
).grid(row=7, column=0, columnspan=2, pady=10)

risk_label = ttk.Label(root, text="", font=("Arial", 12, "bold"))
risk_label.grid(row=8, column=0, columnspan=2)

output_box = tk.Text(root, height=20, width=85)
output_box.grid(row=9, column=0, columnspan=2, padx=10, pady=10)

# Important: call this only AFTER output_box and risk_label exist
update_fields()

root.mainloop()