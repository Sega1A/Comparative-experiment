# Servidor HTTP

Recibe alertas por HTTP, las valida con el formato común (`AlertDTO`) y guarda cada alerta válida en la tabla `alertas_http` de PostgreSQL.

| Archivo | Para qué sirve |
| --- | --- |
| `app.py` | Servidor (Flask). Ruta `POST /alert` en el puerto 8000 |
| `Dockerfile` | Imagen del servicio (gunicorn), se construye desde la raíz del repo |
| `tests/test_http.py` | Tests automáticos (en la carpeta `tests/` de la raíz, no necesitan base de datos) |

## Cómo funciona

- **Ruta:** `POST http://HOST:8000/alert`
- **Cuerpo (JSON):** `device_id`, `sequence` y `timestamp` son obligatorios; hay campos opcionales adicionales (ver `common/schemas/alert.py` y el README principal) y no se aceptan otros.

  ```json
  { "device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000 }
  ```

  `device_id` es texto; `sequence` y `timestamp` (milisegundos) son enteros.

- **Respuestas:**

  | Situación | Código | Cuerpo |
  | --- | --- | --- |
  | Alerta válida y guardada | `200` | `true` |
  | Alerta inválida o JSON malformado | `400` | `false` |
  | Error al guardar en la base de datos | `500` | `false` |
  | Otra ruta | `404` | |

- **Qué se guarda en `alertas_http`:** `payload`, `tamano_bytes` (largo del cuerpo recibido), `enviado_en` (del `timestamp` de la alerta), `perfil_red` (de `NETWORK_PROFILE`), `ip_origen` y `content_type`. Las alertas rechazadas no se guardan.
- El servidor no exige la cabecera `Content-Type: application/json`; valida el contenido del cuerpo.

## Con Docker

Todos los comandos se ejecutan desde la **raíz del repositorio**.

### 1. Levantar

```bash
cp .env.example .env                 # ajuste las claves
docker compose up -d --build db http # solo la base de datos y este servidor
```

Para levantar todos los servicios del proyecto a la vez: `docker compose up -d --build`.

### 2. Comprobar que arrancó

```bash
docker compose logs -f http
```

Deben aparecer las líneas de gunicorn (`Booting worker`). El servidor crea las tablas que falten al arrancar.

### 3. Probar

```bash
curl -i -X POST http://localhost:8000/alert \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"esp32-01","sequence":1,"timestamp":1760000000000}'
```

Debe responder `200` con `true`. Con un cuerpo inválido (por ejemplo sin `sequence`) responde `400` con `false`, y el motivo aparece en el log:

```
2026-10-23 16:50:38,464 WARNING  servers.http.app: Rejected alert: sequence: Field required
```

También sirven Postman o Thunder Client.

### 4. Ver lo guardado

```bash
docker compose exec db psql -U USUARIO BASE -c "select id, ip_origen, content_type, tamano_bytes, payload from alertas_http order by id desc limit 5"
```

Reemplace `USUARIO` y `BASE` por `POSTGRES_USER` y `POSTGRES_DB` de su `.env`.

### Detener

```bash
docker compose down        # conserva los datos
docker compose down -v     # borra también los datos de la base
```

## Sin Docker (local)

Necesita una PostgreSQL accesible. Lo más simple es levantar solo la base con Docker (`docker compose up -d db`).

Desde la **raíz del repositorio**:

### 1. Instalar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,http]"
```

### 2. Configurar

```bash
export DATABASE_URL=postgresql+psycopg://postgres:CLAVE@localhost:5433/alertas
```

- Use el usuario, la clave y el puerto de su `.env` (`POSTGRES_PUERTO`).
- No use el `DATABASE_URL` del `.env` tal cual si apunta al host `db`: ese nombre solo existe dentro de Docker.

### 3. Ejecutar el servidor

```bash
python -m servers.http.app
```

Es el servidor de desarrollo de Flask, en el puerto 8000. Si el contenedor `http` está arriba, deténgalo antes (`docker compose stop http`). Para ejecutarlo como en Docker: `gunicorn --bind 0.0.0.0:8000 "servers.http.app:create_wsgi_app()"`.

### 4. Probar

Con el `curl` de arriba.

### 5. Tests automáticos

```bash
pytest tests/test_http.py
```

No necesitan base de datos ni servidor en ejecución. (`pytest` sin argumentos ejecuta las pruebas de todo el proyecto.)

## Dentro de todo el proyecto

Este servidor es el servicio `http` de `compose.yaml` y comparte la base de datos con `coap` y `mqtt-subscriber`: cada protocolo guarda en su tabla (`alertas_http`, `alertas_coap`, `alertas_mqtt`) con el mismo formato de alerta, y `python -m common.db.export` las exporta juntas. Con `docker compose up -d --build` quedan los tres servidores arriba.

## Problemas frecuentes

| Síntoma | Causa probable |
| --- | --- |
| `404` en `/http/alert` | La ruta anterior. Ahora es `/alert` |
| `400` con `unexpected fields` | El cuerpo trae un campo que no está en el formato de alerta |
| El contenedor se reinicia con `failed to resolve host 'db'` | Se ejecutó fuera de Compose con un `DATABASE_URL` que apunta a `db` |
| `Bind ... 8000 failed: port is already allocated` | Otro programa usa el puerto 8000 |
