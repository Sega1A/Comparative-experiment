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
├── .gitignore
└── README.md
```

## Qué va en cada carpeta

| Carpeta | Contenido previsto | Tecnología |
|---|---|---|
| `common/` | Formato común del mensaje de alerta y módulo de registro de resultados en SQLite. Lo importan los tres servidores y el cliente, para que midan y guarden igual. | Python |
| `servers/http/` | Servidor que recibe alertas por `POST /alerta` y registra su llegada. | Python, Flask |
| `servers/coap/` | Servidor que recibe alertas CoAP confirmables y responde con ACK. | Python, aiocoap |
| `servers/mqtt/` | Configuración de Mosquitto y suscriptor que registra las alertas publicadas. | Mosquitto, Python, paho-mqtt |
| `client/` | Cliente en Python que envía alertas por los tres protocolos en la Fase 1 (reemplaza al ESP32). | Python |
| `firmware/` | Proyecto PlatformIO del ESP32, con tres entornos (`http`, `mqtt`, `coap`) sobre el mismo código de detección. | C++, PlatformIO (Arduino) |
| `netem/` | Scripts reproducibles de degradación de red (retardo, pérdida, pérdida en ráfagas). | `tc netem` |
| `results/` | Base de datos de resultados y CSV exportados. Los `.db` no se suben a Git. | SQLite, CSV |
| `docs/` | Diagramas de arquitectura, plan de pruebas, requerimientos y notas del equipo. | Markdown |

Cada carpeta tiene un archivo `.gitkeep` vacío para que Git la conserve. Se puede borrar cuando la carpeta tenga contenido real.

## Cómo ejecutar

Pendiente. Se completará cuando existan los servicios (Docker Compose, firmware y cliente).

## Base de datos (PostgreSQL + SQLAlchemy)

Las alertas que recibe cada servidor se guardan en PostgreSQL 16. Todo el código de acceso está en `common/db/` y los servidores lo importan desde ahí; nadie define tablas dentro de `servers/`.

```
common/db/
├── __init__.py      # exporta modelos, get_engine y get_session
├── database.py      # engine, sesión y lectura de DATABASE_URL
├── models.py        # AlertaBase y las tablas alertas_http, alertas_mqtt, alertas_coap
└── init_db.py       # crea las tablas (create_all)
```

### 1. Requisitos

- Python 3.10 o superior
- Docker Desktop (o Docker Engine con Compose)

### 2. Instalar dependencias

Desde la raíz del repositorio:

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configurar la conexión

La conexión se define en un archivo `.env` en la raíz del repositorio (junto a `compose.yaml`). El `.env` **no se sube a Git**: tiene claves. Hay dos formas de usarlo:

**A. Base compartida del equipo (Supabase), la forma normal.** Pida el archivo `.env` al responsable del proyecto (se pasa por privado) y colóquelo en la raíz. Trae `DATABASE_URL` con la URL de la base compartida; el módulo acepta el formato `postgresql://...` y lo adapta a psycopg v3. No hace falta Docker. Las tablas ya están creadas; si no lo estuvieran, se crean con el paso 5.

**B. Base local con Docker (opcional, para pruebas propias).** Copie `.env.example` a `.env`, cambie la clave en `POSTGRES_PASSWORD` y en `DATABASE_URL` (deben coincidir) y levante la base con el paso 4. `DATABASE_URL` usa `localhost` cuando el código corre en su máquina y `db` cuando corre dentro de otro contenedor de Docker Compose. Si ya tiene otro PostgreSQL usando el puerto 5432, ponga `POSTGRES_PUERTO=5433` en su `.env` y cambie `localhost:5432` por `localhost:5433` en `DATABASE_URL`.

### 4. Levantar PostgreSQL local (solo con la opción B)

```bash
docker compose up -d db
```

Los datos se guardan en el volumen con nombre `datos_postgres`, así que no se pierden al apagar el contenedor. Para borrarlos por completo: `docker compose down -v`.

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
from common.db import get_session, AlertaHTTP

with get_session() as sesion:
    sesion.add(AlertaHTTP(
        payload=datos,
        tamano_bytes=len(cuerpo),
        ip_origen=request.remote_addr,
        content_type=request.content_type,
    ))
```

`get_session()` hace commit al salir del bloque y rollback si hay un error.

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
