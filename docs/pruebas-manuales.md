# Pruebas manuales rápidas

Guía para probar los tres servidores copiando y pegando comandos en la terminal. Cada bloque es independiente: no depende de variables definidas en otro bloque ni de otra terminal.

Todos los comandos se ejecutan desde la **raíz del repositorio**. Las explicaciones largas están en el [README](../README.md) y en el `README.md` de cada servidor.

## 0. Preparación (una sola vez)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,http,coap,mqtt]"
cp -n .env.example .env
```

Edite `.env` y cambie `cambiar_esta_clave` en `POSTGRES_PASSWORD` y en `DATABASE_URL`. `cp -n` no pisa un `.env` que ya exista.

Si tiene contenedores de versiones anteriores del proyecto ocupando puertos:

```bash
docker ps
docker compose down
```

## 1. Con Docker: levantar todo

```bash
docker compose up -d --build
docker compose ps
```

Deben estar arriba `db` (healthy), `http`, `coap`, `mosquitto` y `mqtt-subscriber`. Los logs de todos:

```bash
docker compose logs -f
```

(`Ctrl+C` para salir; los servicios siguen corriendo.)

## 2. HTTP

Alerta válida. Debe responder `200` y `true`:

```bash
curl -i -X POST http://localhost:8000/alert -H 'Content-Type: application/json' -d "{\"device_id\":\"esp32-01\",\"sequence\":1,\"timestamp\":$(date +%s%3N)}"
```

Alerta con campos opcionales. `200` y `true`:

```bash
curl -i -X POST http://localhost:8000/alert -H 'Content-Type: application/json' -d "{\"device_id\":\"esp32-01\",\"sequence\":2,\"timestamp\":$(date +%s%3N),\"event_type\":\"fall\",\"battery_level\":80,\"acceleration\":2.5}"
```

Alerta inválida, falta `sequence` y `timestamp`. `400` y `false`:

```bash
curl -i -X POST http://localhost:8000/alert -H 'Content-Type: application/json' -d '{"device_id":"esp32-01"}'
```

Campo extra. `400` y `false`:

```bash
curl -i -X POST http://localhost:8000/alert -H 'Content-Type: application/json' -d "{\"device_id\":\"esp32-01\",\"sequence\":3,\"timestamp\":$(date +%s%3N),\"foo\":1}"
```

Tipo incorrecto (`sequence` como texto). `400` y `false`:

```bash
curl -i -X POST http://localhost:8000/alert -H 'Content-Type: application/json' -d "{\"device_id\":\"esp32-01\",\"sequence\":\"3\",\"timestamp\":$(date +%s%3N)}"
```

Ruta que no existe. `404`:

```bash
curl -i -X POST http://localhost:8000/http/alert
```

Ver el motivo de los rechazos y lo guardado:

```bash
docker compose logs --tail 10 http
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB" -c "select id, ip_origen, content_type, tamano_bytes, payload from alertas_http order by id desc limit 5"'
```

## 3. MQTT

Publicar tres alertas válidas con QoS 0, 1 y 2:

```bash
for q in 0 1 2; do docker compose exec -T mosquitto mosquitto_pub -q $q -t alert -m "{\"device_id\":\"esp32-01\",\"sequence\":$q,\"timestamp\":$(date +%s%3N)}"; done
```

Alerta inválida. No se guarda y el log muestra un `WARNING`:

```bash
docker compose exec -T mosquitto mosquitto_pub -q 1 -t alert -m '{"device_id":"esp32-01"}'
```

Ver el log del suscriptor y lo guardado (la columna `qos` debe ser 0, 1 y 2):

```bash
docker compose logs --tail 10 mqtt-subscriber
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB" -c "select id, topic, qos, tamano_bytes, payload from alertas_mqtt order by id desc limit 5"'
```

## 4. CoAP

Script de prueba, 8 comprobaciones (deben pasar las 8). Necesita el entorno virtual activado (paso 0):

```bash
source .venv/bin/activate && python servers/coap/smoke.py
```

20 alertas seguidas:

```bash
source .venv/bin/activate && python servers/coap/smoke.py --repeat 20
```

Una alerta suelta con `aiocoap-client`:

```bash
source .venv/bin/activate && aiocoap-client -m POST coap://localhost/alert --content-format application/json --payload "{\"device_id\":\"esp32-01\",\"sequence\":1,\"timestamp\":$(date +%s%3N)}"
```

Ver el log y lo guardado:

```bash
docker compose logs --tail 10 coap
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB" -c "select id, tamano_bytes, payload from alertas_coap order by id desc limit 5"'
```

## 5. Comparar los tres protocolos

Cuántas filas hay en cada tabla:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB" -c "select '"'"'http'"'"' as protocolo, count(*) from alertas_http union all select '"'"'coap'"'"', count(*) from alertas_coap union all select '"'"'mqtt'"'"', count(*) from alertas_mqtt"'
```

