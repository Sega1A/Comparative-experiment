"""Dispositivo: ESP32 + MPU6050 emulado. Detecta una caida simulada y envia la
misma alerta por HTTP, MQTT y CoAP bajo cada escenario de red."""
import asyncio
import http.client
import json
import os
import random
import socket
import sys
import threading
import time
import uuid

# Transporte UDP IPv4 simple: no depende de que el contenedor tenga IPv6.
os.environ.setdefault("AIOCOAP_CLIENT_TRANSPORT", "simple6")

import aiocoap
import paho.mqtt.client as mqtt

import comun

N_ALERTAS = int(os.environ.get("N_ALERTAS", 30))
TIEMPO_MAX = float(os.environ.get("TIEMPO_MAX", 30))
PAUSA = float(os.environ.get("PAUSA", 0.2))
PERSISTENTE = os.environ.get("CONEXION", "nueva") == "persistente"
MQTT_QOS = int(os.environ.get("MQTT_QOS", 1))
COAP_CON = os.environ.get("COAP_TIPO", "CON") != "NON"
COAP_TIPO = aiocoap.Reliable if COAP_CON else aiocoap.Unreliable
ESCENARIOS = os.environ.get("ESCENARIOS", "/config/escenarios.json")
HOST = {"http": os.environ.get("HOST_HTTP", "servidor-http"),
        "mqtt": os.environ.get("HOST_MQTT", "broker"),
        "coap": os.environ.get("HOST_COAP", "servidor-coap")}
PUERTO = {"http": int(os.environ.get("PUERTO_HTTP", 5000)),
          "mqtt": int(os.environ.get("PUERTO_MQTT", 1883)),
          "coap": int(os.environ.get("PUERTO_COAP", 5683))}
SERVICIO = {"http": "servidor-http", "mqtt": "broker", "coap": "servidor-coap"}
TEMA = "alertas/caidas"
IP = {}
estado = {"http": None, "mqtt": None, "coap": None}   # conexiones reutilizables


# ----------------------- sensor MPU6050 emulado -----------------------

def leer_acelerometro_caida():
    """Magnitud de aceleracion (g) a 50 Hz: reposo, caida libre, impacto, inmovil."""
    reposo = [random.gauss(1.0, 0.05) for _ in range(25)]
    caida_libre = [random.uniform(0.1, 0.4) for _ in range(15)]
    impacto = [random.uniform(2.5, 6.0)]
    inmovil = [random.gauss(1.0, 0.02) for _ in range(50)]
    return reposo + caida_libre + impacto + inmovil


def detectar_caida(muestras, umbral_libre=0.5, umbral_impacto=2.5):
    """Umbrales de Bourke et al. (2007): caida libre seguida de un pico de impacto."""
    hubo_caida_libre = False
    for g in muestras:
        if g < umbral_libre:
            hubo_caida_libre = True
        elif hubo_caida_libre and g > umbral_impacto:
            return round(g, 2)
    return None


# ----------------------------- protocolos -----------------------------

def enviar_http(cuerpo):
    limite = time.monotonic() + TIEMPO_MAX
    con = estado["http"] if PERSISTENTE else None
    try:
        if con is None:
            con = http.client.HTTPConnection(IP["http"], PUERTO["http"], timeout=TIEMPO_MAX)
        if con.sock is None:
            con.connect()
        con.sock.settimeout(max(0.1, limite - time.monotonic()))
        con.request("POST", "/alerta", body=cuerpo,
                    headers={"Content-Type": "application/json"})
        respuesta = con.getresponse()
        respuesta.read()
        estado["http"] = con if PERSISTENTE else None
        return respuesta.status == 200
    except Exception:
        estado["http"] = None
        raise
    finally:
        if estado["http"] is None and con is not None:
            con.close()


def conectar_mqtt(limite):
    conectado = threading.Event()
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                    client_id="esp32-sim-" + uuid.uuid4().hex[:6])
    c.on_connect = lambda *a: conectado.set()
    c.connect_timeout = TIEMPO_MAX
    c.connect(IP["mqtt"], PUERTO["mqtt"], keepalive=60)
    c.loop_start()
    if not conectado.wait(max(0.1, limite - time.monotonic())):
        cerrar_mqtt(c)
        raise TimeoutError("sin CONNACK")
    return c


