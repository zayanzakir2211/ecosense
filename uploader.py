import json
import time
import logging
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, db

# ── CONFIG ────────────────────────────────────────────────────────────────────
DATA_FILE       = Path("sensordata.json")
UPLOAD_INTERVAL = 3600  # seconds between each upload to Firebase (1 hour)

FIREBASE_CRED   = "serviceAccountKey.json"
FIREBASE_DB_URL = "https://greenplus-7a811-default-rtdb.asia-southeast1.firebasedatabase.app/"

# ── INIT ──────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

cred = credentials.Certificate(FIREBASE_CRED)
firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})

# ── MAIN ──────────────────────────────────────────────────────────────────────
while True:
    try:
        local = json.loads(DATA_FILE.read_text())

        # Loop through each sensor in the local file
        for sensor_id, sensor_data in local["sensors"].items():
            new_reading = sensor_data["readings"][0]  # the single latest reading

            ref = db.reference(f"/sensors/{sensor_id}")
            existing = ref.get()

            if existing is None:
                # First time — push entire sensor structure as-is
                ref.set(sensor_data)
                log.info(f"{sensor_id}: first upload, structure created")
            else:
                # Append new reading to existing readings list
                readings = existing.get("readings", [])
                readings.append(new_reading)
                ref.update({"readings": readings})
                log.info(f"{sensor_id}: reading appended → total {len(readings)} readings")

    except Exception as e:
        log.error(f"Upload failed: {e}")

    time.sleep(UPLOAD_INTERVAL)