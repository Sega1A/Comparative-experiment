"""
Muestrea CPU y RAM de los contenedores mientras corre el benchmark.

Se ejecuta EN PARALELO a bench.py, en otra terminal:

    Terminal A:  python medir_recursos.py --segundos 300
    Terminal B:  python bench.py

Genera resultados/recursos.csv con una fila por contenedor por segundo.
Esto cubre el indicador "consumo de recursos" que pide el enunciado.
"""

import argparse
import csv
import subprocess
import time
from datetime import datetime
from pathlib import Path

SALIDA = Path(__file__).resolve().parent.parent / "resultados" / "recursos.csv"

CONTENEDORES = ["t7-mosquitto", "t7-mqtt-echo", "t7-http", "t7-coap"]


def muestra():
    """Una foto de docker stats."""
    cmd = [
        "docker", "stats", "--no-stream",
        "--format", "{{.Name}};{{.CPUPerc}};{{.MemUsage}};{{.NetIO}}",
    ] + CONTENEDORES
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except Exception as e:
        print("Error llamando a docker stats:", e)
        return []

    filas = []
    ahora = datetime.now().isoformat(timespec="seconds")
    for linea in out.stdout.strip().splitlines():
        partes = linea.split(";")
        if len(partes) != 4:
            continue
        nombre, cpu, mem, net = partes
        filas.append({
            "timestamp": ahora,
            "contenedor": nombre,
            "cpu_pct": cpu.replace("%", "").strip(),
            "mem": mem.split("/")[0].strip(),
            "net_io": net.strip(),
        })
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segundos", type=int, default=300)
    ap.add_argument("--intervalo", type=float, default=1.0)
    args = ap.parse_args()

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not SALIDA.exists()

    with open(SALIDA, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "timestamp", "contenedor", "cpu_pct", "mem", "net_io"])
        if nuevo:
            w.writeheader()

        fin = time.time() + args.segundos
        print(f"Muestreando recursos por {args.segundos}s (Ctrl+C para cortar)...")
        try:
            while time.time() < fin:
                for fila in muestra():
                    w.writerow(fila)
                f.flush()
                time.sleep(args.intervalo)
        except KeyboardInterrupt:
            print("\nCortado por el usuario.")

    print(f"Guardado en {SALIDA}")


if __name__ == "__main__":
    main()
