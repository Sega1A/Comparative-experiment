"""
=============================================================
BANCO DE PRUEBAS - Trabajo 7
Comparacion experimental de MQTT, CoAP y HTTP en escenarios IoT
=============================================================

Que hace este script:
  Manda el MISMO mensaje N veces por cada protocolo y cronometra
  cuanto tarda en ir y volver (round-trip time, RTT).
  Guarda cada medicion individual en resultados/resultados.csv

Por que se mide round-trip y no solo el envio:
  Es la unica forma de comparar peras con peras. HTTP y CoAP son
  peticion/respuesta por naturaleza; a MQTT le agregamos un servicio
  de eco para que tambien devuelva algo. Los tres hacen el mismo
  trabajo util: entregar un payload y confirmar que llego.

Variables independientes (lo que cambiamos):
  - protocolo: http, http-noka, coap, mqtt-qos0, mqtt-qos1, mqtt-qos2
  - tamano del payload: 16, 64, 256, 1024 bytes

Variable dependiente (lo que medimos):
  - rtt_ms

Uso:
    python bench.py                      # corrida completa por defecto
    python bench.py --n 500              # 500 mediciones por combinacion
    python bench.py --protocolos coap mqtt-qos1
"""

import argparse
import asyncio
import csv
import os
import socket
import statistics
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
import paho.mqtt.client as mqtt


def _hay_ipv6() -> bool:
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.close()
        return True
    except OSError:
        return False


# aiocoap usa por defecto el transporte udp6, que necesita IPv6.
# Si el sistema no lo tiene, cambiamos a "simple6" (cliente sobre IPv4).
if not _hay_ipv6():
    os.environ.setdefault("AIOCOAP_CLIENT_TRANSPORT", "simple6")

import aiocoap  # noqa: E402

# ------------------------------------------------------------------
# Configuracion (se puede sobrescribir con variables de entorno)
# ------------------------------------------------------------------
HOST = os.getenv("BENCH_HOST", "127.0.0.1")
HTTP_URL = f"http://{HOST}:8000/data"
COAP_URL = f"coap://{HOST}:5683/data"
MQTT_HOST = HOST
MQTT_PORT = 1883
TOPIC_REQ = "bench/req"
TOPIC_RESP = "bench/resp"

TAMANOS_DEFAULT = [16, 64, 256, 1024]
PROTOCOLOS_DEFAULT = [
    "http",        # HTTP/1.1 con keep-alive (conexion reutilizada)
    "http-noka",   # HTTP/1.1 abriendo conexion nueva cada vez
    "coap",        # CoAP confirmable sobre UDP
    "mqtt-qos0",   # MQTT "fire and forget"
    "mqtt-qos1",   # MQTT "al menos una vez"
    "mqtt-qos2",   # MQTT "exactamente una vez"
]

SALIDA = Path(__file__).resolve().parent.parent / "resultados" / "resultados.csv"


def hacer_payload(seq: int, tamano: int) -> bytes:
    """Payload de tamano exacto, con un numero de secuencia al inicio.

    Los primeros 8 bytes son el ID de la medicion (sirve para correlacionar
    peticion y respuesta en MQTT). El resto es relleno.
    """
    cabecera = f"{seq:08d}".encode()
    if tamano <= len(cabecera):
        return cabecera[:tamano]
    return cabecera + b"x" * (tamano - len(cabecera))


# ==================================================================
# HTTP
# ==================================================================
def medir_http(n: int, tamano: int, keepalive: bool = True):
    """Mide RTT de HTTP/1.1. POST al recurso /data."""
    rtts = []
    sesion = requests.Session()
    # Ignorar HTTP_PROXY/HTTPS_PROXY del sistema: un proxy intermedio
    # falsearia por completo la medicion de latencia.
    sesion.trust_env = False
    headers = {"Content-Type": "application/octet-stream"}
    if not keepalive:
        headers["Connection"] = "close"

    # Calentamiento: las primeras peticiones siempre salen lentas
    for i in range(5):
        sesion.post(HTTP_URL, data=hacer_payload(i, tamano), headers=headers)

    for i in range(n):
        payload = hacer_payload(i, tamano)
        t0 = time.perf_counter()
        r = sesion.post(HTTP_URL, data=payload, headers=headers, timeout=10)
        t1 = time.perf_counter()
        if r.status_code == 200:
            rtts.append((t1 - t0) * 1000)

    sesion.close()
    return rtts


# ==================================================================
# CoAP
# ==================================================================
async def _medir_coap_async(n: int, tamano: int):
    rtts = []
    contexto = await aiocoap.Context.create_client_context()

    async def una_peticion(i):
        msg = aiocoap.Message(
            code=aiocoap.numbers.codes.Code.POST,
            payload=hacer_payload(i, tamano),
            uri=COAP_URL,
        )
        msg.mtype = aiocoap.CON  # confirmable: exige ACK, comparable a HTTP
        return await contexto.request(msg).response

    for i in range(5):  # calentamiento
        await una_peticion(i)

    for i in range(n):
        t0 = time.perf_counter()
        try:
            await una_peticion(i)
            t1 = time.perf_counter()
            rtts.append((t1 - t0) * 1000)
        except Exception as e:  # timeouts de UDP: se cuentan como perdida
            print(f"    [coap] fallo en iteracion {i}: {e}", file=sys.stderr)

    await contexto.shutdown()
    return rtts


