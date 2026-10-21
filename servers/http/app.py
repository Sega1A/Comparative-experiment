import logging

from alert import AlertDTO, InvalidAlertError
from flask import Flask, jsonify, request

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="0.0.0.0", port=8000)
