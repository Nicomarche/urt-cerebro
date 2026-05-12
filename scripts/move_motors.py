#!/usr/bin/env python3
"""
Control manual de motores de la placa F401RE por USB.

Protocolo (serial 115200 8N1):
  #kl:30;;\r\n       -> habilita comandos de movimiento (estado "drive")
  #kl:0;;\r\n        -> apaga (estado idle)
  #speed:<int>;;\r\n -> referencia de velocidad
  #steer:<int>;;\r\n -> angulo de direccion en grados (negativo=izq, positivo=der)
  #brake:<int>;;\r\n -> freno con angulo de direccion

Controles teclado:
  w / s   acelerar / desacelerar (paso de SPEED_STEP)
  a / d   girar izquierda / derecha (paso de STEER_STEP)
  espacio frenar (speed=0, brake)
  x       centrar direccion (steer=0)
  r       resetear todo (speed=0, steer=0)
  q       salir (apaga kl)
"""

import argparse
import re
import sys
import termios
import time
import tty
from contextlib import contextmanager

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("Falta pyserial. Instalalo con: pip install pyserial")


BAUDRATE = 115200
SPEED_STEP = 50      # mm/s por pulsacion
STEER_STEP = 25      # decimas de grado por pulsacion (ajusta a gusto)
SPEED_LIMIT = 500
STEER_LIMIT = 250

# Mismo patron que Brain (processSerialHandler.py) pero adaptado a macOS.
# En la Pi: /dev/ttyACM\d+   En Mac: /dev/cu.usbmodem\d+
PORT_REGEX = r"/dev/cu\.usbmodem\d+"


def autodetect_port():
    """Replica la deteccion de Brain: primer puerto que matchee el regex."""
    return next(
        (p.device for p in list_ports.comports() if re.match(PORT_REGEX, p.device)),
        None,
    )


def send(ser, key, value):
    msg = f"#{key}:{value};;\r\n".encode()
    ser.write(msg)
    print(f"  -> {msg.decode().strip()}")


@contextmanager
def raw_terminal():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run_demo(ser):
    """Secuencia corta no-interactiva para probar motores."""
    print("\n=== DEMO ===")
    steps = [
        ("speed",  80, 1.0, "avanzar"),
        ("speed",   0, 0.3, "parar"),
        ("steer", -150, 0.8, "girar izq"),
        ("steer",  150, 0.8, "girar der"),
        ("steer",    0, 0.3, "centrar"),
        ("speed",  -80, 1.0, "retroceder"),
        ("speed",   0, 0.3, "parar"),
        ("brake",   0, 0.5, "freno"),
    ]
    for key, val, dur, desc in steps:
        print(f"[{desc}] ", end="", flush=True)
        send(ser, key, val)
        t0 = time.time()
        while time.time() - t0 < dur:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting).decode(errors="ignore")
                for line in data.splitlines():
                    if line.strip():
                        print(f"  <- {line.strip()}")
            time.sleep(0.02)


def main():
    ap = argparse.ArgumentParser(description="Control manual de motores F401RE")
    ap.add_argument("-p", "--port", help="Puerto serial (ej: /dev/tty.usbmodem...)")
    ap.add_argument("-b", "--baud", type=int, default=BAUDRATE)
    ap.add_argument("--demo", action="store_true",
                    help="Secuencia corta no-interactiva (no requiere teclado)")
    args = ap.parse_args()

    port = args.port or autodetect_port()
    if not port:
        print("No se detecto la placa. Puertos disponibles:")
        for p in list_ports.comports():
            print(f"  {p.device}  -  {p.description}")
        sys.exit("Usa -p /dev/tty.usbmodemXXXX")

    print(f"Abriendo {port} @ {args.baud}...")
    ser = serial.Serial(port, args.baud, timeout=0.1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    print("Habilitando kl:30 (motores activos)")
    send(ser, "kl", 30)
    time.sleep(0.1)

    speed = 0
    steer = 0

    if args.demo:
        try:
            run_demo(ser)
        finally:
            print("\nApagando motores...")
            send(ser, "speed", 0)
            send(ser, "steer", 0)
            time.sleep(0.05)
            send(ser, "kl", 0)
            time.sleep(0.1)
            ser.close()
            print("Cerrado.")
        return

    print(__doc__)
    print(f"\nEstado inicial: speed={speed}  steer={steer}\n")

    try:
        with raw_terminal():
            while True:
                ch = sys.stdin.read(1).lower()
                if ch == "q":
                    break
                elif ch == "w":
                    speed = min(speed + SPEED_STEP, SPEED_LIMIT)
                    send(ser, "speed", speed)
                elif ch == "s":
                    speed = max(speed - SPEED_STEP, -SPEED_LIMIT)
                    send(ser, "speed", speed)
                elif ch == "a":
                    steer = max(steer - STEER_STEP, -STEER_LIMIT)
                    send(ser, "steer", steer)
                elif ch == "d":
                    steer = min(steer + STEER_STEP, STEER_LIMIT)
                    send(ser, "steer", steer)
                elif ch == " ":
                    speed = 0
                    send(ser, "brake", steer)
                elif ch == "x":
                    steer = 0
                    send(ser, "steer", 0)
                elif ch == "r":
                    speed = 0
                    steer = 0
                    send(ser, "speed", 0)
                    send(ser, "steer", 0)

                # eco de respuestas que mande la placa
                if ser.in_waiting:
                    try:
                        data = ser.read(ser.in_waiting).decode(errors="ignore")
                        for line in data.splitlines():
                            if line.strip():
                                print(f"  <- {line.strip()}")
                    except Exception:
                        pass
    finally:
        print("\nApagando motores (speed=0, steer=0, kl:0)...")
        try:
            send(ser, "speed", 0)
            send(ser, "steer", 0)
            time.sleep(0.05)
            send(ser, "kl", 0)
            time.sleep(0.1)
        finally:
            ser.close()
        print("Cerrado.")


if __name__ == "__main__":
    main()
