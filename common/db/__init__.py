"""Módulo de base de datos compartido por los tres servidores.

    from common.db import get_session, AlertaHTTP

    with get_session() as sesion:
        sesion.add(AlertaHTTP(payload={...}, tamano_bytes=120,
                              ip_origen="192.168.1.10",
                              content_type="application/json"))
"""

from common.db.database import get_database_url, get_engine, get_session
from common.db.models import AlertaBase, AlertaCoAP, AlertaHTTP, AlertaMQTT, Base

__all__ = [
    "Base",
    "AlertaBase",
    "AlertaHTTP",
    "AlertaMQTT",
    "AlertaCoAP",
    "get_database_url",
    "get_engine",
    "get_session",
]
