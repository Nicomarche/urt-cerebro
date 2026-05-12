#!/usr/bin/env python3
"""Listen on VCP while resetting MCU via SWD."""
import subprocess, time, serial, threading, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbmodem11303"

print(f"Abriendo {PORT}@115200...")
ser = serial.Serial()
ser.port = PORT
ser.baudrate = 115200
ser.timeout = 0.05
ser.dtr = None
ser.rts = None
ser.open()
time.sleep(0.3)
ser.reset_input_buffer()

stop = False
total = 0
def reader():
    global total
    while not stop:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            total += len(chunk)
            sys.stdout.write(chunk.decode(errors="replace"))
            sys.stdout.flush()
        time.sleep(0.01)

t = threading.Thread(target=reader, daemon=True)
t.start()

print("Escuchando 2s antes del reset...")
time.sleep(2)
print(f"\n[bytes pre-reset: {total}]")

print("Reseteando MCU vía SWD...")
r = subprocess.run(["pyocd", "reset", "-t", "stm32f401re"],
                   capture_output=True, text=True, timeout=30)
print(r.stdout[-500:] if r.stdout else "")
print(r.stderr[-500:] if r.stderr else "")
print(f"\n[bytes post-reset cmd: {total}]")

print("Escuchando 8s post-reset...")
time.sleep(8)
stop = True
time.sleep(0.2)
print(f"\n\n=== TOTAL: {total} bytes ===")
ser.close()
