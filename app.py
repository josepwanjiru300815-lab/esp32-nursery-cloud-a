from flask import Flask, request, jsonify, render_template_string
import json
from datetime import datetime

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
    "volume": 0,
    "last_update": "Never"
}

# Command buffer - cleared after sending to ESP32
command_buffer = {
    "pump": "OFF",
    "valve": "STOPPED"
}

@app.route("/")
def dashboard():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>ESP32 Nursery</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial; margin: 20px; }
            .card { background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 8px; }
            button { padding: 10px 20px; margin: 5px; font-size: 16px; }
            .on { background: #4CAF50; color: white; }
            .off { background: #f44336; color: white; }
        </style>
    </head>
    <body>
        <h1>ESP32 Nursery Dashboard</h1>
        <div class="card">
            <h3>Sensors</h3>
            <p>Temp: <span id="temp">0</span>°C | Humidity: <span id="hum">0</span>%</p>
            <p>Soil 1: <span id="soil1">0</span>% | Soil 2: <span id="soil2">0</span>%</p>
            <p>Tank: <span id="percent">0</span>% | <span id="volume">0</span>L</p>
        </div>
        <div class="card">
            <h3>Controls</h3>
            <p>Pump: <span id="pump">OFF</span></p>
            <button onclick="fetch('/pump/on').then(()=>update())" class="on">Pump ON</button>
            <button onclick="fetch('/pump/off').then(()=>update())" class="off">Pump OFF</button>
            <p>Valve: <span id="valve">STOPPED</span></p>
            <button onclick="fetch('/valve/open').then(()=>update())">Valve OPEN</button>
            <button onclick="fetch('/valve/close').then(()=>update())">Valve CLOSE</button>
            <button onclick="fetch('/valve/stop').then(()=>update())">Valve STOP</button>
        </div>
        <p>Last update: <span id="last_update">Never</span></p>
        
        <script>
            function update() {
                fetch('/status').then(r=>r.json()).then(data=>{
                    document.getElementById('temp').textContent = data.temp;
                    document.getElementById('hum').textContent = data.hum;
                    document.getElementById('soil1').textContent = data.soil1;
                    document.getElementById('soil2').textContent = data.soil2;
                    document.getElementById('percent').textContent = data.percent;
                    document.getElementById('volume').textContent = data.volume;
                    document.getElementById('pump').textContent = data.pump;
                    document.getElementById('valve').textContent = data.valve;
                    document.getElementById('last_update').textContent = data.last_update;
                });
            }
            setInterval(update, 2000);
            update();
        </script>
    </body>
    </html>
    """)

@app.route("/esp32/log", methods=["POST"])
def esp32_log():
    global system_state, command_buffer
    data = request.get_json()
    
    # Update ALL data from ESP32 including pump/valve - original behavior
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
        "volume": data.get("volume", 0),
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Send commands to ESP32, then reset buffer to match current state
    cmd = command_buffer.copy()
    command_buffer["pump"] = system_state["pump"]    # Reset to current
    command_buffer["valve"] = "STOPPED"             # Valve always stops
    
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
