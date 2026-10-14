"""Servidor B: receptor del centro de auxilio. Se suscribe al broker Mosquitto
y registra cada alerta publicada en el tema 'alertas/caidas'."""
import os
import time

import paho.mqtt.client as mqtt

import comun

TEMA = "alertas/caidas"


def al_conectar(cliente, datos, flags, codigo, props):
    cliente.subscribe(TEMA, qos=2)   # se recibe con el QoS con que publico el dispositivo
    print(f"[mqtt] suscrito a {TEMA}", flush=True)


def al_recibir(cliente, datos, msg):
    t = time.time_ns()
    comun.registrar_llegada("mqtt", msg.payload, t)


if __name__ == "__main__":
    comun.crear_esquema()
    comun.vigilar_escenario(os.environ.get("NOMBRE", "mqtt"))
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="centro-auxilio")
    c.on_connect = al_conectar
    c.on_message = al_recibir
    c.connect_async(os.environ.get("MQTT_HOST", "127.0.0.1"),
                    int(os.environ.get("PUERTO_MQTT", 1883)), keepalive=60)
    c.loop_forever(retry_first_connection=True)
