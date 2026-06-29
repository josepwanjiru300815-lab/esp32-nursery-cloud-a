from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from functools import wraps
import secrets
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# System State Memory Cache - keep your existing stuff
system_state = {
    "pump": "OFF", "valve": "STOPPED",
    "volume": 0.0, "percent": 0.0,
    "temp": 0.0, "hum": 0.0,
    "soil1": 0.0, "soil2": 0.0,
    "fault1": False, "fault2": False
}

command_buffer = {"pump": "OFF", "valve": "STOPPED"}

users = {
    "nursery": os.environ.get("USER_PASSWORD", "nursery123"),
    "admin": os.environ.get("ADMIN_PASSWORD", "admin123")
}

# Security log - stores last 100 entries
security_log = []

def add_log(msg, level="info"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip = request.remote_addr if request else "System"
    entry = {
        "time": timestamp,
        "msg": msg,
        "level": level,
        "ip": ip
    }
    security_log.insert(0, entry)
    if len(security_log) > 100: 
        security_log.pop()

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
        if session.get('user') != 'admin':
            add_log(f"Unauthorized admin access attempt to {request.path}", "error")
            return redirect(url_for('handle_login'))
        return f(*args, **kwargs)
    return decorated_function

# ----- YOUR EXISTING ROUTES - KEEP ALL THESE -----
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
        add_log(f"User login success: {username}", "success")
        return redirect('/home')
    add_log(f"Failed user login: {username}", "error")
    return redirect('/?error=1')

@app.route('/login/admin', methods=['POST'])
def handle_login_admin():
    username = request.form.get('username')
    password = request.form.get('password')
    if users.get(username) == password and username == 'admin':
        session['user'] = username
        add_log(f"Admin login success: {username}", "success")
        return redirect('/admin')
    add_log(f"Failed admin login: {username}", "error")
    return redirect('/?error=1')

@app.route('/logout')
def handle_logout():
    user = session.pop('user', None)
    if user: 
        add_log(f"Logout: {user}", "info")
    return redirect('/')

@app.route('/home')
@login_required
def handle_home(): 
    return render_template('home.html')

@app.route('/admin')
@admin_required
def handle_admin():
    return render_template('admin.html', logs=security_log)

# ----- YOUR API ROUTES - KEEP THESE TOO -----
@app.route('/api/status')
def api_status():
    return jsonify(system_state)

@app.route('/api/pump/on')
@login_required
def handle_pump_on():
    command_buffer["pump"] = "ON"
    add_log(f"Pump ON command by {session.get('user')}", "warning")
    return redirect('/nursery1')

# ... keep all your other /api routes ...

# ----- NEW ESP32 LOG ROUTE - ADD THIS -----
@app.route('/esp32/log', methods=['POST'])
def esp32_log():
    try:
        data = request.get_json()
        if not data:
            return "No data", 400
            
        username = data.get('user', 'unknown')
        success = data.get('success', False)
        esp_ip = request.remote_addr
        
        if success:
            add_log(f"ESP32 login success: {username} from ESP32 {esp_ip}", "success")
        else:
            add_log(f"ESP32 login failed: {username} from ESP32 {esp_ip}", "error")
            
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True)
