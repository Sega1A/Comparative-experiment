FROM python:3.13-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends iproute2 \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask==3.1.3 waitress==3.0.2 aiocoap==0.4.17 paho-mqtt==2.1.0 matplotlib==3.11.2
WORKDIR /app
COPY app/ /app/
ENV PYTHONUNBUFFERED=1
