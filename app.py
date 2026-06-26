from flask import Flask, render_template, request, jsonify, redirect

app = Flask(__name__)

# System State Memory Cache
system_state = {
    "pump": "OFF", "valve": "STOPPED",
    "volume": 0.0, "percent": 0.0,
    "temp": 0.0, "hum": 0.0,
    "soil1": 0.0, "soil2": 0.0,
    "fault1": False, "fault2": False
}

# Desired Override Targets
command_buffer = {
    "pump": "OFF",
    "valve": "STOPPED"
}

# Web Interface Endpoints
@app.route('/')
def handle_root(): return render_template('home.html')

@app.route('/about')
def handle_about(): return render_template('about.html')

@app.route('/vision')
def handle_vision(): return render_template('vision.html')

@app.route('/contacts')
def handle_contacts(): return render_template('contacts.html')

@app.route('/beds')
def handle_beds(): return render_template('beds.html')

@app.route('/nursery1')
def handle_nursery1(): return render_template('nursery1.html')

@app.route('/nursery2')
def handle_nursery2():
    return "<body style='background:#0f172a;color:white;font-family:Arial;text-align:center;padding:40px'><h1>Nursery Bed 2</h1><p style='color:#94a3b8'>Yet to be updated</p><a href='/beds' style='color:#38bdf8'>← Back</a></body>"

@app.route('/nursery3')
def handle_nursery3():
    return "<body style='background:#0f172a;color:white;font-family:Arial;text-align:center;padding:40px'><h1>Nursery Bed 3</h1><p style='color:#94a3b8'>Yet to be updated</p><a href='/beds' style='color:#38bdf8'>← Back</a></body>"

# UI Interactivity Control Actions
@app.route('/pump/on')
def handle_pump_on():
    command_buffer["pump"] = "ON"
    return redirect('/nursery1')

@app.route('/pump/off')
def handle_pump_off():
    command_buffer["pump"] = "OFF"
    return redirect('/nursery1')

@app.route('/valve/open')
def handle_valve_open():
    command_buffer["valve"] = "OPEN"
    return redirect('/nursery1')

@app.route('/valve/close')
def handle_valve_close():
    command_buffer["valve"] = "CLOSE"
    return redirect('/nursery1')

@app.route('/valve/stop')
def handle_valve_stop():
    command_buffer["valve"] = "STOP"
    return redirect('/nursery1')

# Live UI Telemetry Polling Endpoint
@app.route('/status')
def handle_status():
    return jsonify(system_state)

# ESP32 Cloud Network Sync Target
@app.route('/esp32/update', methods=['POST'])
def esp32_update():
    global system_state, command_buffer
    try:
        incoming_data = request.json
        if incoming_data:
            system_state["pump"] = incoming_data.get("pump", system_state["pump"])
            system_state["valve"] = incoming_data.get("valve", system_state["valve"])
            system_state["volume"] = float(incoming_data.get("volume", system_state["volume"]))
            system_state["percent"] = float(incoming_data.get("percent", system_state["percent"]))
            system_state["temp"] = float(incoming_data.get("temp", system_state["temp"]))
            system_state["hum"] = float(incoming_data.get("hum", system_state["hum"]))
            system_state["soil1"] = float(incoming_data.get("soil1", system_state["soil1"]))
            system_state["soil2"] = float(incoming_data.get("soil2", system_state["soil2"]))
            system_state["fault1"] = incoming_data.get("fault1") in ['true', True]
            system_state["fault2"] = incoming_data.get("fault2") in ['true', True]

        return f'{{"pump":"{command_buffer["pump"]}","valve":"{command_buffer["valve"]}"}}', 200
    except Exception as e:
        return str(e), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
