# Servidor MQTT

Mosquitto (el broker) más un suscriptor en Python. El suscriptor escucha el topic de alertas, valida cada mensaje con el formato común (`AlertDTO`) y guarda cada alerta válida en la tabla `alertas_mqtt` de PostgreSQL.

| Archivo | Para qué sirve |
| --- | --- |
| `subscriber.py` | Suscriptor (paho-mqtt). Escucha el topic `alert` |
| `mosquitto.conf` | Configuración del broker (puerto 1883, conexiones anónimas) |
| `Dockerfile` | Imagen del suscriptor, se construye desde la raíz del repo |
| `tests/test_mqtt.py` | Tests automáticos (en la carpeta `tests/` de la raíz, no necesitan broker ni base de datos) |

## Cómo funciona

- **Topic:** `alert` (se cambia con `MQTT_TOPIC`). El broker es el servicio `mosquitto` de Compose.
- **Mensaje (JSON):** `device_id`, `sequence` y `timestamp` son obligatorios; hay campos opcionales adicionales (ver `common/schemas/alert.py` y el README principal) y no se aceptan otros.

  ```json
  { "device_id": "esp32-01", "sequence": 1, "timestamp": 1760000000000 }
  ```

  `device_id` es texto; `sequence` y `timestamp` (milisegundos) son enteros.

- **Qué hace con cada mensaje:**

  | Situación | Resultado |
  | --- | --- |
  | Mensaje válido | Se guarda y queda un `INFO` en el log |
  | Mensaje inválido o que no es JSON | Se descarta y queda un `WARNING` con el motivo |
  | Error al guardar en la base de datos | Queda un `ERROR` con el detalle; el suscriptor sigue funcionando |

- **Qué se guarda en `alertas_mqtt`:** `payload`, `tamano_bytes` (largo del mensaje recibido), `enviado_en` (del `timestamp` de la alerta), `perfil_red` (de `NETWORK_PROFILE`), `topic` y `qos`.
- **QoS:** el suscriptor se suscribe con QoS 2. El broker entrega cada mensaje con el menor entre el QoS con que se publicó y el de la suscripción, así que la columna `qos` guarda el QoS con que publicó el dispositivo (0, 1 o 2).
- **Duplicados:** con QoS 1 el broker puede entregar un mensaje más de una vez y se guardaría una fila repetida (distinguible por `device_id` y `sequence`). Hoy no se eliminan.
- **Conexión:** si el broker aún no está disponible al arrancar, el suscriptor reintenta; al reconectarse vuelve a suscribirse solo.

## Con Docker

Todos los comandos se ejecutan desde la **raíz del repositorio**.

### 1. Levantar

```bash
cp .env.example .env                                      # ajuste las claves
docker compose up -d --build db mosquitto mqtt-subscriber # base, broker y suscriptor
```

Para levantar todos los servicios del proyecto a la vez: `docker compose up -d --build`.

### 2. Comprobar que arrancó

```bash
docker compose logs -f mqtt-subscriber
```

Debe aparecer `Subscribed to 'alert' (qos=2)`. El suscriptor crea las tablas que falten al arrancar.

### 3. Probar

Publique desde el propio contenedor del broker (QoS 0, 1 y 2):

```bash
for q in 0 1 2; do
  docker compose exec mosquitto mosquitto_pub -q $q -t alert \
    -m "{\"device_id\":\"esp32-01\",\"sequence\":$q,\"timestamp\":$(date +%s%3N)}"
done
```

El `timestamp` es en milisegundos (`date +%s%3N`). En el log del suscriptor debe aparecer, por cada mensaje:

```
2026-10-23 16:50:38,661 INFO     servers.mqtt.subscriber: Alert received: {'device_id': 'esp32-01', 'sequence': 0, 'timestamp': 1760000000000} (topic=alert, qos=0)
```

Un mensaje inválido no se guarda y deja un aviso:

```bash
docker compose exec mosquitto mosquitto_pub -q 1 -t alert -m '{"device_id":"esp32-01"}'
# WARNING  servers.mqtt.subscriber: Rejected alert on 'alert': sequence: Field required; timestamp: Field required
```

### 4. Ver lo guardado

```bash
docker compose exec db psql -U USUARIO BASE -c "select id, topic, qos, tamano_bytes, payload from alertas_mqtt order by id desc limit 5"
```

Reemplace `USUARIO` y `BASE` por `POSTGRES_USER` y `POSTGRES_DB` de su `.env`.

### Detener

```bash
docker compose down        # conserva los datos
docker compose down -v     # borra también los datos de la base
```

## Sin Docker (local)

Necesita una PostgreSQL y un broker MQTT accesibles. Lo más simple es levantarlos con Docker (`docker compose up -d db mosquitto`).

Desde la **raíz del repositorio**:

### 1. Instalar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,mqtt]"
```

### 2. Configurar

```bash
export DATABASE_URL=postgresql+psycopg://postgres:CLAVE@localhost:5433/alertas
export MQTT_BROKER_HOST=localhost
```

- Use el usuario, la clave y el puerto de su `.env` (`POSTGRES_PUERTO`).
- No use el `DATABASE_URL` ni el `MQTT_BROKER_HOST` del `.env` tal cual si apuntan a `db` o `mosquitto`: esos nombres solo existen dentro de Docker.

### 3. Ejecutar el suscriptor

```bash
python -m servers.mqtt.subscriber
```

Si el contenedor `mqtt-subscriber` está arriba, deténgalo antes (`docker compose stop mqtt-subscriber`): dos suscriptores guardarían cada mensaje dos veces.

### 4. Probar

Con los comandos `mosquitto_pub` de arriba (`docker compose exec mosquitto ...`), o con `mosquitto_pub` instalado en su máquina (`-h localhost`).

### 5. Tests automáticos

```bash
pytest tests/test_mqtt.py
```

No necesitan broker ni base de datos. (`pytest` sin argumentos ejecuta las pruebas de todo el proyecto.)

## Dentro de todo el proyecto

Este servidor son los servicios `mosquitto` y `mqtt-subscriber` de `compose.yaml` y comparte la base de datos con `http` y `coap`: cada protocolo guarda en su tabla (`alertas_mqtt`, `alertas_http`, `alertas_coap`) con el mismo formato de alerta, y `python -m common.db.export` las exporta juntas. Con `docker compose up -d --build` quedan los tres servidores arriba.

## Problemas frecuentes

| Síntoma | Causa probable |
| --- | --- |
| `WARNING ... timestamp: Input should be a valid integer` | El `timestamp` trae decimales (segundos, como `date +%s.%N`). Debe ser un entero en milisegundos |
| No llega nada al suscriptor | Se publicó en otro topic (el correcto es `alert`) o el suscriptor no está conectado |
| Se queda en `Connecting to ...` | El broker no está accesible en `MQTT_BROKER_HOST`/`MQTT_BROKER_PORT` |
| `Bind ... 1883 failed: port is already allocated` | Otro broker usa el puerto 1883 del equipo |
