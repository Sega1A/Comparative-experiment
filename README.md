# Detección de caídas: comparativa HTTP, MQTT y CoAP

Evaluación comparativa de los protocolos HTTP, MQTT y CoAP en un dispositivo portátil de detección de caídas para adultos mayores en zonas rurales con conectividad limitada. El dispositivo usa un ESP32 con un acelerómetro MPU6050. El proyecto mide latencia, fiabilidad, consumo de recursos (memoria y CPU) y tamaño de mensajes, en dos fases: simulación con Docker y validación física con el ESP32.

Proyecto de la asignatura de Servicios Telemáticos.

## Estructura del repositorio

```
├── common/            # Código compartido
├── servers/
│   ├── http/          # Servidor HTTP
│   ├── coap/          # Servidor CoAP
│   └── mqtt/          # Broker MQTT y suscriptor
├── client/            # Cliente simulado
├── firmware/          # Firmware del ESP32
├── netem/             # Degradación de red
├── results/           # Resultados de las pruebas
├── docs/              # Documentación
├── tests/             # Pruebas automáticas (pytest)
├── compose.yaml       # Levanta toda la pila con Docker Compose
├── pyproject.toml     # Dependencias, pytest y ruff
├── .env.example       # Plantilla de configuración
├── .gitignore
└── README.md
```

## Qué va en cada carpeta

| Carpeta | Contenido previsto | Tecnología |
|---|---|---|
| `common/` | Formato común del mensaje de alerta (`AlertDTO`), configuración, logging y acceso a PostgreSQL. Lo importan los tres servidores y el cliente, para que validen y guarden igual. | Python, Pydantic, SQLAlchemy |
| `servers/http/` | Servidor que recibe alertas por `POST /alert` y las guarda en `alertas_http`. | Python, Flask |
| `servers/coap/` | Servidor que recibe alertas CoAP confirmables, responde con ACK y las guarda en `alertas_coap`. | Python, aiocoap |
| `servers/mqtt/` | Configuración de Mosquitto y suscriptor que guarda en `alertas_mqtt` las alertas publicadas. | Mosquitto, Python, paho-mqtt |
| `client/` | Cliente en Python que envía alertas por los tres protocolos en la Fase 1 (reemplaza al ESP32). | Python |
| `firmware/` | Proyecto PlatformIO del ESP32, con tres entornos (`http`, `mqtt`, `coap`) sobre el mismo código de detección. | C++, PlatformIO (Arduino) |
| `netem/` | Scripts reproducibles de degradación de red (retardo, pérdida, pérdida en ráfagas). | `tc netem` |
| `results/` | CSV exportados desde PostgreSQL (`python -m common.db.export`, ver más abajo). | CSV |
| `docs/` | Diagramas de arquitectura, plan de pruebas, requerimientos y notas del equipo. | Markdown |
| `tests/` | Pruebas de `common/` y de los tres servidores. `tests/integration/` usa un PostgreSQL real. | pytest |

Las carpetas que aún no tienen contenido (`client/`, `firmware/`, `netem/`, `results/`) conservan un `.gitkeep` vacío para que Git las mantenga. Se puede borrar cuando la carpeta tenga contenido real.

## Cómo ejecutar

El cliente simulado y el firmware aún no existen; hoy se prueba cada servidor con `curl`, `mosquitto_pub`, `aiocoap-client` o `servers/coap/smoke.py` (cada `README.md` de `servers/` explica cómo).

### Todo el proyecto con Docker Compose

Desde la raíz del repositorio:

```bash
cp .env.example .env          # cambie la clave en POSTGRES_PASSWORD y en DATABASE_URL
docker compose up -d --build  # base de datos, HTTP, CoAP, broker MQTT y suscriptor
docker compose logs -f        # logs de todos los servicios con el mismo formato
```

