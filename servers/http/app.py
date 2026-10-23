import logging

from flask import Flask, Request, jsonify, request

from common.db import AlertaHTTP, store_alert
from common.db.init_db import init_db
from common.log import setup_logging
from common.schemas import AlertDTO, InvalidAlertError, parse_alert

logger = logging.getLogger(__name__)

PORT = 8000


def save_alert(alert: AlertDTO, request: Request) -> None:
    store_alert(
        AlertaHTTP,
        alert,
        len(request.get_data()),
        ip_origen=request.remote_addr or "unknown",
        content_type=request.content_type[:100] if request.content_type else None,
    )


def create_app(save=save_alert) -> Flask:
    app = Flask(__name__)

    @app.post("/http/alert")
    def receive_alert():
        try:
            alert = parse_alert(request.get_data())
            save(alert, request)
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
    """Punto de entrada de gunicorn: configura el logging y prepara la base."""
    setup_logging()
    init_db()
    return create_app()


if __name__ == "__main__":
    setup_logging()
    init_db()
    create_app().run(host="0.0.0.0", port=PORT)
