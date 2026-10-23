import logging

from flask import Flask, jsonify, request

from common.log import setup_logging
from servers.http.alert import AlertDTO, InvalidAlertError

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.post("/http/alert")
    def receive_alert():
        try:
            payload = request.get_json(silent=True)
            alert = AlertDTO.from_payload(payload)
        except InvalidAlertError as error:
            logger.warning("Rejected alert: %s", error)
            return jsonify(False), 400
        except Exception:
            logger.exception("Unexpected error while processing alert")
            return jsonify(False), 500

        logger.info("Alert received: %s", alert)
        return jsonify(True), 200

    return app


def create_wsgi_app() -> Flask:
    """Punto de entrada de gunicorn: configura el logging y crea la app."""
    setup_logging()
    return create_app()


if __name__ == "__main__":
    setup_logging()
    create_app().run(host="0.0.0.0", port=8000)
