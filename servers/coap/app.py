import asyncio
import json
import logging

import aiocoap
from aiocoap import CON, Code, ContentFormat, Message, resource

from common.db import AlertaCoAP, get_session
from common.db.init_db import init_db
from common.log import setup_logging
from common.schemas import AlertDTO, InvalidAlertError, parse_alert

logger = logging.getLogger(__name__)

PORT = 5683


def save_alert(alert: AlertDTO, request: Message) -> None:
    with get_session() as session:
        session.add(
            AlertaCoAP(
                payload=alert.to_payload(),
                tamano_bytes=len(request.payload),
                enviado_en=alert.sent_at,
                tipo_mensaje="CON" if request.mtype == CON else "NON",
                message_id=request.mid,
            )
        )


class AlertResource(resource.Resource):
    def __init__(self, save=save_alert):
        super().__init__()
        self._save = save

    async def render_post(self, request: Message) -> Message:
        try:
            alert = parse_alert(request.payload)
            await asyncio.to_thread(self._save, alert, request)
        except InvalidAlertError as error:
            logger.warning("Rejected alert: %s", error)
            return _reply(Code.BAD_REQUEST, False)
        except Exception:
            logger.exception("Unexpected error while processing alert")
            return _reply(Code.INTERNAL_SERVER_ERROR, False)

        logger.info(
            "Alert received: %s (type=%s, mid=%s)", alert, request.mtype, request.mid
        )
        return _reply(Code.CHANGED, True)


def _reply(code: Code, body: bool) -> Message:
    return Message(
        code=code,
        payload=json.dumps(body).encode(),
        content_format=ContentFormat.JSON,
    )


def _prepare_database() -> None:
    init_db()


def create_site(save=save_alert) -> resource.Site:
    site = resource.Site()
    site.add_resource(["alert"], AlertResource(save))
    return site


async def main(bind=("0.0.0.0", PORT)) -> None:
    await asyncio.to_thread(_prepare_database)
    await aiocoap.Context.create_server_context(create_site(), bind=bind)
    logger.info("CoAP server listening on UDP %s", bind[1])
    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
