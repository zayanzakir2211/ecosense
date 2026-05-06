"""
datawriter.py
────────────────
Reads from: MH-Z19B (CO2), BME280 (temp+humidity), PMS5003 (PM2.5), Sound sensor
Rewrites:   sensordata.json → sensors.sensor_01.readings[0]
Every:      READ_INTERVAL seconds

The uploader.py script handles pushing to Firebase separately.
"""

import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
DATA_FILE     = Path("sensordata.json")
READ_INTERVAL = 30  # seconds between each sensor read

# ── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

# ── SENSOR READERS ────────────────────────────────────────────────────────────

def read_co2() -> int:
    """MH-Z19B via UART serial."""
    import serial
    ser = serial.Serial('/dev/ttyAMA0', baudrate=9600, timeout=1)
    ser.write(b'\xff\x01\x86\x00\x00\x00\x00\x00\x79')
    resp = ser.read(9)
    ser.close()
    if len(resp) < 9 or resp[0] != 0xFF:
        raise ValueError("Bad response from MH-Z19B")
    return (resp[2] << 8) | resp[3]


def read_bme280():
    """BME280 via I2C — returns (temperature_celsius, humidity_percent)."""
    import smbus2
    import bme280
    port   = 1
    address = 0x76  # change to 0x77 if sensor doesn't respond
    bus    = smbus2.SMBus(port)
    calibration_params = bme280.load_calibration_params(bus, address)
    data   = bme280.sample(bus, address, calibration_params)
    return round(data.temperature, 1), round(data.humidity, 1)


def read_pm25() -> float:
    """PMS5003 via UART serial — returns PM2.5 µg/m³."""
    from pms5003 import PMS5003
    pms  = PMS5003()
    data = pms.read()
    return float(data.pm_ug_per_m3(2.5))


def read_sound() -> int:
    """
    Sound sensor via MCP3008 ADC on SPI.
    Returns a 0–100 scaled value (adjust mapping to match your sensor).
    """
    import busio
    import digitalio
    import board
    import adafruit_mcp3xxx.mcp3008 as MCP
    from adafruit_mcp3xxx.analog_in import AnalogIn

    spi  = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
    cs   = digitalio.DigitalInOut(board.D5)   # change pin if needed
    mcp  = MCP.MCP3008(spi, cs)
    chan = AnalogIn(mcp, MCP.P0)              # change channel if needed
    return int(chan.value / 65535 * 100)


# ── FILE REWRITER ─────────────────────────────────────────────────────────────

def rewrite_json(reading: dict):
    """Load sensordata.json, replace readings[0], save back."""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    # Overwrite readings with just the single latest reading
    data["sensors"]["sensor_01"]["readings"] = [reading]
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

# ── MAIN LOOP ─────────────────────────────────────────────────────────────────

def main():
    log.info("=== Sensor Reader Started ===")

    while True:
        try:
            co2         = read_co2()
            temp, hum   = read_bme280()
            pm25        = read_pm25()
            sound       = read_sound()

            reading = {
                "timestamp":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "pm25":        round(pm25, 1),
                "co2":         co2,
                "temperature": temp,
                "humidity":    hum,    # BME280 gives humidity for free, keeping it
                "sound":       sound,
            }

            rewrite_json(reading)
            log.info(
                f"sensordata.json updated → "
                f"CO2={co2}ppm  PM2.5={pm25}µg  "
                f"Temp={temp}°C  Hum={hum}%  Sound={sound}"
            )

        except Exception as e:
            log.error(f"Sensor read failed: {e}")

        time.sleep(READ_INTERVAL)


if __name__ == "__main__":
    main()