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
  o       resetear contador de odometria
  j / k   debug calib servo: PWM crudo -25 / +25 us
  , / .   debug calib servo: PWM crudo -5 / +5 us (fino)
  5       debug calib servo: PWM crudo = 1500 us (centro)
  q       salir (apaga kl)
"""

import argparse
import re
import sys
import termios
import threading
import time
import tty
from contextlib import contextmanager

try:
    import serial
    from serial.tools import list_ports
except ImportError as e:
    print(f"[debug] python ejecutable: {sys.executable}")
    print(f"[debug] sys.path:")
    for p in sys.path:
        print(f"    {p}")
    print(f"[debug] ImportError: {e!r}")
    sys.exit("Falta pyserial. Instalalo con: " + sys.executable + " -m pip install pyserial")


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


def reader_loop(ser, stop_event):
    """Hilo de fondo: imprime @speed + @hallraw cada ~250 ms y el resto tal cual."""
    print("[reader] iniciado", flush=True)
    buf = b""
    latest_speed = None
    latest_odo = None
    latest_hallraw = None
    last_print = 0.0
    total_bytes = 0
    last_diag = time.time()
    while not stop_event.is_set():
        try:
            chunk = ser.read(4096)
        except Exception as e:
            print(f"[reader] excepcion en read: {e!r}", flush=True)
            break
        if chunk:
            total_bytes += len(chunk)
            buf += chunk
            while b"\n" in buf:
                line_bytes, _, buf = buf.partition(b"\n")
                line = line_bytes.decode(errors="ignore").strip()
                if not line:
                    continue
                if line.startswith("@speed:"):
                    try:
                        latest_speed = int(line.split(":", 1)[1].split(";", 1)[0])
                    except Exception:
                        pass
                elif line.startswith("@odo:"):
                    try:
                        latest_odo = int(line.split(":", 1)[1].split(";", 1)[0])
                    except Exception:
                        pass
                elif line.startswith("@hallraw:"):
                    latest_hallraw = line.split(":", 1)[1].rstrip(";")
                else:
                    print(f"  <- {line}", flush=True)
        now = time.time()
        if latest_speed is not None and now - last_print >= 0.25:
            odo_str = f"  odo={latest_odo}mm" if latest_odo is not None else ""
            extra = f"  raw[min;max;pulses]={latest_hallraw}" if latest_hallraw else ""
            print(f"  <- @speed: {latest_speed} mm/s{odo_str}{extra}", flush=True)
            last_print = now
        if now - last_diag >= 2.0:
            print(f"[reader] diag: {total_bytes} bytes leidos en ult. 2s, buf={len(buf)}B, latest_speed={latest_speed}", flush=True)
            total_bytes = 0
            last_diag = now
    print("[reader] terminado", flush=True)


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
    pwm_us = 1500  # estado para calibracion de servo (#steerpwm)

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

    stop_event = threading.Event()
    reader = threading.Thread(target=reader_loop, args=(ser, stop_event), daemon=True)
    reader.start()

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
                elif ch == "o":
                    send(ser, "odoreset", 1)
                elif ch == "j":
                    pwm_us = max(500, pwm_us - 25)
                    send(ser, "steerpwm", pwm_us)
                elif ch == "k":
                    pwm_us = min(2500, pwm_us + 25)
                    send(ser, "steerpwm", pwm_us)
                elif ch == ",":
                    pwm_us = max(500, pwm_us - 5)
                    send(ser, "steerpwm", pwm_us)
                elif ch == ".":
                    pwm_us = min(2500, pwm_us + 5)
                    send(ser, "steerpwm", pwm_us)
                elif ch == "5":
                    pwm_us = 1500
                    send(ser, "steerpwm", pwm_us)
    finally:
        stop_event.set()
        reader.join(timeout=0.5)
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
