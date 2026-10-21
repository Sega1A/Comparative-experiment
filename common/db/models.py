"""Tablas de alertas: una por protocolo, con columnas comunes en AlertaBase."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa de SQLAlchemy para todas las tablas del proyecto."""


class AlertaBase(Base):
    """Columnas comunes a las tres tablas. No crea tabla propia."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, sort_order=-10)
    recibido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        sort_order=-9,
    )
    enviado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, sort_order=-8
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, sort_order=-7
    )
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=-6)
    perfil_red: Mapped[str | None] = mapped_column(Text, nullable=True, sort_order=-5)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id} recibido_en={self.recibido_en}>"


class AlertaHTTP(AlertaBase):
    __tablename__ = "alertas_http"

    ip_origen: Mapped[str] = mapped_column(String(45), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)


class AlertaMQTT(AlertaBase):
    __tablename__ = "alertas_mqtt"
    __table_args__ = (CheckConstraint("qos IN (0, 1, 2)", name="ck_alertas_mqtt_qos"),)

    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    qos: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class AlertaCoAP(AlertaBase):
    __tablename__ = "alertas_coap"
    __table_args__ = (
        CheckConstraint(
            "tipo_mensaje IN ('CON', 'NON')", name="ck_alertas_coap_tipo_mensaje"
        ),
        CheckConstraint(
            "message_id BETWEEN 0 AND 65535", name="ck_alertas_coap_message_id"
        ),
    )

    tipo_mensaje: Mapped[str] = mapped_column(String(3), nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
