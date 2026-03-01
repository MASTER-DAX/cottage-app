from flask import Flask, jsonify, request, Response, render_template
from flask_cors import CORS
import threading
import requests
import os

# ===============================
# CONFIG
# ===============================
WEB_AUTH_URL = "https://rfid-database.onrender.com/api/login_user"

app = Flask(__name__)
CORS(app)

# ===============================
# GLOBAL ONE-SHOT COMMAND (ALEXA STYLE)
# ===============================
last_command = "0"
command_lock = threading.Lock()

DEFAULT_DEVICE_ID = "esp32_1"

# ===============================
# COMMAND MAP (UNCHANGED)
# ===============================
CMD_MAP = {
    ("front_light", "on"): "1",
    ("front_light", "off"): "2",

    ("bed_light", "on"): "3",
    ("bed_light", "off"): "4",

    ("front_fan", "on"): "5",
    ("front_fan", "off"): "6",

    ("bed_fan", "on"): "7",
    ("bed_fan", "off"): "8",

    ("purifier", "on"): "9",
    ("purifier", "off"): "A",

    ("privacy_lights", "on"): "B",
    ("privacy_lights", "off"): "C",

    ("front_door", "unlock"): "D",
    ("front_door", "lock"): "E",

    ("bed_door", "unlock"): "F",
    ("bed_door", "lock"): "G",
}

# ===============================
# HELPERS (UNCHANGED)
# ===============================
def action_to_state(action):
    mapping = {
        "on": "ON",
        "off": "OFF",
        "lock": "LOCKED",
        "unlock": "UNLOCKED"
    }
    return mapping.get(action, action.upper())

# ===============================
# FRONTEND PAGES (UNCHANGED)
# ===============================
@app.route("/")
def login_page():
    return render_template("login.html")


@app.route("/main")
def main_page():
    return render_template("main.html")

# ===============================
# MOBILE DASHBOARD → SEND COMMAND
# ===============================
@app.route("/device/<device>", methods=["POST"])
def control_device(device):
    global last_command

    data = request.get_json(silent=True) or {}
    action = data.get("action", "").lower()

    key = (device, action)
    if key not in CMD_MAP:
        return jsonify({"error": "Invalid command"}), 400

    with command_lock:
        last_command = CMD_MAP[key]

    return jsonify({
        "sent": last_command,
        "device": device,
        "state": action_to_state(action)
    })

# ===============================
# ESP32 POLL (ONE-SHOT, ALEXA STYLE)
# ===============================
@app.route("/api/poll", methods=["GET"])
def poll():
    global last_command

    with command_lock:
        cmd = last_command
        last_command = "0"   # AUTO RESET

    return Response(cmd, mimetype="text/plain")

# ===============================
# MOBILE LOGIN (UNCHANGED)
# ===============================
@app.route("/api/login", methods=["POST"])
def mobile_login():
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    employee_id = data.get("employee_id")

    if not name or not employee_id:
        return jsonify({"success": False, "message": "Missing credentials"}), 400

    try:
        resp = requests.post(
            WEB_AUTH_URL,
            json={"name": name, "employee_id": employee_id},
            timeout=5
        )
    except requests.exceptions.RequestException:
        return jsonify({"success": False, "message": "Auth server unreachable"}), 503

    if resp.status_code != 200:
        return jsonify({"success": False, "message": "Invalid login"}), 401

    return jsonify(resp.json())

# ===============================
# DEVICE STATUS UPDATE (UNCHANGED)
# ===============================
device_status = {}
status_lock = threading.Lock()

@app.route("/api/status", methods=["POST"])
def post_status():
    data = request.get_json(silent=True) or {}

    device_id = data.get("device_id", DEFAULT_DEVICE_ID)
    status = data.get("status", {})

    with status_lock:
        device_status.setdefault(device_id, {}).update(status)

    return jsonify({"ok": True})


@app.route("/api/status", methods=["GET"])
def get_status():
    device_id = request.args.get("device_id", DEFAULT_DEVICE_ID)

    with status_lock:
        return jsonify({"status": device_status.get(device_id, {})})

# ===============================
# LOCAL RUN
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