| Servicio | Puerto en su máquina | Para probarlo |
|---|---|---|
| `db` | `POSTGRES_PUERTO` (5432 por defecto) | `docker compose exec db psql -U <usuario> <base>` |
| `http` | 8000 | `POST http://localhost:8000/alert` |
| `coap` | 5683/udp | `coap://localhost:5683/alert` |
| `mosquitto` | 1883 | publicar en el topic `alert` |
| `mqtt-subscriber` | — | guarda lo publicado en `alert` |

Los servidores de Compose siempre guardan en el servicio `db` (base local), aunque su `.env` apunte a otra base. Cada servidor crea las tablas que falten al arrancar. Para levantar solo algunos: `docker compose up -d --build db http`.

Detener: `docker compose down` (conserva los datos) o `docker compose down -v` (borra también la base).

### Un servidor suelto, sin Docker

Necesita una PostgreSQL accesible (por ejemplo `docker compose up -d db`) y `DATABASE_URL` apuntando a `localhost` (ver «Configurar la conexión»). Con el entorno virtual activado (paso 2) y desde la raíz:

```bash
python -m servers.http.app          # HTTP en el puerto 8000
python -m servers.coap.app          # CoAP en el puerto UDP 5683
python -m servers.mqtt.subscriber   # suscriptor; necesita un broker (MQTT_BROKER_HOST)
```

Los pasos de cada servidor están en su propio `README.md`: [HTTP](servers/http/README.md), [CoAP](servers/coap/README.md), [MQTT](servers/mqtt/README.md).

### Pruebas y calidad del código

```bash
pytest                                   # pruebas que no necesitan base de datos
TEST_DATABASE_URL=postgresql://postgres:clave@localhost:5499/alertas pytest -m integration
ruff check . && ruff format --check --exclude "*.md" .
```

`TEST_DATABASE_URL` debe apuntar a una base desechable: las pruebas de integración borran las tablas de alertas. Sin esa variable se omiten. El CI ejecuta los tres comandos en cada pull request.

## Convenciones del proyecto

### Mensaje de alerta

Los tres protocolos reciben el mismo objeto JSON, validado por `AlertDTO` (`common/schemas/alert.py`):

```json
{ "device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000 }
```

| Campo | Tipo | Obligatorio |
|---|---|---|
| `device_id` | texto | sí |
| `sequence` | entero | sí |
| `timestamp` | entero, milisegundos desde epoch (UTC) | sí |
| `event_type` | texto | no |
| `battery_level` | entero | no |
| `acceleration` | número | no |

No se aceptan otros campos ni tipos distintos (`"1"` no vale como entero). `AlertDTO.model_json_schema()` entrega el contrato como JSON Schema.

### Puntos de entrada y respuestas

| Protocolo | Entrada | Alerta válida | Alerta inválida | Error al guardar |
|---|---|---|---|---|
| HTTP | `POST /alert` | `200` y `true` | `400` y `false` | `500` y `false` |
| CoAP | `POST /alert` | `2.04 Changed` y `true` | `4.00 Bad Request` y `false` | `5.00` y `false` |
| MQTT | topic `alert` (configurable con `MQTT_TOPIC`) | se guarda | se descarta y queda en el log | queda en el log |

### Qué se guarda y cómo se mide

- `tamano_bytes` es el tamaño en bytes del mensaje de la aplicación (el cuerpo JSON recibido), sin cabeceras HTTP, CoAP ni MQTT. Es la misma definición en los tres protocolos.
- `recibido_en` lo pone la base al insertar y `enviado_en` sale del `timestamp` de la alerta. La latencia (`latency_ms` en la exportación) solo es válida si los relojes del emisor y del servidor coinciden: en Docker lo hacen, en el ESP32 requerirá sincronizar la hora.
- `perfil_red` se llena con la variable `NETWORK_PROFILE` (por ejemplo `ideal` o `perdida_10`); sin ella queda vacío.
- MQTT se suscribe con QoS 2, de modo que la columna `qos` es el QoS con que publicó el dispositivo.
- Con QoS 1 el broker puede entregar un mensaje más de una vez, lo que generaría filas repetidas (distinguibles por `device_id` y `sequence`). Hoy no se eliminan duplicados.

