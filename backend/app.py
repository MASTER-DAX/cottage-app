# backend/app.py
from flask import Flask, jsonify, request, Response, render_template
from flask_cors import CORS
import threading

app = Flask(__name__)
CORS(app)

# In-memory command queues: device_id -> list of command chars
command_queues = {}
queues_lock = threading.Lock()

# Last status reported by each device
device_status = {}
status_lock = threading.Lock()

# Map frontend action -> single-char command for Arduino (matches ESP32->Mega mapping)
CMD_MAP = {
    ("fan", "on"):  "1",
    ("fan", "off"): "2",
    ("light", "on"):  "3",
    ("light", "off"): "4",
    ("purifier", "on"): "5",
    ("purifier", "off"): "6",
    ("door", "unlock"): "7",
    ("door", "lock"):   "8"
}

DEFAULT_DEVICE_ID = "esp32_1"

def queue_command(device_id: str, cmd_char: str):
    with queues_lock:
        q = command_queues.setdefault(device_id, [])
        q.append(cmd_char)

# --- Compatibility endpoints (use same names your frontend expects) ---
@app.route('/fan', methods=['POST'])
def fan_control():
    data = request.json or {}
    action = (data.get('action') or "").lower()
    device_id = data.get('device_id', DEFAULT_DEVICE_ID)
    key = ("fan", action)
    if key not in CMD_MAP:
        return jsonify({"error": "invalid action"}), 400
    queue_command(device_id, CMD_MAP[key])
    return jsonify({"queued": CMD_MAP[key]})

@app.route('/light', methods=['POST'])
def light_control():
    data = request.json or {}
    action = (data.get('action') or "").lower()
    device_id = data.get('device_id', DEFAULT_DEVICE_ID)
    key = ("light", action)
    if key not in CMD_MAP:
        return jsonify({"error": "invalid action"}), 400
    queue_command(device_id, CMD_MAP[key])
    return jsonify({"queued": CMD_MAP[key]})

@app.route('/purifier', methods=['POST'])
def purifier_control():
    data = request.json or {}
    action = (data.get('action') or "").lower()
    device_id = data.get('device_id', DEFAULT_DEVICE_ID)
    key = ("purifier", action)
    if key not in CMD_MAP:
        return jsonify({"error": "invalid action"}), 400
    queue_command(device_id, CMD_MAP[key])
    return jsonify({"queued": CMD_MAP[key]})

@app.route('/door', methods=['POST'])
def door_control():
    data = request.json or {}
    action = (data.get('action') or "").lower()
    device_id = data.get('device_id', DEFAULT_DEVICE_ID)
    key = ("door", action)
    if key not in CMD_MAP:
        return jsonify({"error": "invalid action"}), 400
    queue_command(device_id, CMD_MAP[key])
    return jsonify({"queued": CMD_MAP[key]})

# --- General send command (optional) ---
@app.route('/api/send_command', methods=['POST'])
def api_send_command():
    data = request.json or {}
    device_id = data.get('device_id', DEFAULT_DEVICE_ID)
    device = data.get('device')
    action = data.get('action')
    key = (device, action)
    if key not in CMD_MAP:
        return jsonify({"error": "invalid command"}), 400
    queue_command(device_id, CMD_MAP[key])
    return jsonify({"queued": CMD_MAP[key]})

# --- Poll endpoint used by ESP32: returns a single char (text/plain) or empty body ---
@app.route('/api/poll', methods=['GET'])
def api_poll():
    device_id = request.args.get('device_id', DEFAULT_DEVICE_ID)
    with queues_lock:
        q = command_queues.get(device_id, [])
        if q:
            cmd = q.pop(0)
            return Response(cmd, mimetype='text/plain')
    return Response('', mimetype='text/plain')

# --- Device posts statuses here after executing a command ---
@app.route('/api/status', methods=['POST'])
def api_status():
    data = request.json or {}
    device_id = data.get('device_id', DEFAULT_DEVICE_ID)
    status = data.get('status', '')
    with status_lock:
        device_status[device_id] = status
    return jsonify({"ok": True})

# --- Frontend can query last known device status ---
@app.route('/api/status', methods=['GET'])
def api_get_status():
    device_id = request.args.get('device_id', DEFAULT_DEVICE_ID)
    with status_lock:
        return jsonify({"status": device_status.get(device_id, "")})

@app.route('/')
def index():
    # ✅ Load your HTML dashboard
    return render_template('main.html')
    
if __name__ == '__main__':
    # For local testing only: run with python app.py
    app.run(host='0.0.0.0', port=10000)