def cerrar_mqtt(c):
    try:
        c.disconnect()
    finally:
        c.loop_stop()


def enviar_mqtt(cuerpo):
    limite = time.monotonic() + TIEMPO_MAX
    c = estado["mqtt"] if PERSISTENTE else None
    if c is None:
        c = conectar_mqtt(limite)
    try:
        info = c.publish(TEMA, cuerpo, qos=MQTT_QOS)
        info.wait_for_publish(timeout=max(0.1, limite - time.monotonic()))
        ok = info.is_published()   # con QoS 1/2 = el broker confirmo (PUBACK/PUBCOMP)
    except Exception:
        ok = False
    if PERSISTENTE and ok:
        estado["mqtt"] = c
    else:
        estado["mqtt"] = None
        cerrar_mqtt(c)
    if not ok:
        raise TimeoutError("sin confirmacion del broker")
    return True


async def enviar_coap(cuerpo):
    mensaje = aiocoap.Message(code=aiocoap.POST, transport_tuning=COAP_TIPO, payload=cuerpo,
                              uri=f"coap://{IP['coap']}:{PUERTO['coap']}/alerta",
                              content_format=50)   # application/json
    respuesta = await asyncio.wait_for(estado["coap"].request(mensaje).response, TIEMPO_MAX)
    return respuesta.code.is_successful()


# ------------------------------ medicion ------------------------------

def bytes_interfaz():
    """Bytes que realmente salieron/entraron por la interfaz (incluye cabeceras
    Ethernet/IP/TCP/UDP, establecimiento de conexion, ACK y retransmisiones)."""
    try:
        base = f"/sys/class/net/{comun.INTERFAZ}/statistics/"
        with open(base + "tx_bytes") as tx, open(base + "rx_bytes") as rx:
            return int(tx.read()), int(rx.read())
    except OSError:
        return 0, 0


async def enviar_alerta(corrida, escenario, netem, protocolo, n, acc_g):
    alerta = {"id": uuid.uuid4().hex[:12], "dispositivo": "esp32-sim-01",
              "evento": "caida", "acc_g": acc_g, "inmovil_s": 10,
              "t_envio_ns": time.time_ns()}
    cuerpo = json.dumps(alerta, separators=(",", ":")).encode()
    tx0, rx0 = bytes_interfaz()
    cpu0 = time.process_time()
    t_conf, error = None, None
    try:
        if protocolo == "coap":
            ok = await enviar_coap(cuerpo)
        else:
            ok = await asyncio.to_thread(enviar_http if protocolo == "http" else enviar_mqtt, cuerpo)
        if ok:
            t_conf = time.time_ns()
        else:
            error = "respuesta de error"
    except Exception as e:
        error = type(e).__name__
    cpu_ms = (time.process_time() - cpu0) * 1000
    await asyncio.sleep(PAUSA)            # deja salir los ultimos paquetes (FIN, ACK)
    tx1, rx1 = bytes_interfaz()
    comun.escribir(("INSERT INTO envios VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (alerta["id"], corrida, escenario, netem, protocolo, n,
                alerta["t_envio_ns"], t_conf, int(t_conf is not None),
                len(cuerpo), tx1 - tx0, rx1 - rx0, cpu_ms, error)))
    return t_conf is not None, ((t_conf or 0) - alerta["t_envio_ns"]) / 1e6


# ---------------------------- experimento ----------------------------

def resolver_servidores():
    """Espera a que los tres servidores existan y acepten conexiones."""
    for nombre, host in HOST.items():
        for _ in range(60):
            try:
                IP[nombre] = socket.gethostbyname(host)
                if nombre != "coap":
                    socket.create_connection((IP[nombre], PUERTO[nombre]), timeout=2).close()
                break
            except OSError:
                time.sleep(1)
        else:
            sys.exit(f"ERROR: no responde el servidor {nombre} ({host}). "
                     f"Revisa: docker compose logs {SERVICIO[nombre]}")


