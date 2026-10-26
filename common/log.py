"""Configuración de logging común a servidores y herramientas.

Todo el proyecto escribe por `logging`, con el mismo formato y en stdout
(así `docker compose logs` muestra lo mismo que la terminal). Cada módulo usa:

    logger = logging.getLogger(__name__)

y el punto de entrada (servidor o script) llama una vez a `setup_logging()`.
El nivel sale de LOG_LEVEL (ver `common.schemas.Settings`).
"""

import logging
import sys

from common.schemas import get_settings

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def setup_logging(level: str | None = None) -> None:
    """Configura el logger raíz. Sin `level` usa LOG_LEVEL de la configuración."""
    logging.basicConfig(
        level=level or get_settings().log_level,
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
