# Se construye con el contexto en la raíz del repositorio (ver compose.yaml).
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY common ./common
COPY servers/__init__.py ./servers/__init__.py
COPY servers/coap ./servers/coap
RUN --mount=type=cache,target=/root/.cache/pip pip install ".[coap]"
EXPOSE 5683/udp
CMD ["python", "-m", "servers.coap.app"]
