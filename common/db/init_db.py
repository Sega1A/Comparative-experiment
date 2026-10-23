"""Crea las tablas en PostgreSQL (Base.metadata.create_all).

Uso, desde la raíz del repositorio:
    python -m common.db.init_db            # crea las tablas
    python -m common.db.init_db --prueba   # además inserta y lee una fila por tabla
"""

import argparse
import logging
from datetime import UTC, datetime

from sqlalchemy import inspect, select, text

from common.db.database import get_engine, get_session
from common.db.models import AlertaCoAP, AlertaHTTP, AlertaMQTT, Base
from common.log import setup_logging

logger = logging.getLogger(__name__)

# Clave del bloqueo de PostgreSQL que evita que dos servidores creen tablas a la vez.
INIT_LOCK_ID = 7_315_001


def init_db() -> list:
    """Crea las tablas que falten y devuelve la lista de tablas del proyecto.

    Es seguro llamarla desde varios procesos a la vez (arranque de los servidores).
    """
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:id)"), {"id": INIT_LOCK_ID}
        )
        Base.metadata.create_all(connection)
    existentes = set(inspect(engine).get_table_names())
    return [t for t in Base.metadata.tables if t in existentes]


def prueba_insertar_y_leer() -> None:
    """Inserta una fila de prueba en cada tabla, la lee y luego la borra."""
    ahora = datetime.now(UTC)
    payload = {"dispositivo": "prueba", "evento": "caida", "aceleracion_g": 2.7}
    filas = [
        AlertaHTTP(
            payload=payload,
            tamano_bytes=64,
            enviado_en=ahora,
            perfil_red="ideal",
            ip_origen="127.0.0.1",
            content_type="application/json",
        ),
        AlertaMQTT(
            payload=payload,
            tamano_bytes=64,
            enviado_en=ahora,
            perfil_red="ideal",
            topic="alertas/caidas",
            qos=1,
        ),
        AlertaCoAP(
            payload=payload,
            tamano_bytes=64,
            enviado_en=ahora,
            perfil_red="ideal",
            tipo_mensaje="CON",
            message_id=1234,
        ),
    ]
    with get_session() as sesion:
        sesion.add_all(filas)
        sesion.flush()
        for fila in filas:
            modelo = type(fila)
            leida = sesion.scalars(select(modelo).where(modelo.id == fila.id)).one()
            logger.info(
                "OK %s: id=%s recibido_en=%s payload=%s",
                modelo.__tablename__,
                leida.id,
                leida.recibido_en.isoformat(),
                leida.payload,
            )
        for fila in filas:
            sesion.delete(fila)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea las tablas de alertas.")
    parser.add_argument(
        "--prueba",
        action="store_true",
        help="inserta, lee y borra una fila de prueba por tabla",
    )
    args = parser.parse_args()

    tablas = init_db()
    logger.info("Tablas listas (%s): %s", len(tablas), ", ".join(tablas))
    if args.prueba:
        logger.info("Prueba de inserción y lectura:")
        prueba_insertar_y_leer()


if __name__ == "__main__":
    setup_logging()
    main()
