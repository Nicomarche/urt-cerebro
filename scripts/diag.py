#!/usr/bin/env python3
"""Diagnostico de comunicacion con la placa F401RE."""
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbmodem1303"

print(f"== Abriendo {PORT} (sin tocar DTR/RTS) ==")
ser = serial.Serial()
ser.port = PORT
ser.baudrate = 115200
ser.timeout = 0.1
ser.dtr = None  # no manejar
ser.rts = None
ser.open()
time.sleep(0.3)

def listen(label, seconds):
    print(f"\n-- escuchando {seconds}s tras '{label}' --")
    t0 = time.time()
    buf = b""
    while time.time() - t0 < seconds:
        if ser.in_waiting:
            buf += ser.read(ser.in_waiting)
        time.sleep(0.02)
    if buf:
        for line in buf.decode(errors="ignore").splitlines():
            if line.strip():
                print(f"  <- {line.strip()}")
    else:
        print("  (silencio total)")

# 1) escuchar pasivamente — la placa publica @speed/@battery/@imu periodicamente si esta corriendo
listen("pasivo (deberia haber tickers)", 3.0)

# 2) ping con #alive
print("\n== TX #alive:1;; ==")
ser.write(b"#alive:1;;\r\n")
listen("alive", 1.0)

# 3) intentar habilitar motores y mover
print("\n== TX #kl:30;; ==")
ser.write(b"#kl:30;;\r\n")
listen("kl:30", 1.0)

print("\n== TX #speed:80;; ==")
ser.write(b"#speed:80;;\r\n")
listen("speed:80", 1.5)

print("\n== TX #steer:100;; ==")
ser.write(b"#steer:100;;\r\n")
listen("steer:100", 1.0)

print("\n== TX #speed:0;; + #steer:0;; + #kl:0;; ==")
ser.write(b"#speed:0;;\r\n")
ser.write(b"#steer:0;;\r\n")
ser.write(b"#kl:0;;\r\n")
listen("apagado", 1.0)

ser.close()
print("\n== fin ==")
