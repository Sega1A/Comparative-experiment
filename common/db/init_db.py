"""Crea las tablas en PostgreSQL (Base.metadata.create_all).

Uso, desde la raíz del repositorio:
    python -m common.db.init_db            # crea las tablas
    python -m common.db.init_db --prueba   # además inserta y lee una fila por tabla
"""

import argparse
from datetime import UTC, datetime

from sqlalchemy import inspect, select

from common.db.database import get_engine, get_session
from common.db.models import AlertaCoAP, AlertaHTTP, AlertaMQTT, Base


def init_db() -> list:
    """Crea las tablas que falten y devuelve la lista de tablas del proyecto."""
    engine = get_engine()
    Base.metadata.create_all(engine)
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
            print(
                f"  OK {modelo.__tablename__}: id={leida.id} "
                f"recibido_en={leida.recibido_en.isoformat()} payload={leida.payload}"
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
    print(f"Tablas listas ({len(tablas)}): {', '.join(tablas)}")
    if args.prueba:
        print("Prueba de inserción y lectura:")
        prueba_insertar_y_leer()


if __name__ == "__main__":
    main()