### Idiomas y nombres

Las tablas y columnas de la base están en español (`alertas_http`, `recibido_en`, `tamano_bytes`) y el código, la API y los CSV exportados en inglés (`protocol`, `latency_ms`, `alerts_http.csv`). Es una convención deliberada: los nombres de la base no se renombran porque implicaría migrar los datos ya guardados.

### Logging

Todo el código escribe con `logging` (nunca `print`), con el mismo formato en servidores y herramientas:

```
2026-10-23 16:50:38,439 INFO     servers.http.app: Alert received: {...}
```

Cada módulo usa `logger = logging.getLogger(...)` y el punto de entrada llama una vez a `setup_logging()` (`common/log.py`). El nivel se ajusta con `LOG_LEVEL`. En Docker la hora sale en UTC. La única excepción es `servers/coap/smoke.py`, cuya salida es el informe de la prueba. El registro de acceso propio de gunicorn (HTTP) mantiene su formato.

### Configuración

Toda la configuración se lee en `common/schemas/config.py` (`Settings`): primero las variables de entorno y luego el `.env` de la raíz. Para agregar una variable, un campo en `Settings` y una línea en `.env.example`.

| Variable | Para qué | Por defecto |
|---|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL | obligatoria |
| `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT` | Broker MQTT | `localhost`, `1883` |
| `MQTT_TOPIC` | Topic de las alertas | `alert` |
| `NETWORK_PROFILE` | Valor de `perfil_red` en cada alerta guardada | vacío |
| `LOG_LEVEL` | Nivel de los logs | `INFO` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PUERTO` | Contenedor `db` de Compose | ver `.env.example` |

## Base de datos (PostgreSQL + SQLAlchemy)

Las alertas que recibe cada servidor se guardan en PostgreSQL 16. Todo el código de acceso está en `common/db/` y los servidores lo importan desde ahí; nadie define tablas dentro de `servers/`. El resto de `common/` es `schemas/` (`AlertDTO` y `Settings`, ver `docs/pydantic.md`) y `log.py`.

```
common/db/
├── __init__.py      # exporta modelos, get_engine y get_session
├── database.py      # engine, sesión y lectura de DATABASE_URL
├── models.py        # AlertaBase y las tablas alertas_http, alertas_mqtt, alertas_coap
├── repository.py    # store_alert(): guardado común a los tres servidores
├── init_db.py       # crea las tablas (create_all)
└── export.py        # exporta las alertas a CSV
```

### 1. Requisitos

- Python 3.11 o superior
- Docker Desktop (o Docker Engine con Compose)

### 2. Instalar dependencias

Desde la raíz del repositorio:

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate
pip install -e ".[dev,http,coap,mqtt]"
```

Las dependencias y sus versiones están en `pyproject.toml`: una base común (SQLAlchemy, psycopg, Pydantic) más un extra por servidor (`http`, `coap`, `mqtt`) y `dev` (pytest, ruff). Para un solo servidor basta su extra, por ejemplo `pip install -e ".[coap]"`.

### 3. Configurar la conexión

La conexión se define en un archivo `.env` en la raíz del repositorio (junto a `compose.yaml`). El `.env` **no se sube a Git**: tiene claves. Hay dos formas de usarlo:

**A. Base compartida del equipo (Supabase), la forma normal.** Pida el archivo `.env` al responsable del proyecto (se pasa por privado) y colóquelo en la raíz. Trae `DATABASE_URL` con la URL de la base compartida; el módulo acepta el formato `postgresql://...` y lo adapta a psycopg v3. No hace falta Docker. Las tablas ya están creadas; si no lo estuvieran, se crean con el paso 5.

