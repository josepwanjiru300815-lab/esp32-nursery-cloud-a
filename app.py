from flask import Flask, request, jsonify, render_template_string
import json
from datetime import datetime
import pytz

app = Flask(__name__)

# Global state - server is the master
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

# Commands get sent once, then cleared
command_buffer = {
    "valve": "STOPPED"
}

# Login logs for dashboard
login_logs = []

# Users - change these
USERS = {
    "admin": "admin123",
    "farmer": "farm2024"
}

@app.route("/esp32/log", methods=["POST"])
def esp32_log():
    global system_state, command_buffer
    data = request.get_json()
    
    # 1. Update ONLY sensor data from ESP32
    kenya_tz = pytz.timezone('Africa/Nairobi')
    system_state.update({
        "temp": data.get("temp", 0),
        "hum": data.get("hum", 0),
        "soil1": data.get("soil1", 0),
        "soil2": data.get("soil2", 0),
        "fault1": data.get("fault1", False),
        "fault2": data.get("fault2", False),
        "percent": data.get("percent", 0),
        "volume": data.get("volume", 0),
        "last_update": datetime.now(kenya_tz).strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # 2. Build response with CURRENT state + any pending valve command
    response = {
        "pump": system_state["pump"],    # Send current pump state
        "valve": command_buffer["valve"] # Send valve command
    }
    
    # 3. If we sent a valve command, update state and clear buffer
    if command_buffer["valve"] != "STOPPED":
        system_state["valve"] = command_buffer["valve"]
        command_buffer["valve"] = "STOPPED"  # Clear after sending once
    
    return jsonify(response)

@app.route("/pump/on")
def pump_on():
    system_state["pump"] = "ON"
    return jsonify({"status": "ok", "pump": "ON"})

@app.route("/pump/off")
def pump_off():
    system_state["pump"] = "OFF"
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
    system_state["valve"] = "STOPPED"
    return jsonify({"status": "ok", "valve": "STOPPED"})

@app.route("/status")
def status():
    return jsonify(system_state)

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("user", "")
    success = data.get("success", False)
    log_time = data.get("time", "NoTime")
    offline = data.get("offline", False)
    
    login_logs.insert(0, {
        "user": username,
        "success": success,
        "time": log_time,
        "offline": offline,
        "delay_ms": data.get("delay_ms", 0)
    })
    
    # Keep only last 50 logs
    if len(login_logs) > 50:
        login_logs.pop()
    
    return jsonify({"status": "logged"})

@app.route("/")
def dashboard():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ESP32 Nursery Cloud</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
            .card { background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
            .value { font-size: 2em; font-weight: bold; color: #2196F3; }
            .label { color: #666; font-size: 0.9em; }
            button { padding: 12px 24px; margin: 5px; font-size: 16px; border: none; border-radius: 5px; cursor: pointer; }
            .on { background: #4CAF50; color: white; }
            .off { background: #f44336; color: white; }
            .open { background: #2196F3; color: white; }
            .close { background: #FF9800; color: white; }
            .stop { background: #9E9E9E; color: white; }
            .status-on { color: #4CAF50; font-weight: bold; }
            .status-off { color: #f44336; font-weight: bold; }
            .fault { color: #f44336; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        </style>
        <script>
            function control(action) {
                fetch('/' + action).then(r => r.json()).then(d => {
                    console.log(d);
                    setTimeout(updateStatus, 500);
                });
            }
            
            function updateStatus() {
                fetch('/status').then(r => r.json()).then(data => {
                    document.getElementById('temp').innerText = data.temp.toFixed(1) + '°C';
                    document.getElementById('hum').innerText = data.hum.toFixed(1) + '%';
                    document.getElementById('soil1').innerText = data.soil1.toFixed(0) + '%';
                    document.getElementById('soil2').innerText = data.soil2.toFixed(0) + '%';
                    document.getElementById('percent').innerText = data.percent.toFixed(0) + '%';
                    document.getElementById('volume').innerText = data.volume.toFixed(0) + ' L';
                    document.getElementById('pump').innerText = data.pump;
                    document.getElementById('pump').className = data.pump == 'ON' ? 'status-on' : 'status-off';
                    document.getElementById('valve').innerText = data.valve;
                    document.getElementById('fault1').innerText = data.fault1 ? 'FAULT' : 'OK';
                    document.getElementById('fault1').className = data.fault1 ? 'fault' : '';
                    document.getElementById('fault2').innerText = data.fault2 ? 'FAULT' : 'OK';
                    document.getElementById('fault2').className = data.fault2 ? 'fault' : '';
                    document.getElementById('update').innerText = data.last_update;
                });
            }
            
            setInterval(updateStatus, 2000);
            window.onload = updateStatus;
        </script>
    </head>
    <body>
        <h1>ESP32 Nursery Cloud Dashboard</h1>
        
        <div class="card">
            <h2>Controls</h2>
            <button class="on" onclick="control('pump/on')">Pump ON</button>
            <button class="off" onclick="control('pump/off')">Pump OFF</button>
            <button class="open" onclick="control('valve/open')">Valve OPEN</button>
            <button class="close" onclick="control('valve/close')">Valve CLOSE</button>
            <button class="stop" onclick="control('valve/stop')">Valve STOP</button>
        </div>
        
        <div class="card">
            <h2>System Status</h2>
            <div class="grid">
                <div><div class="label">Pump</div><div class="value" id="pump">OFF</div></div>
                <div><div class="label">Valve</div><div class="value" id="valve">STOPPED</div></div>
                <div><div class="label">Tank Level</div><div class="value" id="percent">0%</div></div>
                <div><div class="label">Tank Volume</div><div class="value" id="volume">0 L</div></div>
            </div>
        </div>
        
        <div class="card">
            <h2>Sensors</h2>
            <div class="grid">
                <div><div class="label">Temperature</div><div class="value" id="temp">0°C</div></div>
                <div><div class="label">Humidity</div><div class="value" id="hum">0%</div></div>
                <div><div class="label">Soil 1</div><div class="value" id="soil1">0%</div></div>
                <div><div class="label">Soil 2</div><div class="value" id="soil2">0%</div></div>
                <div><div class="label">Soil 1 Status</div><div class="value" id="fault1">OK</div></div>
                <div><div class="label">Soil 2 Status</div><div class="value" id="fault2">OK</div></div>
            </div>
            <p style="color:#666; margin-top:15px;">Last Update: <span id="update">Never</span></p>
        </div>
        
        <div class="card">
            <h2>Login Logs</h2>
            <table>
                <tr><th>Time</th><th>User</th><th>Status</th><th>Offline</th></tr>
                {% for log in logs %}
                <tr>
                    <td>{{ log.time }}</td>
                    <td>{{ log.user }}</td>
                    <td>{{ 'Success' if log.success else 'Failed' }}</td>
                    <td>{{ 'Yes (' + log.delay_ms|string + 'ms)' if log.offline else 'No' }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, logs=login_logs[:10])

if __name__ == "__main__":
    app.run(debug=True)
