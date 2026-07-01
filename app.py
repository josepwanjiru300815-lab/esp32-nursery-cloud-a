from flask import Flask, request, jsonify
import json

app = Flask(__name__)

# Global state
system_state = {
    "pump": "OFF",
    "valve": "STOPPED",
    "temp": 0,
    "hum": 0,
    "soil1": 0,
    "soil2": 0,
    "fault1": False,
    "fault2": False,
    "percent": 0,
    "volume": 0
}

# Command buffer
command_buffer = {
    "pump": "OFF",
    "valve": "STOPPED"
}

@app.route("/esp32/log", methods=["POST"])
def esp32_log():
    global system_state, command_buffer
    data = request.get_json()
    
    # Update state from ESP32
    system_state.update({
        "pump": data.get("pump", "OFF"),
        "valve": data.get("valve", "STOPPED"),
        "temp": data.get("temp", 0),
        "hum": data.get("hum", 0),
        "soil1": data.get("soil1", 0),
        "soil2": data.get("soil2", 0),
        "fault1": data.get("fault1", False),
        "fault2": data.get("fault2", False),
        "percent": data.get("percent", 0),
        "volume": data.get("volume", 0)
    })
    
    # Send commands and reset
    cmd = command_buffer.copy()
    command_buffer["pump"] = system_state["pump"]
    command_buffer["valve"] = "STOPPED"
    
    return jsonify(cmd)

@app.route("/pump/on")
def pump_on():
    command_buffer["pump"] = "ON"
    return jsonify({"status": "ok", "pump": "ON"})

@app.route("/pump/off")
def pump_off():
    command_buffer["pump"] = "OFF"
    return jsonify({"status": "ok", "pump": "OFF"})

@app.route("/valve/open")
def valve_open():
    command_buffer["valve"] = "OPENING"
    return jsonify({"status": "ok", "valve": "OPENING"})

@app.route("/valve/close")
def valve_close():
    command_buffer["valve"] = "CLOSING"
    return jsonify({"status": "ok", "valve": "CLOSING"})

@app.route("/valve/stop")
def valve_stop():
    command_buffer["valve"] = "STOPPED"
    return jsonify({"status": "ok", "valve": "STOPPED"})

@app.route("/status")
def status():
    return jsonify(system_state)

if __name__ == "__main__":
    app.run(debug=True)