**B. Base local con Docker (opcional, para pruebas propias).** Copie `.env.example` a `.env`, cambie la clave en `POSTGRES_PASSWORD` y en `DATABASE_URL` (deben coincidir) y levante la base con el paso 4. `DATABASE_URL` usa `localhost` cuando el código corre en su máquina y `db` cuando corre dentro de otro contenedor de Docker Compose. Si ya tiene otro PostgreSQL usando el puerto 5432, ponga `POSTGRES_PUERTO=5433` en su `.env` y cambie `localhost:5432` por `localhost:5433` en `DATABASE_URL`.

### 4. Levantar PostgreSQL local (solo con la opción B)

```bash
docker compose up -d db
```

Los datos se guardan en el volumen con nombre `datos_postgres`, así que no se pierden al apagar el contenedor. Para borrarlos por completo: `docker compose down -v`.

Los servidores crean las tablas que falten al arrancar (es seguro aunque arranquen a la vez), así que este paso y el siguiente solo hacen falta si quiere crearlas a mano.

### 5. Crear las tablas

```bash
python -m common.db.init_db
```

Para comprobar además que se puede insertar y leer en cada tabla (las filas de prueba se borran al final):

```bash
python -m common.db.init_db --prueba
```

### Tablas

Columnas comunes (`AlertaBase`): `id`, `recibido_en` (con zona horaria, `now()` del servidor), `enviado_en`, `payload` (JSONB), `tamano_bytes`, `perfil_red`.

| Tabla | Columnas propias |
|---|---|
| `alertas_http` | `ip_origen`, `content_type` |
| `alertas_mqtt` | `topic`, `qos` (0, 1 o 2) |
| `alertas_coap` | `tipo_mensaje` (`CON`/`NON`), `message_id` (0–65535) |

### Uso desde un servidor

```python
from common.db import AlertaHTTP, store_alert
from common.schemas import parse_alert

alert = parse_alert(cuerpo)  # lanza InvalidAlertError si no cumple el formato
store_alert(
    AlertaHTTP, alert, len(cuerpo),
    ip_origen=request.remote_addr,
    content_type=request.content_type,
)
```

`store_alert()` completa `payload`, `tamano_bytes`, `enviado_en` y `perfil_red`; el servidor solo aporta las columnas propias de su protocolo. Para otras consultas, `get_session()` hace commit al salir del bloque y rollback si hay un error:

```python
from common.db import get_session

with get_session() as sesion:
    sesion.add(...)
```

### Exportar resultados a CSV

Para comparar los protocolos sin consultar la base a mano, las alertas guardadas se exportan a archivos `.csv`, que se abren en Excel, LibreOffice o pandas. Usa la misma `DATABASE_URL` del `.env`.

```bash
python -m common.db.export
```

Crea una carpeta `results/export_<fecha y hora UTC>/` con:

| Archivo | Contenido |
|---|---|
| `alerts_http.csv`, `alerts_mqtt.csv`, `alerts_coap.csv` | Todas las columnas de cada tabla |
| `alerts_all.csv` | Los tres protocolos juntos, solo con las columnas comunes, para compararlos |

Cada fila agrega dos columnas calculadas: `protocol` y `latency_ms`, que es `recibido_en` menos `enviado_en` en milisegundos. Queda vacía si la alerta no tiene `enviado_en`. Las fechas se exportan en UTC y el `payload` como texto JSON.

Opciones:

| Opción | Uso |
|---|---|
| `--protocol http` | Solo un protocolo (`http`, `mqtt`, `coap` o `all`, por defecto `all`) |
| `--profile ideal` | Solo las alertas con ese `perfil_red`, para comparar un mismo escenario de red |
| `--output results/prueba1` | Carpeta de salida en lugar de la carpeta con fecha |

Ejemplo: `python -m common.db.export --profile perdida_10 --output results/perdida_10`.

## Gestión del proyecto

Scrum con sprints de una semana. El backlog y los sprints están en GitHub Projects.
