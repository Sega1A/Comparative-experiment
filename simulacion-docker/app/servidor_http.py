"""Servidor A: HTTP. Recibe la alerta por POST /alerta y registra la llegada."""
import os
import time

from flask import Flask, request
from waitress import serve

import comun

app = Flask(__name__)


@app.post("/alerta")
def alerta():
    t = time.time_ns()
    comun.registrar_llegada("http", request.get_data(), t)
    return "OK", 200


if __name__ == "__main__":
    comun.crear_esquema()
    comun.vigilar_escenario(os.environ.get("NOMBRE", "http"))
    print("[http] escuchando en TCP 5000", flush=True)
    serve(app, host="0.0.0.0", port=int(os.environ.get("PUERTO_HTTP", 5000)), threads=8)
