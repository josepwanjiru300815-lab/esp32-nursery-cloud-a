import os
import secrets
from datetime import datetime
import pytz
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, session, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_HTTPONLY'] = True
# Connect to Neon Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Kenya timezone using pytz
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

# System State Memory Cache
system_state = {
    "pump": "OFF", "valve": "STOPPED",
    "volume": 0.0, "percent": 0.0,
    "temp": 0.0, "hum": 0.0,
    "soil1": 0.0, "soil2": 0.0,
    "fault1": False, "fault2": False
}

command_buffer = {"pump": "OFF", "valve": "STOPPED"}

users = {
    "nursery": os.environ.get("USER_PASSWORD", "12345678"),
    "admin": os.environ.get("ADMIN_PASSWORD", "12345678")
}

def add_log(msg, level="info", custom_time=None):
    timestamp = custom_time if custom_time else get_kenya_time()
    ip = "System"
    if request:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
    try:
        new_log = SecurityLog(time=timestamp, msg=msg, level=level, ip=ip or "unknown")
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Database log error: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            add_log(f"Unauthorized access attempt to {request.path}", "error")
            return redirect(url_for('handle_login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user')!= 'admin':
            add_log(f"Unauthorized admin access attempt to {request.path}", "error")
            return redirect(url_for('handle_login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== STATIC IMAGE ROUTE FOR ESP32 /img/ ==========
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
        add_log(f"Vercel user login success: {username}", "success")
        return redirect('/home')
    add_log(f"Failed Vercel user login: {username}", "error")
    return redirect('/?error=1')
@app.route('/test')
def test_route():
    return "TEST WORKS - Routes are loading"
@app.route('/login/admin', methods=['POST'])
def handle_login_admin():
    username = request.form.get('username')
    password = request.form.get('password')
    if users.get(username) == password and username == 'admin':
        session['user'] = username
        add_log(f"Vercel admin login success: {username}", "success")
        return redirect('/admin')
    add_log(f"Failed Vercel admin login: {username}", "error")
    return redirect('/?error=1')

@app.route('/logout')
def handle_logout():
    user = session.pop('user', None)
    if user:
        add_log(f"Logout: {user}", "info")
    return redirect('/')

# ========== MAIN PAGES ==========
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

@app.route('/contact')
@login_required
def handle_contact():
    return render_template('contact.html')

@app.route('/contacts')
@login_required
def handle_contacts():
    return render_template('contacts.html')

# ========== ADMIN PAGES ==========
@app.route('/admin')
@admin_required
def handle_admin():
    return render_template('admin.html')

@app.route('/adminpanel')
@admin_required
def handle_adminpanel():
    return render_template('adminpanel.html')

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
    new_password = request.form.get('new_password')
    add_log("Admin changed user password", "warning")
    return redirect('/admin')

@app.route('/admin/kick_users', methods=['POST'])
@admin_required
def kick_users():
    add_log("Admin kicked all users", "warning")
    return redirect('/admin')

# ========== API ROUTES ==========
@app.route('/api/status')
def api_status():
    return jsonify(system_state)

# ADDED: This route fixes nursery1.html buttons and live updates
@app.route('/status')
def status_esp32():
    return jsonify(system_state)

@app.route('/api/contacts')
@login_required
def get_contacts():
    contacts = [
        {"name": "JOSEPH", "img": url_for('static', filename='joseph.jpg'), "role": "Developer", "phone": "+254700000001"},
        {"name": "AYUB", "img": url_for('static', filename='ayub.jpg'), "role": "Supervisor", "phone": "+254700000002"},
        {"name": "DR.MAITETHIA", "img": url_for('static', filename='maitethia.jpg'), "role": "Lead Supervisor", "phone": "+254700000003"},
    ]
    return jsonify(contacts)

# ========== PUMP/VALVE CONTROL ROUTES - ADDED FOR ESP32 COMPATIBILITY ==========
# ========== PUMP/VALVE CONTROL ROUTES - TESTING WITHOUT LOGIN ==========
@app.route('/pump/on')
def pump_on():
    command_buffer["pump"] = "ON"
    # add_log("Pump turned ON via web", "info")  # COMMENT OUT FOR NOW
    return redirect('/nursery1')

@app.route('/pump/off')
def pump_off():
    command_buffer["pump"] = "OFF"
    # add_log("Pump turned OFF via web", "info")  # COMMENT OUT FOR NOW
    return redirect('/nursery1')

@app.route('/valve/open')
def valve_open():
    command_buffer["valve"] = "OPENING"
    # add_log("Valve opening via web", "info")  # COMMENT OUT FOR NOW
    return redirect('/nursery1')

@app.route('/valve/close')
def valve_close():
    command_buffer["valve"] = "CLOSING"
    # add_log("Valve closing via web", "info")  # COMMENT OUT FOR NOW
    return redirect('/nursery1')

@app.route('/valve/stop')
def valve_stop():
    command_buffer["valve"] = "STOPPED"
    # add_log("Valve stopped via web", "info")  # COMMENT OUT FOR NOW
    return redirect('/nursery1')

# ========== ESP32 INTEGRATION ==========
@app.route('/esp32/log', methods=['POST'])
def esp32_log():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON"}), 400

    esp_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if esp_ip and ',' in esp_ip:
        esp_ip = esp_ip.split(',')[0].strip()

    if 'user' in data and 'success' in data:
        username = data.get('user', 'unknown')
        success = data.get('success', False)
        esp_time = data.get('time')
        if success:
            add_log(f"ESP32 login success: {username} from {esp_ip}", "success", custom_time=esp_time)
        else:
            add_log(f"ESP32 login failed: {username} from {esp_ip}", "error", custom_time=esp_time)
        return jsonify({"status": "logged"}), 200

    if 'temp' in data:
        system_state.update({
            "pump": data.get('pump', 'OFF'),
            "valve": data.get('valve', 'STOPPED'),
            "temp": data.get('temp', 0.0),
            "hum": data.get('hum', 0.0),
            "soil1": data.get('soil1', 0.0),
            "soil2": data.get('soil2', 0.0),
            "fault1": data.get('fault1', False),
            "fault2": data.get('fault2', False),
            "percent": data.get('percent', 0.0),
            "volume": data.get('volume', 0.0)
        })
        return jsonify({
            "pump": command_buffer["pump"],
            "valve": command_buffer["valve"]
        }), 200

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(debug=True)
