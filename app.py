import os
import secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))

# Connect to Neon Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Table for Logs
class SecurityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(50), nullable=False)
    msg = db.Column(db.String(255), nullable=False)
    level = db.Column(db.String(20), nullable=False)
    ip = db.Column(db.String(50), nullable=False)

# System State Memory Cache - resets on each serverless invocation
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

def add_log(msg, level="info"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip = "System"
    if request:
        # Vercel uses X-Forwarded-For header
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
    new_password = request.form.get('new_password')
    # Add your password update logic here
    add_log("Admin changed user password", "warning")
    return redirect('/admin')

@app.route('/admin/kick_users', methods=['POST'])
@admin_required
def kick_users():
    # Add your kick logic here
    add_log("Admin kicked all users", "warning")
    return redirect('/admin')

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
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON"}), 400

    username = data.get('user', 'unknown')
    success = data.get('success', False)

    # Get real IP - works on Vercel
    esp_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in esp_ip:
        esp_ip = esp_ip.split(',')[0].strip()

    # Log it using your existing add_log function
    if success:
        add_log(f"ESP32 login success: {username} from ESP32 {esp_ip}", "success")
    else:
        add_log(f"ESP32 login failed: {username} from ESP32 {esp_ip}", "error")

    return jsonify({"status": "ok"}), 200
@app.route('/esp32/log', methods=['POST'])
def esp32_log():
    try:
        data = request.get_json()
        if not data:
            return "No data", 400

        username = data.get('user', 'unknown')
        success = data.get('success', False)
        esp_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if esp_ip and ',' in esp_ip:
            esp_ip = esp_ip.split(',')[0].strip()

        if success:
            add_log(f"ESP32 login success: {username} from ESP32 {esp_ip}", "success")
        else:
            add_log(f"ESP32 login failed: {username} from ESP32 {esp_ip}", "error")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True)
