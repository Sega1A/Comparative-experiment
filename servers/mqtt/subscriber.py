import json
import os
import sys
import time

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "mosquitto")
BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
TOPIC = "alertas/caidas"


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(
            f"[MQTT] Conectado exitosamente al Broker en {BROKER_HOST}:{BROKER_PORT}",
            flush=True,
        )
        client.subscribe(TOPIC, qos=1)
        print(
            f"[MQTT] Suscrito al tema: '{TOPIC}' (Escuchando en QoS 0 y QoS 1)",
            flush=True,
        )
    else:
        print(f"[MQTT] Error de conexión con el Broker. Código: {rc}", flush=True)


def on_message(client, userdata, msg):
    recepcion_ts = time.time()
    payload_raw = msg.payload.decode("utf-8", errors="replace")

    print("\n" + "=" * 55, flush=True)
    print("[NUEVA ALERTA RECIBIDA]", flush=True)
    print(f"  ▸ Tema (Topic)   : {msg.topic}", flush=True)
    print(f"  ▸ QoS del Mensaje: {msg.qos}", flush=True)

    try:
        data = json.loads(payload_raw)
        emision_ts = data.get("timestamp")
        device_id = data.get("device_id", "Desconocido")

        if emision_ts is not None:
            latencia_ms = (recepcion_ts - float(emision_ts)) * 1000.0
            print(f"  ▸ Dispositivo ID : {device_id}", flush=True)
            print(f"  ▸ Latencia Medida: {latencia_ms:.2f} ms", flush=True)
        else:
            print(
                "  ⚠️  Advertencia: El payload no incluye la clave 'timestamp'.",
                flush=True,
            )

        print(f"  ▸ Payload JSON   : {data}", flush=True)

    except (json.JSONDecodeError, ValueError) as err:
        print(f"  ❌ Error al decodificar JSON: {err}", flush=True)


def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="mqtt_subscriber_service",
    )

    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[MQTT] Conectando a {BROKER_HOST}:{BROKER_PORT}...", flush=True)

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[MQTT] Servicio detenido.", flush=True)
        client.disconnect()
        sys.exit(0)
    except Exception as e:
        print(f"[MQTT] Error crítico: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