def medir_coap(n: int, tamano: int):
    return asyncio.run(_medir_coap_async(n, tamano))


# ==================================================================
# MQTT
# ==================================================================
def medir_mqtt(n: int, tamano: int, qos: int):
    """Mide RTT de MQTT: publish en bench/req -> eco en bench/resp."""
    rtts = []
    respuesta = threading.Event()
    esperando = {"seq": -1}

    def on_message(client, userdata, msg):
        # Los primeros 8 bytes traen el numero de secuencia
        try:
            seq = int(msg.payload[:8])
        except ValueError:
            return
        if seq == esperando["seq"]:
            respuesta.set()

    def on_socket_open(client, userdata, sock):
        # Desactiva Nagle en el cliente: mismo motivo que en el broker.
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    cliente = mqtt.Client(client_id=f"t7-bench-{qos}-{tamano}", clean_session=True)
    cliente.on_socket_open = on_socket_open
    cliente.on_message = on_message
    cliente.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    cliente.subscribe(TOPIC_RESP, qos=qos)
    cliente.loop_start()
    time.sleep(0.5)  # dar tiempo a que la suscripcion se confirme

    def un_envio(seq):
        esperando["seq"] = seq
        respuesta.clear()
        cliente.publish(TOPIC_REQ, payload=hacer_payload(seq, tamano), qos=qos)
        return respuesta.wait(timeout=5)

    for i in range(5):  # calentamiento
        un_envio(i)

    for i in range(n):
        t0 = time.perf_counter()
        ok = un_envio(i)
        t1 = time.perf_counter()
        if ok:
            rtts.append((t1 - t0) * 1000)
        else:
            print(f"    [mqtt-qos{qos}] timeout en iteracion {i}", file=sys.stderr)

    cliente.loop_stop()
    cliente.disconnect()
    return rtts


# ==================================================================
# Orquestador
# ==================================================================
EJECUTORES = {
    "http":      lambda n, t: medir_http(n, t, keepalive=True),
    "http-noka": lambda n, t: medir_http(n, t, keepalive=False),
    "coap":      lambda n, t: medir_coap(n, t),
    "mqtt-qos0": lambda n, t: medir_mqtt(n, t, 0),
    "mqtt-qos1": lambda n, t: medir_mqtt(n, t, 1),
    "mqtt-qos2": lambda n, t: medir_mqtt(n, t, 2),
}


def main():
    ap = argparse.ArgumentParser(description="Banco de pruebas MQTT vs CoAP vs HTTP")
    ap.add_argument("--n", type=int, default=200,
                    help="mediciones por combinacion (default 200)")
    ap.add_argument("--tamanos", type=int, nargs="+", default=TAMANOS_DEFAULT,
                    help="tamanos de payload en bytes")
    ap.add_argument("--protocolos", nargs="+", default=PROTOCOLOS_DEFAULT,
                    choices=list(EJECUTORES.keys()))
    ap.add_argument("--etiqueta", default="corrida1",
                    help="nombre de la corrida (para comparar escenarios)")
    args = ap.parse_args()

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    archivo_nuevo = not SALIDA.exists()

    filas = []
    print(f"\n{'='*60}")
    print(f"Banco de pruebas | n={args.n} | etiqueta={args.etiqueta}")
    print(f"{'='*60}\n")

    for proto in args.protocolos:
        for tamano in args.tamanos:
            print(f"  -> {proto:<10} payload={tamano:>5} B ... ", end="", flush=True)
            t_inicio = time.time()
            rtts = EJECUTORES[proto](args.n, tamano)
            duracion = time.time() - t_inicio

            if not rtts:
                print("SIN DATOS")
                continue

            for i, rtt in enumerate(rtts):
                filas.append({
                    "etiqueta": args.etiqueta,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "protocolo": proto,
                    "payload_bytes": tamano,
                    "iteracion": i,
                    "rtt_ms": round(rtt, 4),
                })

            exitosas = len(rtts)
            perdidas = 100 * (args.n - exitosas) / args.n
            print(f"media={statistics.mean(rtts):7.2f} ms  "
                  f"p95={sorted(rtts)[int(0.95*exitosas)-1]:7.2f} ms  "
                  f"perdida={perdidas:4.1f}%  "
                  f"({duracion:.1f}s)")

    with open(SALIDA, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "etiqueta", "timestamp", "protocolo",
            "payload_bytes", "iteracion", "rtt_ms",
        ])
        if archivo_nuevo:
            w.writeheader()
        w.writerows(filas)

    print(f"\n{len(filas)} mediciones guardadas en {SALIDA}")
    print("Siguiente paso: python analizar.py\n")


if __name__ == "__main__":
    main()
