from flask import Flask, jsonify, request, Response, render_template
from flask_cors import CORS
import threading
import requests
import os

from db import update_device_status, get_device_status, update_many_status

# ===============================
# CONFIG
# ===============================
WEB_AUTH_URL = "https://rfid-database-1.onrender.com/api/login_user"

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
    mapping = {
        "on": "ON",
        "off": "OFF",
        "lock": "LOCKED",
        "unlock": "UNLOCKED"
    }
    return mapping.get(action, action.upper())


# ===============================
# FRONTEND
# ===============================

@app.route("/ping")
def ping():
    return "alive"


@app.route("/")
def login_page():
    return render_template("login.html")


@app.route("/main")
def main_page():
    return render_template("main.html")


# ===============================
# DEVICE CONTROL (Dashboard → ESP32)
# ===============================
@app.route("/device/<device>", methods=["POST"])
def control_device(device):

    data = request.get_json(silent=True) or {}

    action = data.get("action", "").lower()
    device_id = data.get("device_id", DEFAULT_DEVICE_ID)

    key = (device, action)

    if key not in CMD_MAP:
        return jsonify({"error": "Invalid command"}), 400

    cmd = CMD_MAP[key]

    # queue command for ESP32
    queue_command(device_id, cmd)

    state = action_to_state(action)

    # save to MongoDB
    update_device_status(device_id, device, state)

    # update RAM cache
    with status_lock:
        device_status.setdefault(device_id, {})[device] = state

    return jsonify({
        "queued": cmd,
        "device": device,
        "state": state
    })


# ===============================
# ESP32 POLL (ESP32 → server)
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
# MOBILE LOGIN (proxy auth server)
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
# DEVICE STATUS UPDATE (ESP32 → server)
# ===============================
@app.route("/api/status", methods=["POST"])
def post_status():

    data = request.get_json(silent=True) or {}

    device_id = data.get("device_id", DEFAULT_DEVICE_ID)
    status = data.get("status", {})

    # save to MongoDB
    update_many_status(device_id, status)

    # update RAM cache
    with status_lock:
        device_status.setdefault(device_id, {}).update(status)

    return jsonify({"ok": True})


# ===============================
# GET DEVICE STATUS (Dashboard)
# ===============================
@app.route("/api/status", methods=["GET"])
def get_status():

    device_id = request.args.get("device_id", DEFAULT_DEVICE_ID)

    # get from MongoDB
    status = get_device_status(device_id)

    return jsonify({"status": status})


# ===============================
# LOCAL RUN ONLY
# ===============================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
