from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from functools import wraps
import secrets
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

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
    "nursery": os.environ.get("USER_PASSWORD", "nursery123"),
    "admin": os.environ.get("ADMIN_PASSWORD", "admin123")
}

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

@app.route('/contact')
@login_required
def handle_contact(): 
    return render_template('contact.html')

@app.route('/admin')
@admin_required
def handle_admin():
    return render_template('admin.html', logs=security_log)

@app.route('/api/status')
def api_status():
    return jsonify(system_state)

@app.route('/contacts')
@login_required
def handle_contacts(): 
    return render_template('contacts.html')
@app.route('/api/contacts')
@login_required  
def get_contacts():
    contacts = [
        {"name": "JOSEPH", "img": url_for('static', filename='joseph.jpg'), "role": "Developer", "phone": "+254700000001"},
        {"name": "AYUB", "img": url_for('static', filename='ayub.jpg'), "role": "Supervisor", "phone": "+254700000002"},
        {"name": "DR.MAITETHIA", "img": url_for('static', filename='maitethia.jpg'), "role": "Lead Supervisor", "phone": "+254700000003"},
    ]
    return jsonify(contacts)

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
