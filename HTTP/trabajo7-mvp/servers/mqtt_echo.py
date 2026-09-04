"""
Servicio de eco MQTT.

MQTT es publicacion/suscripcion: no tiene "respuesta" nativa como HTTP.
Para poder medir un round-trip comparable, este servicio se suscribe a
bench/req y republica lo que llega en bench/resp.

Flujo:  cliente --publish--> bench/req --> [este servicio] --> bench/resp --> cliente
"""

import os
import socket
import logging

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

TOPIC_REQ = "bench/req"
TOPIC_RESP = "bench/resp"


def on_socket_open(client, userdata, sock):
    """Desactiva Nagle. Sin esto, TCP acumula mensajes pequenos y agrega
    ~40 ms artificiales a cada QoS 1 / QoS 2."""
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


def on_connect(client, userdata, flags, rc):
    logging.info("Conectado al broker (rc=%s). Suscribiendo a %s", rc, TOPIC_REQ)
    # QoS 2 en la suscripcion: el QoS efectivo lo decide el publisher
    client.subscribe(TOPIC_REQ, qos=2)


def on_message(client, userdata, msg):
    # Devolvemos el mismo payload con el mismo QoS con el que llego
    client.publish(TOPIC_RESP, payload=msg.payload, qos=msg.qos)


def main():
    client = mqtt.Client(client_id="t7-echo", clean_session=True)
    client.on_socket_open = on_socket_open
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    logging.info("Servicio de eco MQTT iniciado contra %s:%s", MQTT_HOST, MQTT_PORT)
    client.loop_forever()


if __name__ == "__main__":
    main()
