"""Funciones compartidas: base de datos SQLite y degradacion de red (tc netem)."""
import json
import os
import sqlite3
import subprocess
import threading
import time

DATOS = os.environ.get("DATOS", "/datos")
BD = os.path.join(DATOS, "resultados.db")
DIR_RED = os.path.join(DATOS, "red")
ARCHIVO_ESCENARIO = os.path.join(DIR_RED, "escenario.json")
NETEM = os.environ.get("NETEM", "1") == "1"      # NETEM=0 para probar sin Docker
INTERFAZ = os.environ.get("INTERFAZ", "eth0")
SERVIDORES = ("http", "mqtt", "coap")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS envios(
  id TEXT PRIMARY KEY, corrida TEXT, escenario TEXT, netem TEXT, protocolo TEXT,
  n INTEGER, t_envio_ns INTEGER, t_conf_ns INTEGER, confirmado INTEGER,
  bytes_payload INTEGER, bytes_tx INTEGER, bytes_rx INTEGER, cpu_ms REAL, error TEXT);
CREATE TABLE IF NOT EXISTS llegadas(
  id TEXT, protocolo TEXT, t_llegada_ns INTEGER, bytes_payload INTEGER);
CREATE INDEX IF NOT EXISTS llegadas_id ON llegadas(id);
"""


def bd():
    """Abre la base de datos (solo lectura o uso puntual)."""
    os.makedirs(DIR_RED, exist_ok=True)
    return sqlite3.connect(BD, timeout=30, isolation_level=None)


def escribir(*sentencias, intentos=100):
    """Ejecuta sentencias (sql, parametros) en una transaccion. Varios contenedores
    escriben en el mismo archivo: BEGIN IMMEDIATE + reintentos evita perder registros."""
    for intento in range(intentos):
        con = bd()
        try:
            con.execute("BEGIN IMMEDIATE")
            for sql, parametros in sentencias:
                con.execute(sql, parametros)
            con.execute("COMMIT")
            return
        except sqlite3.OperationalError:
            if intento == intentos - 1:
                raise
            time.sleep(0.02 * (intento + 1))
        finally:
            con.close()


def crear_esquema():
    escribir(*[(s, ()) for s in ESQUEMA.split(";") if s.strip()])


def registrar_llegada(protocolo, cuerpo, t_llegada_ns):
    """La llama cada servidor cuando recibe una alerta."""
    try:
        alerta = json.loads(cuerpo)
        escribir(("INSERT INTO llegadas VALUES (?,?,?,?)",
                  (alerta["id"], protocolo, t_llegada_ns, len(cuerpo))))
    except Exception as e:  # una alerta corrupta no debe tumbar el servidor
        print(f"[{protocolo}] alerta descartada: {e!r}", flush=True)


# ------------------------- degradacion de red -------------------------

def aplicar_netem(spec):
    """Aplica 'tc netem <spec>' al trafico saliente. Devuelve '' o el error."""
    if not NETEM:
        return ""
    subprocess.run(["tc", "qdisc", "del", "dev", INTERFAZ, "root"], capture_output=True)
    if not spec.strip():
        return ""
    r = subprocess.run(["tc", "qdisc", "add", "dev", INTERFAZ, "root", "netem", *spec.split()],
                       capture_output=True, text=True)
    return r.stderr.strip() if r.returncode else ""


def publicar_escenario(token, spec):
    """El dispositivo anuncia el escenario; los servidores lo leen y lo aplican."""
    os.makedirs(DIR_RED, exist_ok=True)
    tmp = ARCHIVO_ESCENARIO + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"token": token, "netem": spec}, f)
    os.replace(tmp, ARCHIVO_ESCENARIO)


def estado_servidor(nombre):
    try:
        with open(os.path.join(DIR_RED, nombre + ".estado")) as f:
            return f.read().strip()
    except OSError:
        return ""


def vigilar_escenario(nombre):
    """Hilo de cada servidor: aplica en su interfaz el escenario anunciado."""
    def bucle():
        os.makedirs(DIR_RED, exist_ok=True)
        ultimo = None
        while True:
            try:
                with open(ARCHIVO_ESCENARIO) as f:
                    esc = json.load(f)
            except (OSError, ValueError):
                esc = {"token": "inicio", "netem": ""}
            if esc["token"] != ultimo:
                error = aplicar_netem(esc["netem"])
                ultimo = esc["token"]
                with open(os.path.join(DIR_RED, nombre + ".estado"), "w") as f:
                    f.write(f"{ultimo} {'ERROR ' + error if error else 'ok'}")
                print(f"[{nombre}] red: '{esc['netem'] or 'sin degradacion'}' {error}", flush=True)
            time.sleep(0.3)
    threading.Thread(target=bucle, daemon=True).start()