Exportar a CSV (crea la carpeta `results/export_<fecha>/` con `alerts_all.csv`, `alerts_http.csv`, `alerts_coap.csv` y `alerts_mqtt.csv`). Va desde su máquina, así que necesita una `DATABASE_URL` con host `localhost` y el puerto `POSTGRES_PUERTO` (ver «Errores» más abajo):

```bash
source .venv/bin/activate && set -a && source <(grep -E '^POSTGRES_' .env) && set +a && DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PUERTO/$POSTGRES_DB" python -m common.db.export
```

`latency_ms` debe ser un número pequeño y positivo en los tres protocolos.

## 6. Sin Docker: un servidor suelto

Levanta solo la base y el broker, y detiene los servidores de Docker para no repetir puertos:

```bash
docker compose up -d db mosquitto && docker compose stop http coap mqtt-subscriber
```

Cada servidor, en su propia terminal, desde la raíz. El bloque arma la `DATABASE_URL` correcta a partir de su `.env` sin tocar el archivo:

```bash
source .venv/bin/activate && set -a && source <(grep -E '^POSTGRES_' .env) && set +a && export DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PUERTO/$POSTGRES_DB" MQTT_BROKER_HOST=localhost && python -m servers.http.app
```

Cambie el final por `python -m servers.coap.app` o `python -m servers.mqtt.subscriber` para los otros dos. Las pruebas de las secciones 2 a 4 son las mismas, pero los logs salen en la terminal del servidor (no con `docker compose logs`).

Para volver a la pila completa:

```bash
docker compose up -d
```

## 7. Tests automáticos y estilo

Sin base de datos (107 pruebas):

```bash
source .venv/bin/activate && pytest
```

Estilo:

```bash
source .venv/bin/activate && ruff check . && ruff format --check --exclude "*.md" .
```

Integración, con una base desechable (**borra las tablas de alertas** de esa base):

```bash
docker run -d --name pg-test -e POSTGRES_PASSWORD=clave -e POSTGRES_DB=alertas -p 5499:5432 postgres:16 && sleep 5 && source .venv/bin/activate && TEST_DATABASE_URL=postgresql://postgres:clave@localhost:5499/alertas pytest -m integration; docker rm -f pg-test
```

## 8. Apagar

```bash
docker compose down       # conserva los datos
docker compose down -v    # borra también la base
```

## Errores frecuentes y cómo corregirlos

| Síntoma | Causa | Solución |
|---|---|---|
| HTTP `400` y en el log `Invalid JSON: expected value at line 1 column 50` | El JSON llegó con `"timestamp":` vacío porque se usó una variable (`$TS`) sin definir | Use los comandos de este documento, que llevan `$(date +%s%3N)` dentro |
| `400` y `timestamp: Input should be a valid integer` | El `timestamp` trae decimales o está en segundos | Debe ser un entero en milisegundos: `date +%s%3N` |
| `400` y `unexpected fields` | El cuerpo trae un campo que no es del formato de alerta | Quite el campo (ver el README principal, «Mensaje de alerta») |
| `404` en `/http/alert` | Ruta antigua | Use `/alert` |
| `port is already allocated` (1883, 5683, 8000 o `POSTGRES_PUERTO`) | Otro contenedor o programa usa ese puerto | `docker ps` y detenga el otro, o `docker compose down` |
| `password authentication failed for user "alertas"` al ejecutar sin Docker | La `DATABASE_URL` de su `.env` apunta al puerto 5432, donde puede haber un PostgreSQL del sistema, con un usuario que no es el de Docker | Use el bloque de la sección 6 (arma la URL con `POSTGRES_USER` y `POSTGRES_PUERTO`) o corrija la línea de `DATABASE_URL` en `.env` |
| `failed to resolve host 'db'` | Se ejecutó un servidor fuera de Docker con una `DATABASE_URL` que apunta a `db` | `db` solo existe dentro de Docker: use `localhost` y `POSTGRES_PUERTO` |
| `Connecting to ...` y no avanza (MQTT) | El broker no responde en `MQTT_BROKER_HOST`/`MQTT_BROKER_PORT` | Fuera de Docker use `MQTT_BROKER_HOST=localhost` y `docker compose up -d mosquitto` |
| MQTT guarda cada mensaje dos veces | Hay dos suscriptores (el de Docker y uno local) | `docker compose stop mqtt-subscriber` |
| Cambió el usuario o la clave de Postgres en `.env` y no surte efecto | El volumen conserva las credenciales con que se creó | `docker compose down -v` (borra los datos) |
| `ModuleNotFoundError` al ejecutar | Entorno virtual sin activar o paquete sin instalar | `source .venv/bin/activate && pip install -e ".[dev,http,coap,mqtt]"` |
| `relation "alertas_http" does not exist` | Las tablas aún no existen | Se crean al arrancar cualquier servidor; revise sus logs |
