from flask import Flask, jsonify, request, Response, render_template
from flask_cors import CORS
import threading
import requests

WEB_AUTH_URL = "https://rfid-database.onrender.com/api/login_user"


app = Flask(__name__)
CORS(app)

# ===============================
# DATA STORAGE
# ===============================
command_queues = {}
device_status = {}

queues_lock = threading.Lock()
status_lock = threading.Lock()

DEFAULT_DEVICE_ID = "esp32_1"

# ===============================
# COMMAND MAP
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
# HELPERS
# ===============================
def queue_command(device_id, cmd):
    with queues_lock:
        command_queues.setdefault(device_id, []).append(cmd)

def action_to_state(action):
    if action == "on":
        return "ON"
    if action == "off":
        return "OFF"
    if action == "lock":
        return "LOCKED"
    if action == "unlock":
        return "UNLOCKED"
    return action.upper()

# ===============================
# FRONTEND
# ===============================
@app.route("/")
def login_page():
    """ Login Page """
    return render_template("login.html")


@app.route("/main")
def main_page():
    """ Main Dashboard Page """
    return render_template("main.html")
# ===============================
# DEVICE CONTROL
# ===============================
@app.route("/device/<device>", methods=["POST"])
def control_device(device):
    data = request.json or {}
    action = data.get("action", "").lower()
    device_id = data.get("device_id", DEFAULT_DEVICE_ID)

    key = (device, action)
    if key not in CMD_MAP:
        return jsonify({"error": "Invalid command"}), 400

    cmd = CMD_MAP[key]
    queue_command(device_id, cmd)

    with status_lock:
        device_status.setdefault(device_id, {})[device] = action_to_state(action)

    return jsonify({
        "queued": cmd,
        "device": device,
        "state": action_to_state(action)
    })

# ===============================
# ESP32 POLL
# ===============================
@app.route("/api/poll")
def poll():
    device_id = request.args.get("device_id", DEFAULT_DEVICE_ID)
    with queues_lock:
        q = command_queues.get(device_id, [])
        if q:
            return Response(q.pop(0), mimetype="text/plain")
    return Response("", mimetype="text/plain")

# ===============================
# STATUS UPDATE FROM DEVICE
# ===============================

@app.route("/api/login", methods=["POST"])
def mobile_login():
    data = request.json or {}
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

    data = resp.json()
    if not data.get("success"):
        return jsonify(data), 401

    return jsonify({
        "success": True,
        "user": data["user"]
    })

@app.route("/api/status", methods=["POST"])
def post_status():
    data = request.json or {}
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
    app.run(host="0.0.0.0", port=10000)

