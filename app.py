
# backend/app.py
from flask import Flask, jsonify, request, Response, render_template
from flask_cors import CORS
import threading

app = Flask(__name__)
CORS(app)

# In-memory command queues: device_id -> list of command chars
command_queues = {}
queues_lock = threading.Lock()

# Last status reported by each device (can be used by frontend to display current known states)
device_status = {}
status_lock = threading.Lock()

# Map frontend device+action -> single-char command for Arduino/ESP32
CMD_MAP = {
    # Lights
    ("front_light", "on"): "1",
    ("front_light", "off"): "2",
    ("bed_light", "on"): "3",
    ("bed_light", "off"): "4",
    # Fans
    ("front_fan", "on"): "5",
    ("front_fan", "off"): "6",
    ("bed_fan", "on"): "7",
    ("bed_fan", "off"): "8",
    # Purifier
    ("purifier", "on"): "9",
    ("purifier", "off"): "A",
    # Privacy lights
    ("privacy_lights", "on"): "B",
    ("privacy_lights", "off"): "C",
    # Doors (lock/unlock)
    ("front_door", "unlock"): "D",
    ("front_door", "lock"): "E",
    ("bed_door", "unlock"): "F",
    ("bed_door", "lock"): "G",
}

# Default device id used by the frontend if none provided
DEFAULT_DEVICE_ID = "esp32_1"

def queue_command(device_id: str, cmd_char: str):
    """Append a single-char command to the device's queue."""
    with queues_lock:
        q = command_queues.setdefault(device_id, [])
        q.append(cmd_char)

def action_to_display_state(device: str, action: str):
    """Convert action (on/off/lock/unlock) to a frontend display string."""
    a = action.lower()
    if a in ("on", "off"):
        return "ON" if a == "on" else "OFF"
    if a in ("lock", "unlock"):
        return "UNLOCKED" if a == "unlock" else "LOCKED"
    return a.upper()

# Generic device control endpoint used by the updated frontend
@app.route('/device/<device_name>', methods=['POST'])
def device_control(device_name):
    data = request.json or {}
    action = (data.get('action') or "").lower()
    device_id = data.get('device_id', DEFAULT_DEVICE_ID)

    key = (device_name, action)
    if key not in CMD_MAP:
        return jsonify({"error": "invalid action or device", "device": device_name, "action": action}), 400

    cmd_char = CMD_MAP[key]
    queue_command(device_id, cmd_char)

    # Optionally update last known status (optimistic)
    display = action_to_display_state(device_name, action)
    with status_lock:
        # store as e.g. {"front_light": "ON"} keyed per device name under the device_id
        per_dev = device_status.setdefault(device_id, {})
        per_dev[device_name] = display

    return jsonify({
        "queued": cmd_char,
        "device": device_name,
        "new_state": display
    })

# Keep compatibility endpoints if other code expects /fan, /light, /purifier, /door
@app.route('/fan', methods=['POST'])
def fan_control():
    data = request.json or {}
    action = (data.get('action') or "").lower()
    # map 'fan' to front_fan by default (left for backward compatibility)
    return device_control_internal("front_fan", action, data.get('device_id', DEFAULT_DEVICE_ID))

@app.route('/light', methods=['POST'])
def light_control():
    data = request.json or {}
    # For compatibility, toggle front_light
    return device_control_internal("front_light", (data.get('action') or "").lower(), data.get('device_id', DEFAULT_DEVICE_ID))

@app.route('/purifier', methods=['POST'])
def purifier_control():
    data = request.json or {}
    return device_control_internal("purifier", (data.get('action') or "").lower(), data.get('device_id', DEFAULT_DEVICE_ID))

@app.route('/door', methods=['POST'])
def door_control():
    data = request.json or {}
    # Map to front_door for compatibility
    return device_control_internal("front_door", (data.get('action') or "").lower(), data.get('device_id', DEFAULT_DEVICE_ID))

def device_control_internal(device_name, action, device_id):
    key = (device_name, action)
    if key not in CMD_MAP:
        return jsonify({"error": "invalid action or device", "device": device_name, "action": action}), 400
    cmd_char = CMD_MAP[key]
    queue_command(device_id, cmd_char)
    display = action_to_display_state(device_name, action)
    with status_lock:
        per_dev = device_status.setdefault(device_id, {})
        per_dev[device_name] = display
    return jsonify({"queued": cmd_char, "device": device_name, "new_state": display})

# --- Poll endpoint used by ESP32: returns a single char command (text/plain) or empty body ---
@app.route('/api/poll', methods=['GET'])
def api_poll():
    device_id = request.args.get('device_id', DEFAULT_DEVICE_ID)
    with queues_lock:
        q = command_queues.get(device_id, [])
        if q:
            cmd = q.pop(0)
            return Response(cmd, mimetype='text/plain')
    return Response('', mimetype='text/plain')

# --- Device posts statuses here after executing a command (e.g. ESP32/Arduino can POST actual statuses) ---
@app.route('/api/status', methods=['POST'])
def api_status():
    data = request.json or {}
    device_id = data.get('device_id', DEFAULT_DEVICE_ID)
    status = data.get('status', {})  # expect JSON object mapping device names -> states
    if not isinstance(status, dict):
        return jsonify({"error": "status must be an object/dict"}), 400
    with status_lock:
        per_dev = device_status.setdefault(device_id, {})
        per_dev.update(status)
    return jsonify({"ok": True})

# --- Frontend can query last known device statuses ---
@app.route('/api/status', methods=['GET'])
def api_get_status():
    device_id = request.args.get('device_id', DEFAULT_DEVICE_ID)
    with status_lock:
        return jsonify({"status": device_status.get(device_id, {})})

@app.route('/')
def index():
    # serve templates/main.html
    return render_template('main.html')

if __name__ == '__main__':
    # For local testing only:
    app.run(host='0.0.0.0', port=10000)
