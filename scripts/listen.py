#!/usr/bin/env python3
"""Escucha pasivamente 20s. Apreta el boton RESET (negro) mientras corre."""
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbmodem1303"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

print(f"== Abriendo {PORT} @ {BAUD} (sin tocar DTR/RTS) ==")
ser = serial.Serial()
ser.port = PORT
ser.baudrate = BAUD
ser.timeout = 0.05
ser.dtr = None
ser.rts = None
ser.open()
time.sleep(0.2)
ser.reset_input_buffer()

print("\n>>> APRETA EL BOTON NEGRO (RESET) AHORA <<<")
print("Escuchando 20 segundos. Cualquier byte que entre se muestra.\n")

t0 = time.time()
total = 0
last_report = t0
buf = b""
while time.time() - t0 < 20:
    if ser.in_waiting:
        chunk = ser.read(ser.in_waiting)
        buf += chunk
        total += len(chunk)
        # imprimir incrementalmente
        try:
            text = chunk.decode(errors="replace")
            sys.stdout.write(text)
            sys.stdout.flush()
        except Exception:
            print(chunk)
    now = time.time()
    if now - last_report >= 2.0:
        print(f"  [t={now-t0:4.1f}s  bytes={total}]")
        last_report = now
    time.sleep(0.01)

print(f"\n\n== Fin. Total bytes: {total} ==")
if buf:
    print(f"Raw (primeros 200): {buf[:200]!r}")
ser.close()
