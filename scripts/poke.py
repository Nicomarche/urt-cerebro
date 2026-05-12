#!/usr/bin/env python3
"""Probar tty vs cu, varios bauds, mandando comandos mientras escucha."""
import sys
import time
import serial

DEVICES = ["/dev/cu.usbmodem1303", "/dev/tty.usbmodem1303"]
BAUDS = [115200, 19200, 9600, 460800, 230400]
PROBES = [
    b"#alive:1;;\r\n",
    b"#kl:30;;\r\n",
    b"#kl:15;;\r\n",
    b"\r\n",
    b"?\r\n",
    b"AT\r\n",
]

def trial(dev, baud):
    print(f"\n=== {dev} @ {baud} ===")
    try:
        ser = serial.Serial()
        ser.port = dev
        ser.baudrate = baud
        ser.timeout = 0.05
        ser.dtr = True
        ser.rts = True
        ser.open()
    except Exception as e:
        print(f"  open ERROR: {e}")
        return
    time.sleep(0.2)
    ser.reset_input_buffer()

    total = 0
    buf = b""

    def drain(label, t=0.8):
        nonlocal total, buf
        t0 = time.time()
        chunk_all = b""
        while time.time() - t0 < t:
            if ser.in_waiting:
                c = ser.read(ser.in_waiting)
                chunk_all += c
                buf += c
                total += len(c)
            time.sleep(0.01)
        if chunk_all:
            try:
                txt = chunk_all.decode(errors="replace")
                print(f"  [{label}] +{len(chunk_all)}B  {txt.strip()[:120]!r}")
            except Exception:
                print(f"  [{label}] +{len(chunk_all)}B  raw={chunk_all[:60]!r}")

    drain("pasivo", 1.0)
    for p in PROBES:
        try:
            ser.write(p)
            ser.flush()
        except Exception as e:
            print(f"  write ERROR {p!r}: {e}")
            break
        drain(f"tras {p!r}", 0.6)

    print(f"  TOTAL bytes: {total}")
    ser.close()

for dev in DEVICES:
    for b in BAUDS:
        trial(dev, b)

print("\n== fin ==")
