#!/usr/bin/env python3
"""Escanea baud rates y flow control para detectar la voz del firmware."""
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbmodem1303"

BAUDS = [9600, 19200, 38400, 57600, 115200, 230400, 256000, 460800, 921600]

def try_baud(baud, dtr=None, rts=None, listen_s=2.0, label=""):
    print(f"\n--- {baud} baud  dtr={dtr} rts={rts}  {label} ---")
    try:
        ser = serial.Serial()
        ser.port = PORT
        ser.baudrate = baud
        ser.timeout = 0.1
        if dtr is not None:
            ser.dtr = dtr
        if rts is not None:
            ser.rts = rts
        ser.open()
        time.sleep(0.2)
        ser.reset_input_buffer()
        t0 = time.time()
        buf = b""
        while time.time() - t0 < listen_s:
            if ser.in_waiting:
                buf += ser.read(ser.in_waiting)
            time.sleep(0.02)
        ser.close()
        if buf:
            printable = sum(1 for c in buf if 32 <= c < 127 or c in (9, 10, 13))
            ratio = printable / len(buf) if buf else 0
            print(f"  {len(buf)} bytes recibidos  printable={ratio:.0%}")
            print(f"  raw: {buf[:120]!r}")
            try:
                decoded = buf.decode(errors='replace')
                for line in decoded.splitlines()[:5]:
                    if line.strip():
                        print(f"  decoded: {line.strip()[:100]}")
            except Exception:
                pass
        else:
            print("  silencio")
    except Exception as e:
        print(f"  ERROR: {e}")

# Escucha pasiva en distintos bauds
for b in BAUDS:
    try_baud(b, dtr=None, rts=None, listen_s=2.0)

# Asegurar DTR/RTS asertados explicitamente a 115200
try_baud(115200, dtr=True, rts=True, listen_s=2.0, label="DTR=1 RTS=1")
try_baud(115200, dtr=False, rts=False, listen_s=2.0, label="DTR=0 RTS=0")

print("\n== fin ==")
