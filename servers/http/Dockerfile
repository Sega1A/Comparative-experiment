# Se construye con el contexto en la raíz del repositorio (ver compose.yaml).
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY common ./common
COPY servers/__init__.py ./servers/__init__.py
COPY servers/http ./servers/http
RUN --mount=type=cache,target=/root/.cache/pip pip install ".[http]"
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "servers.http.app:create_app()"]
