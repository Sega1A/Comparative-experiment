"""Guardado de alertas, igual para los tres protocolos.

Cada servidor aporta solo lo que es propio de su protocolo (IP, topic y QoS,
tipo de mensaje y message id) y esta función completa el resto:

    store_alert(AlertaHTTP, alert, len(body), ip_origen=ip, content_type=tipo)
"""

from common.db.database import get_session
from common.db.models import AlertaBase
from common.schemas import AlertDTO, get_settings


def store_alert(
    model: type[AlertaBase], alert: AlertDTO, size: int, **metadata: object
) -> None:
    """Guarda `alert` en la tabla de `model`.

    `size` son los bytes del mensaje de la aplicación (el cuerpo recibido, sin
    cabeceras del protocolo). `perfil_red` sale de NETWORK_PROFILE.
    """
    with get_session() as session:
        session.add(
            model(
                payload=alert.to_payload(),
                tamano_bytes=size,
                enviado_en=alert.sent_at,
                perfil_red=get_settings().network_profile,
                **metadata,
            )
        )
