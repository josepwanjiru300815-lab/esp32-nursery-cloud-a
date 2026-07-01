from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import json
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = 'nursery_secret_key_2024' # Change this

# Global state - server is master
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
    "valve": "STOPPED"
}

# Users
USERS = {
    "admin": "admin123",
    "farmer": "farm2024",
    "user": "user123"
}

# Login logs
login_logs = []

# ==================== ESP32 API ROUTES ====================

@app.route("/esp32/log", methods=["POST"])
def esp32_log():
    global system_state, command_buffer
    data = request.get_json()

    # 1. Update ONLY sensor data from ESP32 - don't accept pump/valve
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
        "pump": system_state["pump"],
        "valve": command_buffer["valve"]
    }

    # 3. If we sent a valve command, update state and clear buffer
    if command_buffer["valve"]!= "STOPPED":
        system_state["valve"] = command_buffer["valve"]
        command_buffer["valve"] = "STOPPED"

    return jsonify(response)

@app.route("/pump/on")
def pump_on():
    if not session.get("logged_in"):
        return jsonify({"error": "Not logged in"}), 401
    system_state["pump"] = "ON"
    return jsonify({"status": "ok", "pump": "ON"})

@app.route("/pump/off")
def pump_off():
    if not session.get("logged_in"):
        return jsonify({"error": "Not logged in"}), 401
    system_state["pump"] = "OFF"
    return jsonify({"status": "ok", "pump": "OFF"})

@app.route("/valve/open")
def valve_open():
    if not session.get("logged_in"):
        return jsonify({"error": "Not logged in"}), 401
    command_buffer["valve"] = "OPENING"
    return jsonify({"status": "ok", "valve": "OPENING"})

@app.route("/valve/close")
def valve_close():
    if not session.get("logged_in"):
        return jsonify({"error": "Not logged in"}), 401
    command_buffer["valve"] = "CLOSING"
    return jsonify({"status": "ok", "valve": "CLOSING"})

@app.route("/valve/stop")
def valve_stop():
    if not session.get("logged_in"):
        return jsonify({"error": "Not logged in"}), 401
    command_buffer["valve"] = "STOPPED"
    system_state["valve"] = "STOPPED"
    return jsonify({"status": "ok", "valve": "STOPPED"})

@app.route("/status")
def status():
    return jsonify(system_state)

# ==================== HTML PAGE ROUTES ====================

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in USERS and USERS[username] == password:
            session["logged_in"] = True
            session["username"] = username
            login_logs.insert(0, {
                "user": username,
                "success": True,
                "time": datetime.now(pytz.timezone('Africa/Nairobi')).strftime("%Y-%m-%d %H:%M:%S"),
                "ip": request.remote_addr
            })
            return redirect(url_for("admin"))
        else:
            login_logs.insert(0, {
                "user": username,
                "success": False,
                "time": datetime.now(pytz.timezone('Africa/Nairobi')).strftime("%Y-%m-%d %H:%M:%S"),
                "ip": request.remote_addr
            })
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html", error=None)

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("admin.html", logs=login_logs[:20], state=system_state)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/beds")
def beds():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("beds.html", state=system_state)

@app.route("/contacts")
def contacts():
    return render_template("contacts.html")

@app.route("/nursery1")
def nursery1():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("nursery1.html", state=system_state)

@app.route("/nursery2")
def nursery2():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("nursery2.html", state=system_state)

@app.route("/nursery3")
def nursery3():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("nursery3.html", state=system_state)

@app.route("/vision")
def vision():
    return render_template("vision.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
