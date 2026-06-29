from flask import request, jsonify
import json

@app.route('/esp32/log', methods=['POST'])
def esp32_log():
    try:
        data = request.get_json()
        if not data:
            return "No data", 400
            
        username = data.get('user', 'unknown')
        success = data.get('success', False)
        esp_ip = request.remote_addr  # ESP32's public IP
        
        if success:
            add_log(f"ESP32 login success: {username} from ESP32 {esp_ip}", "success")
        else:
            add_log(f"ESP32 login failed: {username} from ESP32 {esp_ip}", "error")
            
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return str(e), 500
