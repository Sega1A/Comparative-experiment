FROM python:3.12-slim

WORKDIR /app

COPY servers/coap/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY servers/coap/app.py ./

EXPOSE 5683/udp

CMD ["python", "app.py"]
