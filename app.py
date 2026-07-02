import os
import secrets
from datetime import datetime, timedelta
import pytz
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, session, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))

# Connect to Neon Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Kenya timezone
KENYA_TZ = pytz.timezone("Africa/Nairobi")

def get_kenya_time():
    return datetime.now(KENYA_TZ).strftime("%Y-%m-%d %H:%M:%S")

# Database Table for Logs
class SecurityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(50), nullable=False)
    msg = db.Column(db.String(255), nullable=False)
    level = db.Column(db.String(20), nullable=False)
    ip = db.Column(db.String(50), nullable=False)

# System State - matches ESP32 status JSON exactly
system_state = {
    "pump": "OFF",
    "valve": "STOPPED",
    "auto": "AUTO",
    "valveAuto": "AUTO",
    "volume": 0.0,
    "percent": 0.0,
    "temp": 0.0,
    "hum": 0.0,
    "soil1": 0.0,
    "soil2": 0.0,
    "fault1": False,
    "fault2": False
}

# Commands queued to send back to ESP32 on next data push
command_buffer = {
    "pump": None,
    "valve": None
}

users = {
    "nursery": os.environ.get("USER_PASSWORD", "12345678"),
    "admin":   os.environ.get("ADMIN_PASSWORD", "12345678")
}

def add_log(msg, level="info", custom_time=None):
    timestamp = custom_time if custom_time else get_kenya_time()
    ip = "System"
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
    except Exception:
        pass
    try:
        new_log = SecurityLog(time=timestamp, msg=msg, level=level, ip=ip or "unknown")
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Database log error: {e}")

# ========== SESSION TIMEOUT = 20 MINUTES ==========
SESSION_TIMEOUT = timedelta(minutes=20)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('handle_login'))
        # Check inactivity timeout
        last_active = session.get('last_active')
        if last_active:
            elapsed = datetime.utcnow() - datetime.fromisoformat(last_active)
            if elapsed > SESSION_TIMEOUT:
                user = session.get('user')
                session.clear()
                add_log(f"Session expired (20min inactivity): {user}", "warning")
                return redirect(url_for('handle_login'))
        # Reset timer on every page/action visit
        session['last_active'] = datetime.utcnow().isoformat()
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user') != 'admin':
            return redirect(url_for('handle_login'))
        # Check inactivity timeout
        last_active = session.get('last_active')
        if last_active:
            elapsed = datetime.utcnow() - datetime.fromisoformat(last_active)
            if elapsed > SESSION_TIMEOUT:
                user = session.get('user')
                session.clear()
                add_log(f"Admin session expired (20min inactivity): {user}", "warning")
                return redirect(url_for('handle_login'))
        session['last_active'] = datetime.utcnow().isoformat()
        return f(*args, **kwargs)
    return decorated_function

# ========== STATIC FILES ==========
@app.route('/img/<path:filename>')
def serve_img(filename):
    return send_from_directory('static', filename)

# ========== AUTH ROUTES ==========
@app.route('/')
def handle_root():
    return render_template('login.html')

@app.route('/login')
def handle_login():
    return render_template('login.html')

@app.route('/login/user', methods=['POST'])
def handle_login_user():
    username = request.form.get('username')
    password = request.form.get('password')
    if users.get(username) == password and username == 'nursery':
        session['user'] = username
        session['last_active'] = datetime.utcnow().isoformat()
        add_log(f"User login success: {username}", "success")
        return redirect('/home')
    add_log(f"User login failed: {username}", "error")
    return redirect('/?error=1')

@app.route('/login/admin', methods=['POST'])
def handle_login_admin():
    username = request.form.get('username')
    password = request.form.get('password')
    if users.get(username) == password and username == 'admin':
        session['user'] = username
        session['last_active'] = datetime.utcnow().isoformat()
        add_log(f"Admin login success: {username}", "success")
        return redirect('/admin')
    add_log(f"Admin login failed: {username}", "error")
    return redirect('/?error=1')

@app.route('/logout')
def handle_logout():
    user = session.pop('user', None)
    session.clear()
    if user:
        add_log(f"Logout: {user}", "info")
    return redirect('/')

# ========== PAGE ROUTES ==========
@app.route('/home')
@login_required
def handle_home():
    return render_template('home.html')

@app.route('/beds')
@login_required
def handle_beds():
    return render_template('beds.html')

@app.route('/nursery1')
@login_required
def handle_nursery1():
    return render_template('nursery1.html')

@app.route('/nursery2')
@login_required
def handle_nursery2():
    return render_template('nursery2.html')

@app.route('/nursery3')
@login_required
def handle_nursery3():
    return render_template('nursery3.html')

@app.route('/about')
@login_required
def handle_about():
    return render_template('about.html')

@app.route('/vision')
@login_required
def handle_vision():
    return render_template('vision.html')

@app.route('/contacts')
@login_required
def handle_contacts():
    return render_template('contacts.html')

# ========== ADMIN ROUTES ==========
@app.route('/admin')
@admin_required
def handle_admin():
    return render_template('admin.html')

@app.route('/api/logs')
@admin_required
def api_logs():
    try:
        db_logs = SecurityLog.query.order_by(SecurityLog.id.desc()).limit(50).all()
        logs = [{"time": l.time, "msg": l.msg, "level": l.level, "ip": l.ip} for l in db_logs]
        return jsonify(logs)
    except Exception as e:
        db.session.rollback()
        return jsonify([{"time": "-", "msg": f"Log error: {e}", "level": "error", "ip": "-"}]), 500

