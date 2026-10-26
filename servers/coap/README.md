# Servidor CoAP

Recibe alertas por CoAP sobre UDP, responde con ACK a los mensajes confirmables (CON) y guarda cada alerta válida en la tabla `alertas_coap` de PostgreSQL.

| Archivo       | Para qué sirve                                                  |
| ------------- | --------------------------------------------------------------- |
| `app.py`      | Servidor (aiocoap). Recurso `POST /alert` en el puerto UDP 5683 |
| `smoke.py`    | Script de prueba manual contra un servidor en ejecución         |
| `tests/test_coap.py` | Tests automáticos (en la carpeta `tests/` de la raíz, no necesitan base de datos) |
| `Dockerfile`  | Imagen del servicio, se construye desde la raíz del repo        |

## Cómo funciona

- **Ruta:** `POST coap://HOST:5683/alert`
- **Cuerpo (JSON):** `device_id`, `sequence` y `timestamp` son obligatorios; hay campos opcionales adicionales (ver `common/schemas/alert.py` y el README principal) y no se aceptan otros.

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
- **Qué se guarda en `alertas_coap`:** `payload`, `tamano_bytes`, `enviado_en` (del `timestamp` de la alerta), `perfil_red` (de `NETWORK_PROFILE`), `tipo_mensaje` (`CON` o `NON`) y `message_id`. Las alertas rechazadas no se guardan.
- **Importante:** CoAP usa UDP. Si el puerto se publica sin `/udp` (por ejemplo `5683:5683`), el ESP32 no llega y el error es confuso. En `compose.yaml` ya está como `5683:5683/udp`.

## Con Docker

Todos los comandos se ejecutan desde la **raíz del repositorio**.

### 1. Levantar

```bash
cp .env.example .env          # ajuste las claves
docker compose up -d --build db coap  # solo la base de datos y este servidor
```

Para levantar todos los servicios del proyecto a la vez: `docker compose up -d --build` (ver el README principal).

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
docker compose exec db psql -U USUARIO BASE -c "select id, tipo_mensaje, message_id, payload from alertas_coap order by id desc limit 5"
```

Reemplace `USUARIO` y `BASE` por `POSTGRES_USER` y `POSTGRES_DB` de su `.env`.

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
pip install -e ".[dev,coap]"
```

### 2. Configurar

```bash
export DATABASE_URL=postgresql+psycopg://postgres:CLAVE@localhost:5433/alertas
```

- Use el usuario, la clave y el puerto de su `.env` (`POSTGRES_PUERTO`).
- No use el `DATABASE_URL` del `.env` tal cual si apunta al host `db`: ese nombre solo existe dentro de Docker.

### 3. Ejecutar el servidor

```bash
python -m servers.coap.app
```

Al arrancar crea las tablas que falten. Si el contenedor `coap` está arriba, deténgalo antes (`docker compose stop coap`): ambos usan el puerto UDP 5683.

### 4. Probar

En otra terminal, con el entorno virtual activado:

```bash
python servers/coap/smoke.py
```

### 5. Tests automáticos

```bash
pytest tests/test_coap.py
```

No necesitan base de datos ni servidor en ejecución. (`pytest` sin argumentos ejecuta las pruebas de todo el proyecto.)

## Dentro de todo el proyecto

Este servidor es el servicio `coap` de `compose.yaml` y comparte la base de datos con `http` y `mqtt-subscriber`: cada protocolo guarda en su tabla (`alertas_coap`, `alertas_http`, `alertas_mqtt`) con el mismo formato de alerta, y `python -m common.db.export` las exporta juntas. Con `docker compose up -d --build` quedan los tres servidores arriba. Si otro servicio ya usa el puerto UDP 5683 del equipo, el contenedor no arranca.

## Script de prueba (`smoke.py`)

Envía varias alertas y comprueba las respuestas: alerta válida CON (debe llegar con ACK), válida NON, cuatro tipos de alerta inválida, ruta desconocida y una serie de alertas CON seguidas para ver la latencia.

```bash
python servers/coap/smoke.py                          # contra localhost:5683
python servers/coap/smoke.py --host 192.168.1.50      # contra otra máquina
python servers/coap/smoke.py --repeat 100             # 100 alertas seguidas
```

Los logs del servidor usan el formato estándar del proyecto (ver «Logging» en el README principal).

Termina con código 0 si todas las pruebas pasan y 1 si alguna falla. Cada ejecución guarda alertas reales en la base de datos (las válidas), así que conviene vaciar la tabla antes de un experimento formal.

## Probar con otras herramientas

Thunder Client y Postman no sirven: no soportan CoAP. Alternativas:

```bash
pip install aiocoap
aiocoap-client -m POST coap://localhost/alert --payload '{"device_id":"esp32-01","sequence":1,"timestamp":1760000000000}'
aiocoap-client -m POST coap://localhost/alert --non --payload '{"device_id":"esp32-01","sequence":2,"timestamp":1760000000000}'
```

`--non` envía el mensaje como NON; sin él se envía como CON. Desde el ESP32 use `coap://IP_DEL_HOST:5683/alert`.
