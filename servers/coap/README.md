# Servidor CoAP

Recibe alertas por CoAP sobre UDP, responde con ACK a los mensajes confirmables (CON) y guarda cada alerta válida en la tabla `alertas_coap` de PostgreSQL.

| Archivo       | Para qué sirve                                                  |
| ------------- | --------------------------------------------------------------- |
| `app.py`      | Servidor (aiocoap). Recurso `POST /alert` en el puerto UDP 5683 |
| `alert.py`    | Validación del cuerpo de la alerta (`AlertDTO`)                 |
| `smoke.py`    | Script de prueba manual contra un servidor en ejecución         |
| `test_app.py` | Tests automáticos con pytest (no necesitan base de datos)       |
| `Dockerfile`  | Imagen del servicio, se construye desde la raíz del repo        |

## Cómo funciona

- **Ruta:** `POST coap://HOST:5683/alert`
- **Cuerpo (JSON):** los tres campos son obligatorios y no se aceptan otros.

  ```json
  { "device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000 }
  ```

  `device_id` es texto; `sequence` y `timestamp` (milisegundos) son enteros.

- **Respuestas:**

  | Situación                            | Código                       | Cuerpo  |
  | ------------------------------------ | ---------------------------- | ------- |
  | Alerta válida y guardada             | `2.04 Changed`               | `true`  |
  | Alerta inválida o JSON malformado    | `4.00 Bad Request`           | `false` |
  | Error al guardar en la base de datos | `5.00 Internal Server Error` | `false` |
  | Otra ruta                            | `4.04 Not Found`             |         |
  | Otro método (GET, etc.)              | `4.05 Method Not Allowed`    |         |

- **Mensajes CON:** el servidor responde con el ACK llevando ya la respuesta (piggyback). Los mensajes NON también se aceptan.
- **Qué se guarda en `alertas_coap`:** `payload`, `tamano_bytes`, `enviado_en` (del `timestamp` de la alerta), `tipo_mensaje` (`CON` o `NON`) y `message_id`. Las alertas rechazadas no se guardan.
- **Importante:** CoAP usa UDP. Si el puerto se publica sin `/udp` (por ejemplo `5683:5683`), el ESP32 no llega y el error es confuso. En `compose.yaml` ya está como `5683:5683/udp`.

## Con Docker

Todos los comandos se ejecutan desde la **raíz del repositorio**.

### 1. Levantar

```bash
cp .env.example .env          # ajuste las claves
docker compose up -d --build  # levanta la base de datos (db) y el servidor (coap)
```

### 2. Comprobar que arrancó

```bash
docker compose logs -f coap
```

Debe aparecer `CoAP server listening on UDP 5683`. El servidor crea las tablas que falten al arrancar. Deje esta terminal abierta para ver las alertas que llegan.

### 3. Probar

En otra terminal, también en la raíz del repo, prepare el cliente:

```bash
python -m venv .venv
source .venv/bin/activate
pip install aiocoap
```

Y ejecute el script:

```bash
python servers/coap/smoke.py
```

Al final debe decir `8/8 pruebas correctas`.

### 4. Ver lo guardado

```bash
docker compose exec db psql -U postgres alertas -c "select id, tipo_mensaje, message_id, payload from alertas_coap order by id desc limit 5"
```

Cambie `postgres` y `alertas` si en su `.env` el usuario y la base son otros.

### Detener

```bash
docker compose down        # conserva los datos
docker compose down -v     # borra también los datos de la base
```

Si Docker responde `permission denied`, agréguese al grupo con `sudo usermod -aG docker $USER` y cierre sesión y vuelva a entrar.

## Sin Docker (local)

Necesita una PostgreSQL accesible. Lo más simple es levantar solo la base con Docker (`docker compose up -d db`); si tiene una instalada, cree en ella la base `alertas`.

Desde la **raíz del repositorio**:

### 1. Instalar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r servers/coap/requirements-dev.txt
```

### 2. Configurar

```bash
export DATABASE_URL=postgresql+psycopg://postgres:CLAVE@localhost:5433/alertas
export PYTHONPATH=$PWD
```

- Use el usuario, la clave y el puerto de su `.env` (`POSTGRES_PUERTO`).
- No use el `DATABASE_URL` del `.env` tal cual: apunta al host `db`, que solo existe dentro de Docker.
- `PYTHONPATH` debe ser la ruta absoluta de la raíz; con una ruta relativa falla con `No module named 'common'`.

### 3. Ejecutar el servidor

```bash
python servers/coap/app.py
```

Al arrancar crea las tablas que falten. Si el contenedor `coap` está arriba, deténgalo antes (`docker compose stop coap`): ambos usan el puerto UDP 5683.

### 4. Probar

En otra terminal, con el entorno virtual activado:

```bash
python servers/coap/smoke.py
```

### 5. Tests automáticos

```bash
cd servers/coap
pytest
```

No necesitan base de datos ni servidor en ejecución.

## Script de prueba (`smoke.py`)

Envía varias alertas y comprueba las respuestas: alerta válida CON (debe llegar con ACK), válida NON, cuatro tipos de alerta inválida, ruta desconocida y una serie de alertas CON seguidas para ver la latencia.

```bash
python servers/coap/smoke.py                          # contra localhost:5683
python servers/coap/smoke.py --host 192.168.1.50      # contra otra máquina
python servers/coap/smoke.py --repeat 100             # 100 alertas seguidas
```

Termina con código 0 si todas las pruebas pasan y 1 si alguna falla. Cada ejecución guarda alertas reales en la base de datos (las válidas), así que conviene vaciar la tabla antes de un experimento formal.

## Probar con otras herramientas

Thunder Client y Postman no sirven: no soportan CoAP. Alternativas:

```bash
pip install aiocoap
aiocoap-client -m POST coap://localhost/alert --payload '{"device_id":"esp32-01","sequence":1,"timestamp":1760000000000}'
aiocoap-client -m POST coap://localhost/alert --non --payload '{"device_id":"esp32-01","sequence":2,"timestamp":1760000000000}'
```

`--non` envía el mensaje como NON; sin él se envía como CON. Desde el ESP32 use `coap://IP_DEL_HOST:5683/alert`.
