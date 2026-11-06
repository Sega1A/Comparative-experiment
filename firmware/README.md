# Firmware del ESP32

Detecta caídas e inmovilidad con el MPU6050 y envía la alerta por HTTP, MQTT o CoAP a los servidores de `servers/`. Está hecho con PlatformIO (framework Arduino 3.x).

## Hardware

| Componente | Pin del ESP32 |
|---|---|
| MPU6050 SDA / SCL | D21 / D22 |
| MPU6050 VCC / GND | 3V3 / GND |
| Buzzer (+) | D19 (la otra pata a GND). Se maneja con PWM a 2,7 kHz: sirve activo o pasivo |
| LED de estado | GPIO2 (LED azul integrado en la placa) |
| Botón | BOOT de la placa (GPIO0) |

Notas de la validación (26/10/2026):
- El módulo responde `WHO_AM_I = 0x70`: es un clon compatible (tipo MPU-6500), con los mismos registros de acelerómetro.
- La placa usa un chip USB CH9102, que en Linux aparece como `/dev/ttyACM0`.
- El buzzer no sonaba con un nivel alto fijo (es pasivo), por eso se maneja con PWM. Al arrancar da un pitido corto de confirmación.
- Un LED verde externo con 220 Ω no encendía con 3,3 V (su tensión directa ronda 3 V), por eso se usa el LED integrado.

## Primera vez

1. Copie `include/config.example.h` como `include/config.h` y complete:
   - el WiFi (solo de **2,4 GHz**),
   - la IP de la laptop que corre `docker compose up` (`hostname -I`),
   - el `DEVICE_ID`.

   `config.h` no se sube a Git.
2. En VS Code, abra **esta carpeta** (`firmware/`), no la raíz del repositorio.
3. En la barra de abajo, elija el entorno (`env:mqtt`, `env:http`, `env:coap` o `env:operativo`). Luego compile con ✓, suba con → y abra el monitor con el enchufe.

Por terminal: `pio run -e coap -t upload && pio device monitor`.

## Entornos

| Entorno | Modo | Para qué |
|---|---|---|
| `http`, `mqtt`, `coap` | Experimento | Medir. Un único protocolo y la misma política de reintentos en los tres. |
| `operativo` | Operativo | La demo. Si un protocolo falla `FAILOVER_AFTER` veces seguidas, pasa al siguiente (`FAILOVER_ORDER` en `src/protocols.cpp`). |

## Qué hace cuando el envío falla

1. **La alerta no se pierde.** Se guarda en la flash (NVS) apenas se detecta, y sale de la cola solo cuando el servidor confirma. Sobrevive a reinicios.
2. **Cada intento tiene un límite** de `ATTEMPT_TIMEOUT_MS` (10 s). Dentro de ese límite actúa la fiabilidad propia de cada protocolo:

   | Protocolo | Confirmación válida | Fiabilidad dentro del intento |
   |---|---|---|
   | HTTP | `200` con cuerpo `true` | Retransmisiones de TCP |
   | MQTT | `PUBACK` del broker (QoS 1) | TCP + QoS 1 |
   | CoAP | `2.04` | Mensaje CON con retransmisión exponencial (RFC 7252): a los 2–3 s y a los 6–9 s. Con el límite de 10 s caben 2 retransmisiones; las 4 de la RFC necesitarían ~93 s |

3. **Entre intentos**, espera 1, 2, 4, 8… s (±20 % al azar, tope de 30 s). Reenvía con el **mismo `sequence`**, así el par `(device_id, sequence)` identifica duplicados.
4. **Sin WiFi**, el intento espera la reconexión dentro del mismo límite y cuenta como fallido (`sin_wifi`).
5. **No reintenta si el servidor rechaza el mensaje** (`400` en HTTP, `4.xx` en CoAP): repetir no lo arreglaría.
6. **En modo experimento**, tras `MAX_ATTEMPTS` (5) la alerta se da por **perdida**: así se mide la tasa de entrega. **En modo operativo** nunca se rinde.
7. **Aviso local:** el buzzer suena 10 s (o hasta presionar BOOT) y el LED parpadea rápido mientras haya alertas sin confirmar.

Todos los valores están en `include/settings.h` y deben declararse en el informe.

Hay dos diferencias que el análisis debe tener en cuenta:
- **El PUBACK de MQTT** confirma la llegada al broker, no el guardado en la base.
- **La respuesta CoAP puede llegar de dos formas.** Si la base tarda, aiocoap responde con un ACK vacío y luego la respuesta aparte; el firmware maneja ambos casos.

## Detección

Usa umbrales sobre `|a|` (Bourke et al., 2007), a 50 Hz:
1. **Caída libre:** `|a|` baja de 0,5 g.
2. **Impacto:** `|a|` supera 2,5 g, como máximo 1 s después.
3. Pasados 2 s del impacto, se genera la alerta `fall`, con el pico de aceleración.
4. Si después la persona queda **quieta 15 s** (`||a| − 1 g| < 0,15 g`), se genera la alerta `immobility`.

Si ocurre otra caída mientras vigila la inmovilidad de la anterior, se detecta igual.

Para calibrar, el monitor muestra líneas `SENSOR` con el pico y el mínimo de cada golpe, aunque no llegue a ser caída: `golpe_sin_caida_libre`, `caida_libre_sin_impacto_suficiente`, `caida_detectada`.

El botón BOOT (pulsación corta) significa "estoy bien": silencia la alarma y deja de vigilar.

## Botón y comandos del monitor serie

| Acción | Efecto |
|---|---|
| BOOT corto | Estoy bien: silencia la alarma |
| BOOT largo (2 s) | Inicia/detiene una ráfaga de 30 alertas de prueba |
| `f` | Simula una caída |
| `t` | Envía una alerta de prueba |
| `r` | Ráfaga on/off |
| `s` | Estado: WiFi, RSSI, hora, cola, contadores |
| `b` | Prueba el buzzer 1 s |
| `h` | Ayuda |

En la ráfaga, cada alerta sale 2 s después de que terminó la anterior, para que las mediciones sean independientes.

## Registro para el análisis

El monitor guarda todo en un `.log` (filtro `log2file`). Hay dos tipos de línea CSV:

```
ATTEMPT,protocolo,secuencia,intento,estado,ms,rssi,retransmisiones_coap,error
RESULT,modo,protocolo,secuencia,evento,resultado,intentos,ms_ultimo_intento,ms_total,rssi,bytes_payload,heap_minimo,error
```

- **Tasa de entrega:** `RESULT` con `entregada` sobre el total.
- **Latencia en el dispositivo:** `ms_ultimo_intento` es el tiempo de ida y vuelta del intento exitoso. `ms_total` incluye los reintentos.
- **Latencia en el servidor:** `latency_ms` de `python -m common.db.export`. Solo es válida si el ESP32 tenía hora NTP (`ntp=si` en las líneas `EVENT`).
- **Recursos:** `heap_minimo` (RAM libre mínima desde el arranque) y `bytes_payload`.

## Archivos

```
firmware/
├── platformio.ini          # entornos http, mqtt, coap, operativo
├── include/
│   ├── config.example.h    # copiar a config.h (WiFi, IP del servidor)
│   ├── settings.h          # parámetros del experimento
│   └── *.h
└── src/
    ├── main.cpp            # tareas, cola, reintentos, botón, buzzer, LED
    ├── protocols.cpp       # un intento por HTTP, MQTT o CoAP
    ├── fall_detector.cpp   # máquina de estados de la detección
    ├── alert_queue.cpp     # cola persistente en NVS
    ├── alert.cpp           # JSON compatible con AlertDTO
    └── log.cpp
```