@app.route('/admin/change_pass', methods=['POST'])
@admin_required
def change_pass():
    add_log("Admin changed user password", "warning")
    return redirect('/admin')

@app.route('/admin/kick_users', methods=['POST'])
@admin_required
def kick_users():
    add_log("Admin kicked all users", "warning")
    return redirect('/admin')

# ========== STATUS API ==========
# NOTE: /status does NOT reset the inactivity timer on purpose
# so that a tab left open polling every 1.5s does not keep session alive
@app.route('/status')
def status_esp32():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(system_state)

@app.route('/api/status')
def api_status():
    return jsonify(system_state)

# ========== PUMP CONTROL ==========
@app.route('/pump/on')
@login_required
def pump_on():
    if system_state['auto'] == 'AUTO':
        add_log("Pump ON blocked - AUTO mode active", "warning")
        return jsonify({"blocked": True})
    command_buffer['pump'] = 'ON'
    system_state['pump'] = 'ON'
    add_log("Pump turned ON via cloud dashboard", "info")
    return jsonify({"ok": True})

@app.route('/pump/off')
@login_required
def pump_off():
    if system_state['auto'] == 'AUTO':
        add_log("Pump OFF blocked - AUTO mode active", "warning")
        return jsonify({"blocked": True})
    command_buffer['pump'] = 'OFF'
    system_state['pump'] = 'OFF'
    add_log("Pump turned OFF via cloud dashboard", "info")
    return jsonify({"ok": True})

@app.route('/toggleAuto')
@login_required
def toggle_auto():
    system_state['auto'] = 'MANUAL' if system_state['auto'] == 'AUTO' else 'AUTO'
    if system_state['auto'] == 'MANUAL':
        command_buffer['pump'] = 'OFF'
        system_state['pump'] = 'OFF'
    add_log(f"Pump mode switched to {system_state['auto']}", "info")
    return jsonify({"ok": True})

# ========== VALVE CONTROL ==========
@app.route('/valve/open')
@login_required
def valve_open():
    if system_state['valveAuto'] == 'AUTO':
        add_log("Valve OPEN blocked - AUTO mode active", "warning")
        return jsonify({"blocked": True})
    command_buffer['valve'] = 'OPENING'
    system_state['valve'] = 'OPENING'
    add_log("Valve opening via cloud dashboard", "info")
    return jsonify({"ok": True})

@app.route('/valve/close')
@login_required
def valve_close():
    if system_state['valveAuto'] == 'AUTO':
        add_log("Valve CLOSE blocked - AUTO mode active", "warning")
        return jsonify({"blocked": True})
    command_buffer['valve'] = 'CLOSING'
    system_state['valve'] = 'CLOSING'
    add_log("Valve closing via cloud dashboard", "info")
    return jsonify({"ok": True})

@app.route('/valve/stop')
@login_required
def valve_stop():
    if system_state['valveAuto'] == 'AUTO':
        add_log("Valve STOP blocked - AUTO mode active", "warning")
        return jsonify({"blocked": True})
    command_buffer['valve'] = 'STOPPED'
    system_state['valve'] = 'STOPPED'
    add_log("Valve stopped via cloud dashboard", "info")
    return jsonify({"ok": True})

@app.route('/toggleValveAuto')
@login_required
def toggle_valve_auto():
    system_state['valveAuto'] = 'MANUAL' if system_state['valveAuto'] == 'AUTO' else 'AUTO'
    if system_state['valveAuto'] == 'MANUAL':
        command_buffer['valve'] = 'STOPPED'
        system_state['valve'] = 'STOPPED'
    add_log(f"Valve mode switched to {system_state['valveAuto']}", "info")
    return jsonify({"ok": True})

# ========== ESP32 DATA PUSH ==========
@app.route('/esp32/log', methods=['POST'])
def esp32_log():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON"}), 400

    esp_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if esp_ip and ',' in esp_ip:
        esp_ip = esp_ip.split(',')[0].strip()

    # Login log from ESP32
    if 'user' in data and 'success' in data:
        username = data.get('user', 'unknown')
        success = data.get('success', False)
        esp_time = data.get('time')
        level = "success" if success else "error"
        msg = f"ESP32 login {'success' if success else 'failed'}: {username} from {esp_ip}"
        add_log(msg, level, custom_time=esp_time)
        return jsonify({"status": "logged"}), 200

    # Sensor data from ESP32
    if 'temp' in data:
        system_state.update({
            "temp":    data.get('temp',    0.0),
            "hum":     data.get('hum',     0.0),
            "soil1":   data.get('soil1',   0.0),
            "soil2":   data.get('soil2',   0.0),
            "fault1":  data.get('fault1',  False),
            "fault2":  data.get('fault2',  False),
            "percent": data.get('percent', 0.0),
            "volume":  data.get('volume',  0.0)
        })
        # Send queued commands then clear them
        response = {}
        if command_buffer['pump'] is not None:
            response['pump'] = command_buffer['pump']
            command_buffer['pump'] = None
        if command_buffer['valve'] is not None:
            response['valve'] = command_buffer['valve']
            command_buffer['valve'] = None
        return jsonify(response), 200

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(debug=True)
