#!/usr/bin/env python3
"""Bombardeo de prueba: abre/cierra, manda mucho, en muchos bauds."""
import sys, time, serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbmodem11303"

KEYS = ["alive", "kl", "speed", "steer", "brake", "vcd", "battery",
        "instant", "imu", "hallspeed", "resourceMonitor", "batteryCapacity"]
BAUDS = [115200, 19200, 9600, 460800, 38400]

def open_close_cycle(dev, baud, iterations=3):
    """A veces el primer open no 'desperta' el endpoint; reintentamos."""
    received = b""
    for i in range(iterations):
        try:
            ser = serial.Serial(dev, baud, timeout=0.05)
        except Exception as e:
            print(f"  iter {i} open ERROR: {e}")
            time.sleep(0.3)
            continue
        time.sleep(0.15)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        # mandar cada key
        for k in KEYS:
            for val in ("1", "0", "30"):
                ser.write(f"#{k}:{val};;\r\n".encode())
                ser.flush()
                time.sleep(0.05)
                if ser.in_waiting:
                    received += ser.read(ser.in_waiting)
        # final drain
        t0 = time.time()
        while time.time() - t0 < 0.5:
            if ser.in_waiting:
                received += ser.read(ser.in_waiting)
            time.sleep(0.02)
        ser.close()
        time.sleep(0.2)
    return received

for baud in BAUDS:
    print(f"\n=== {baud} ===")
    rx = open_close_cycle(PORT, baud)
    print(f"  total bytes: {len(rx)}")
    if rx:
        print(f"  RAW: {rx[:200]!r}")
        for line in rx.decode(errors='replace').splitlines()[:5]:
            if line.strip():
                print(f"  >> {line.strip()[:120]}")

print("\n== fin ==")
