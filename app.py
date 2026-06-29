from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from functools import wraps
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Change this to a fixed secret in production

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

# Simple user storage - replace with DB in production
users = {
    "nursery": "nursery123",  # username: password
    "admin": "admin123"
}

# Security log - replace with DB in production
security_log = []

def add_log(msg, level="info"):
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    security_log.insert(0, f"[{timestamp}] {msg}")
    if len(security_log) > 100: security_log.pop()

# Auth decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('handle_login', error=1))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user') != 'admin':
            return redirect(url_for('handle_login', error=1))
        return f(*args, **kwargs)
    return decorated_function

# Web Interface Endpoints
@app.route('/')
def handle_root(): return render_template('login.html')

@app.route('/home')
@login_required
def handle_home(): return render_template('home.html')

@app.route('/about')
def handle_about(): return render_template('about.html')

@app.route('/vision')
def handle_vision(): return render_template('vision.html')

@app.route('/contacts')
def handle_contacts(): return render_template('contacts.html')

@app.route('/beds')
@login_required
def handle_beds(): return render_template('beds.html')

@app.route('/nursery1')
@login_required
def handle_nursery1(): return render_template('nursery1.html')

@app.route('/nursery2')
@login_required
def handle_nursery2():
    return "<body style='background:#0f172a;color:white;font-family:Arial;text-align:center;padding:40px'><h1>Nursery Bed 2</h1><p style='color:#94a3b8'>Yet to be updated</p><a href='/beds' style='color:#38bdf8'>← Back</a></body>"

@app.route('/nursery3')
@login_required
def handle_nursery3():
    return "<body style='background:#0f172a;color:white;font-family:Arial;text-align:center;padding:40px'><h1>Nursery Bed 3</h1><p style='color:#94a3b8'>Yet to be updated</p><a href='/beds' style='color:#38bdf8'>← Back</a></body>"

# Login routes
@app.route('/login')
def handle_login(): return render_template('login.html')

@app.route('/login/user', methods=['POST'])
def handle_login_user():
    username = request.form.get('username')
    password = request.form.get('password')
    if users.get(username) == password and username == 'nursery':
        session['user'] = username
        add_log(f"User login: {username}", "success")
        return redirect('/home')
    add_log(f"Failed login attempt: {username}", "error")
    return redirect('/?error=1')

@app.route('/login/admin', methods=['POST'])
def handle_login_admin():
    username = request.form.get('username')
    password = request.form.get('password')
    if users.get(username) == password and username == 'admin':
        session['user'] = username
        add_log(f"Admin login: {username}", "success")
        return redirect('/admin')
    add_log(f"Failed admin login attempt: {username}", "error")
    return redirect('/?error=1')

@app.route('/logout')
def handle_logout():
    user = session.pop('user', None)
    if user: add_log(f"Logout: {user}")
    return redirect('/')

# Admin page
@app.route('/admin')
@admin_required
def handle_admin():
    return render_template('admin.html', logs=security_log)

@app.route('/admin/change_pass', methods=['POST'])
@admin_required
def handle_change_pass():
    new_pass = request.form.get('new_password')
    users['nursery'] = new_pass
    add_log("User password changed by admin", "warning")
    return redirect('/admin')

@app.route('/admin/kick_users', methods=['POST'])
@admin_required
def handle_kick_users():
    # In real app, you'd invalidate all sessions here
    add_log("Kick all users triggered by admin", "warning")
    return redirect('/admin')

# UI Interactivity Control Actions - add /api prefix to match JS
@app.route('/api/pump/on')
@login_required
def handle_pump_on():
    command_buffer["pump"] = "ON"
    add_log("Pump ON command sent")
    return redirect('/nursery1')

@app.route('/api/pump/off')
@login_required
def handle_pump_off():
    command_buffer["pump"] = "OFF"
    add_log("Pump OFF command sent")
    return redirect('/nursery1')

@app.route('/api/valve/open')
@login_required
def handle_valve_open():
    command_buffer["valve"] = "OPEN"
    add_log("Valve OPEN command sent")
    return redirect('/nursery1')

@app.route('/api/valve/close')
@login_required
def handle_valve_close():
    command_buffer["valve"] = "CLOSE"
    add_log("Valve CLOSE command sent")
    return redirect('/nursery1')

@app.route('/api/valve/stop')
@login_required
def handle_valve_stop():
    command_buffer["valve"] = "STOP"
    add_log("Valve STOP command sent")
    return redirect('/nursery1')

# Live UI Telemetry Polling Endpoint
@app.route('/api/status')
@login_required
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
