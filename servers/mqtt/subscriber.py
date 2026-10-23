import json
import logging
import sys
import time

import paho.mqtt.client as mqtt

from common.log import setup_logging
from common.schemas import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
BROKER_HOST = settings.mqtt_broker_host
BROKER_PORT = settings.mqtt_broker_port
TOPIC = settings.mqtt_topic


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Connected to broker at %s:%s", BROKER_HOST, BROKER_PORT)
        client.subscribe(TOPIC, qos=1)
        logger.info("Subscribed to topic '%s'", TOPIC)
    else:
        logger.error("Could not connect to broker. Code: %s", rc)


def on_message(client, userdata, msg):
    received_at = time.time()
    raw = msg.payload.decode("utf-8", errors="replace")
    logger.info("Alert received: topic=%s qos=%s", msg.topic, msg.qos)

    try:
        data = json.loads(raw)
        sent_at = data.get("timestamp")
        device_id = data.get("device_id", "unknown")

        if sent_at is not None:
            latency_ms = (received_at - float(sent_at)) * 1000.0
            logger.info("device=%s latency=%.2f ms", device_id, latency_ms)
        else:
            logger.warning("Payload has no 'timestamp' key")

        logger.info("Payload: %s", data)

    except (json.JSONDecodeError, ValueError) as error:
        logger.warning("Could not decode JSON: %s", error)


def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="mqtt_subscriber_service",
    )

    client.on_connect = on_connect
    client.on_message = on_message

    logger.info("Connecting to %s:%s...", BROKER_HOST, BROKER_PORT)

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Service stopped")
        client.disconnect()
        sys.exit(0)
    except Exception:
        logger.exception("Critical error")
        sys.exit(1)


if __name__ == "__main__":
    setup_logging()
    main()
