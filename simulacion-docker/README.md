# Simulación: detección de caídas — HTTP vs MQTT vs CoAP

Un dispositivo (ESP32 + MPU6050 emulado) envía la misma alerta de caída a tres
servidores, bajo cuatro condiciones de red creadas con `tc netem`.

| Contenedor      | Rol                                   | Tecnología        | Puerto   |
|-----------------|---------------------------------------|-------------------|----------|
| `dispositivo`   | Detecta la caída y envía la alerta    | Python            | —        |
| `servidor-http` | Servidor A                            | Flask (waitress)  | TCP 5000 |
| `broker` + `receptor-mqtt` | Servidor B (broker + centro de auxilio) | Mosquitto + paho | TCP 1883 |
| `servidor-coap` | Servidor C                            | aiocoap           | UDP 5683 |
| `analizar`      | Tablas, CSV y gráfico                 | Python + SQLite   | —        |

## Ejecutar

```
docker compose run --rm dispositivo
docker compose run --rm analizar
```

La primera vez tarda unos minutos (descarga y construye la imagen). Los
resultados quedan en la carpeta `resultados/`:

- `resumen.csv`: una fila por escenario y protocolo (entrega, latencia, bytes, CPU)
- `detalle.csv`: una fila por alerta
- `resultados.db`: base de datos SQLite (tablas `envios` y `llegadas`)
- `comparativa.png`: gráfico comparativo

Otros comandos:

```
docker compose logs servidor-http receptor-mqtt servidor-coap   # ver los servidores
docker stats                                                     # CPU y memoria por contenedor
docker compose down                                              # apagar (los datos se conservan)
docker compose down -v                                           # apagar y borrar los datos
docker compose build                                             # reconstruir si cambias algo en app/
```

## Cambiar el experimento

- `.env`: número de alertas, tiempo máximo, conexión nueva o persistente,
  QoS de MQTT (0, 1, 2) y tipo de mensaje CoAP (CON, NON).
- `escenarios.json`: condiciones de red. Cada valor son los parámetros de
  `tc netem` (ejemplo: `delay 300ms 50ms loss 15%`). Para pérdida en ráfagas:
  `loss gemodel 10% 30%`.

Cada ejecución del dispositivo es una "corrida" nueva; `analizar` resume la última.

## Qué se mide

- **Entrega**: porcentaje de alertas que llegaron al servidor.
- **Latencia**: hora de llegada al servidor menos hora de envío (todos los
  contenedores usan el reloj del mismo equipo). En MQTT incluye el paso por el broker.
- **Confirmación**: el dispositivo recibió la respuesta (200 de HTTP, PUBACK de
  MQTT, respuesta de CoAP) antes de `TIEMPO_MAX`.
- **Bytes de red**: tráfico total del dispositivo por alerta (ida y vuelta, con
  cabeceras Ethernet/IP/TCP/UDP, establecimiento de conexión, ACK y retransmisiones).
- **CPU**: tiempo de procesador del dispositivo por alerta.

## Condiciones del experimento (para el informe)

- La degradación se aplica en ambos sentidos: en la salida del dispositivo y en
  la salida de cada servidor. `loss 15%` es 15 % por sentido.
- El orden de los protocolos rota en cada caída y las alertas se envían de una en una.
- Con `CONEXION=nueva` HTTP y MQTT abren una conexión TCP por alerta (dispositivo
  que despierta, envía y vuelve a dormir). CoAP no tiene conexión.
- Sin cifrado (TLS/DTLS), como indica la sección 6.5.
- El receptor MQTT está en el mismo equipo que el broker, sin degradación entre ellos.
