import logging
import sys

import paho.mqtt.client as mqtt

from common.db import AlertaMQTT, store_alert
from common.db.init_db import init_db
from common.log import setup_logging
from common.schemas import AlertDTO, InvalidAlertError, get_settings, parse_alert

logger = logging.getLogger("servers.mqtt.subscriber")

# QoS máximo: el broker entrega cada mensaje con el menor entre el QoS con que se
# publicó y este, así la columna `qos` refleja lo que realmente usó el dispositivo.
SUBSCRIPTION_QOS = 2


def save_alert(alert: AlertDTO, msg: mqtt.MQTTMessage) -> None:
    store_alert(AlertaMQTT, alert, len(msg.payload), topic=msg.topic, qos=msg.qos)


def handle_message(msg: mqtt.MQTTMessage, save=save_alert) -> bool:
    """Valida y guarda un mensaje. Devuelve True si quedó guardado."""
    try:
        alert = parse_alert(msg.payload)
        save(alert, msg)
    except InvalidAlertError as error:
        logger.warning("Rejected alert on '%s': %s", msg.topic, error)
        return False
    except Exception:
        logger.exception("Unexpected error while processing alert")
        return False

    logger.info(
        "Alert received: %s (topic=%s, qos=%s)",
        alert.to_payload(),
        msg.topic,
        msg.qos,
    )
    return True


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code.is_failure:
        logger.error("Could not connect to broker: %s", reason_code)
        return
    logger.info("Connected to broker")
    client.subscribe(userdata.mqtt_topic, qos=SUBSCRIPTION_QOS)
    logger.info("Subscribed to '%s' (qos=%s)", userdata.mqtt_topic, SUBSCRIPTION_QOS)


def on_message(client, userdata, msg):
    handle_message(msg)


def main() -> None:
    settings = get_settings()
    init_db()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="mqtt_subscriber_service",
        userdata=settings,
    )
    client.on_connect = on_connect
    client.on_message = on_message

    logger.info(
        "Connecting to %s:%s...", settings.mqtt_broker_host, settings.mqtt_broker_port
    )
    try:
        client.connect_async(
            settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=60
        )
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        logger.info("Service stopped")
        client.disconnect()
    except Exception:
        logger.exception("Critical error")
        sys.exit(1)


if __name__ == "__main__":
    setup_logging()
    main()