async def esperar_servidores():
    """Antes de medir, envia una alerta de prueba por cada protocolo hasta que el
    servidor la registra (asi el receptor MQTT ya esta suscrito cuando empieza)."""
    envio = {"http": enviar_http, "mqtt": enviar_mqtt}
    for p in ("http", "mqtt", "coap"):
        for _ in range(40):
            sonda = "sonda-" + uuid.uuid4().hex[:8]
            cuerpo = json.dumps({"id": sonda}).encode()
            try:
                tarea = enviar_coap(cuerpo) if p == "coap" else asyncio.to_thread(envio[p], cuerpo)
                await asyncio.wait_for(tarea, 5)
                for _ in range(10):
                    bd = comun.bd()
                    llego = bd.execute("SELECT 1 FROM llegadas WHERE id = ?", (sonda,)).fetchone()
                    bd.close()
                    if llego:
                        break
                    await asyncio.sleep(0.2)
                if llego:
                    break
            except Exception:
                pass
            await asyncio.sleep(1)
        else:
            servicio = "receptor-mqtt broker" if p == "mqtt" else SERVICIO[p]
            sys.exit(f"ERROR: el servidor {p} no registra alertas. Revisa: docker compose logs {servicio}")
    comun.escribir(("DELETE FROM llegadas WHERE id LIKE 'sonda-%'", ()))


def cambiar_escenario(token, netem):
    """Aplica la degradacion en el dispositivo y espera a que los servidores tambien."""
    comun.publicar_escenario(token, netem)
    error = comun.aplicar_netem(netem)
    if error:
        sys.exit(f"ERROR: no se pudo aplicar netem en el dispositivo: {error}")
    if not comun.NETEM:
        return
    limite = time.monotonic() + 30
    while time.monotonic() < limite:
        estados = [comun.estado_servidor(s) for s in comun.SERVIDORES]
        if all(e == f"{token} ok" for e in estados):
            return
        if any(e.startswith(f"{token} ERROR") for e in estados):
            sys.exit(f"ERROR: un servidor no pudo aplicar netem: {estados}")
        time.sleep(0.2)
    sys.exit(f"ERROR: los servidores no confirmaron el escenario de red: {estados}. "
             "Revisa: docker compose logs")


async def main():
    with open(ESCENARIOS) as f:
        escenarios = json.load(f)
    corrida = time.strftime("%Y%m%d-%H%M%S")
    resolver_servidores()
    comun.crear_esquema()
    estado["coap"] = await aiocoap.Context.create_client_context()
    cambiar_escenario(f"{corrida}:inicio", "")
    await esperar_servidores()
    protocolos = ["http", "mqtt", "coap"]
    print(f"Corrida {corrida}: {N_ALERTAS} alertas x 3 protocolos x {len(escenarios)} escenarios | "
          f"conexion={'persistente' if PERSISTENTE else 'nueva'} MQTT QoS {MQTT_QOS} "
          f"CoAP {'CON' if COAP_CON else 'NON'}", flush=True)
    try:
        for escenario, netem in escenarios.items():
            cambiar_escenario(f"{corrida}:{escenario}", netem)
            print(f"\n=== Escenario '{escenario}': {netem or 'sin degradacion'} ===", flush=True)
            ok = dict.fromkeys(protocolos, 0)
            for n in range(N_ALERTAS):
                acc_g = detectar_caida(leer_acelerometro_caida())
                orden = protocolos[n % 3:] + protocolos[:n % 3]   # rota el orden
                linea = []
                for p in orden:
                    confirmado, ms = await enviar_alerta(corrida, escenario, netem, p, n, acc_g)
                    ok[p] += confirmado
                    linea.append(f"{p} {ms:7.1f} ms" if confirmado else f"{p}   PERDIDA ")
                print(f"  caida {n + 1:3d}/{N_ALERTAS} ({acc_g} g)  " + " | ".join(sorted(linea)), flush=True)
            print("  confirmadas: " + ", ".join(f"{p} {ok[p]}/{N_ALERTAS}" for p in protocolos), flush=True)
    finally:
        cambiar_escenario(f"{corrida}:fin", "")   # deja la red sin degradacion
        if estado["mqtt"]:
            cerrar_mqtt(estado["mqtt"])
        await estado["coap"].shutdown()
    print("\nListo. Ahora ejecuta:  docker compose run --rm analizar", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
