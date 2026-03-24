import os
from pymongo import MongoClient

# ===============================
# CONNECT TO MONGODB
# ===============================
MONGO_URI = "mongodb+srv://daxdeniega16:136541ASAka@cluster0.u2nctpk.mongodb.net/"
client = MongoClient(MONGO_URI)

db = client["smart_cottage"]
devices = db["devices"]

# ===============================
# DEFAULT DEVICE STATUS
# ===============================
DEFAULT_STATUS = {
    "front_light": "OFF",
    "bed_light": "OFF",
    "front_fan": "OFF",
    "bed_fan": "OFF",
    "purifier": "OFF",
    "privacy_lights": "OFF",
    "front_door": "LOCKED",
    "bed_door": "LOCKED"
}


# ===============================
# CREATE DEVICE IF NOT EXISTS
# ===============================
def ensure_device(device_id):

    existing = devices.find_one({"device_id": device_id})

    if not existing:
        devices.insert_one({
            "device_id": device_id,
            "status": DEFAULT_STATUS.copy()
        })


# ===============================
# UPDATE SINGLE DEVICE
# ===============================
def update_device_status(device_id, device, state):

    ensure_device(device_id)

    devices.update_one(
        {"device_id": device_id},
        {"$set": {f"status.{device}": state}}
    )


# ===============================
# UPDATE MANY DEVICES
# ===============================
def update_many_status(device_id, status_dict):

    ensure_device(device_id)

    update_data = {}

    for device, state in status_dict.items():
        update_data[f"status.{device}"] = state

    devices.update_one(
        {"device_id": device_id},
        {"$set": update_data}
    )


# ===============================
# GET STATUS
# ===============================
def get_device_status(device_id):

    ensure_device(device_id)

    device = devices.find_one({"device_id": device_id})

    if not device:
        return DEFAULT_STATUS

    return device.get("status", DEFAULT_STATUS)
