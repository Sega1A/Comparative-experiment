# Trabajo 7 — MQTT vs. CoAP vs. HTTP para IoT

Banco de pruebas experimental para comparar los tres protocolos bajo condiciones
idénticas y con evidencia medible.

---

## 1. La idea en una frase

Los tres servidores hacen **exactamente el mismo trabajo** (reciben un payload y lo
devuelven). Un cliente los golpea N veces, cronometra cada ida y vuelta, y guarda
todo en un CSV. Después un script convierte ese CSV en tablas y gráficos.

Eso es todo. No hay app, no hay dashboard bonito, no hay sensores. El producto de
este trabajo **es el experimento**.

---

## 2. Qué mide y por qué

| Indicador del enunciado | Cómo se mide aquí | Estado |
|---|---|---|
| Latencia | `bench.py` cronometra el round-trip completo | ✅ MVP |
| Tamaño de mensajes | `capturar_trafico.sh` con tshark cuenta bytes reales | ✅ MVP |
| Consumo de recursos | `medir_recursos.py` muestrea `docker stats` | ✅ MVP |
| Fiabilidad | `escenario_red.sh` inyecta pérdida de paquetes | ✅ MVP |
| Escalabilidad | N clientes concurrentes | ⬜ Backlog (Sprint 3) |

### Por qué se mide ida y vuelta, y no solo el envío

Es la única forma de comparar peras con peras. HTTP y CoAP son petición/respuesta
por naturaleza. MQTT es publicación/suscripción y no responde nada. Para nivelar
la cancha se agregó un servicio de eco MQTT: el cliente publica en `bench/req`, el
eco republica en `bench/resp`, y el cliente mide cuánto tardó el viaje redondo.
Los tres protocolos terminan haciendo el mismo trabajo útil.

**Esto hay que justificarlo explícitamente en el capítulo de metodología.** Es la
decisión de diseño más discutible del trabajo y también la más defendible.

### Variantes que se miden

- `http` — HTTP/1.1 con keep-alive (la conexión TCP se reutiliza)
- `http-noka` — HTTP/1.1 abriendo conexión nueva cada vez (muestra el costo del handshake)
- `coap` — CoAP confirmable (CON) sobre UDP
- `mqtt-qos0` — sin garantía de entrega
- `mqtt-qos1` — al menos una vez
- `mqtt-qos2` — exactamente una vez

Incluir los tres QoS de MQTT vale oro para el informe: se ve el precio exacto de
la fiabilidad dentro de un mismo protocolo.

---

## 3. Arquitectura

```
                       ┌──────────────────────┐
                       │      bench.py        │
                       │  (cliente / sensor   │
                       │      simulado)       │
                       └───┬───────┬───────┬──┘
              HTTP/TCP:8000│  UDP:5683      │ MQTT/TCP:1883
                 ┌─────────┘       │        └─────────┐
                 ▼                 ▼                  ▼
        ┌────────────────┐ ┌──────────────┐  ┌─────────────────┐
        │  http-server   │ │ coap-server  │  │   mosquitto     │
        │   (FastAPI)    │ │  (aiocoap)   │  │    (broker)     │
        └────────────────┘ └──────────────┘  └────────┬────────┘
                                                      │ bench/req
                                                      ▼
                                             ┌─────────────────┐
                                             │   mqtt-echo     │
                                             │ (republica en   │
                                             │   bench/resp)   │
                                             └─────────────────┘
```

Todo corre en contenedores Docker en la misma red bridge.

---

## 4. Cómo correrlo

### Requisitos
- Docker y Docker Compose
- Python 3.10+ en tu máquina (el cliente corre fuera de Docker)

### Paso 1 — Levantar los servidores

```bash
docker compose up -d --build
docker compose ps          # los 4 servicios deben estar "running"
```

Verificar que responden:

```bash
curl http://localhost:8000/health
docker compose logs coap-server | tail -3
docker compose logs mqtt-echo | tail -3
```

### Paso 2 — Instalar el cliente

```bash
cd bench
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Paso 3 — Correr el experimento

```bash
python bench.py --n 200 --etiqueta corrida1
```

Salida esperada:

```
  -> http       payload=   16 B ... media=   0.72 ms  p95=   0.93 ms  perdida= 0.0%
  -> coap       payload=   16 B ... media=   0.36 ms  p95=   0.47 ms  perdida= 0.0%
  -> mqtt-qos0  payload=   16 B ... media=   0.18 ms  p95=   0.24 ms  perdida= 0.0%
  ...
```

### Paso 4 — Generar tablas y gráficos

```bash
python analizar.py --etiqueta corrida1
```

Genera en `resultados/`:
- `tabla_resumen.csv` → la tabla del capítulo 11 del informe
- `fig1_latencia_por_protocolo.png`
- `fig2_latencia_vs_payload.png`
- `fig3_distribucion.png`

### Paso 5 (opcional) — Recursos, tráfico y redes malas

```bash
# CPU/RAM: en otra terminal, mientras corre bench.py
python medir_recursos.py --segundos 300

# Bytes reales en la red (necesita tshark)
sudo ./capturar_trafico.sh 120

# Simular una red mala y repetir el experimento
sudo ./escenario_red.sh celular
python bench.py --n 200 --etiqueta celular
sudo ./escenario_red.sh limpiar
```

Comparar `corrida1` contra `celular` es donde aparecen los resultados más
interesantes del trabajo.

---

## 5. Datos de ejemplo incluidos

`resultados/resultados.csv` ya trae una corrida con etiqueta `demo` (2400
mediciones) para que puedas probar `analizar.py` de inmediato. **Bórrala antes de
entregar** y reemplázala por tus propias mediciones:

```bash
rm ../resultados/resultados.csv
```

---

## 6. Dos trampas que ya están resueltas (y que van en el informe)

**Nagle + delayed ACK.** Sin `set_tcp_nodelay true` en Mosquitto y sin
`TCP_NODELAY` en los clientes paho, MQTT con QoS 1 y 2 mostraba ~88 ms de latencia
constante. No era culpa del protocolo: era TCP acumulando paquetes pequeños. Con
el arreglo bajó a ~0.2 ms. **Esto solo se explica como un hallazgo metodológico y
suma muchísimo en la defensa.**

**aiocoap e IPv6.** La librería usa por defecto un transporte que exige IPv6, y
muchos contenedores no lo tienen. `coap_server.py` detecta esto y cambia
automáticamente a un transporte IPv4.

---

## 7. Mapeo al informe de 17 secciones

| Sección del informe | De dónde sale |
|---|---|
| 7. Diseño de la arquitectura | El diagrama de arriba + `docker-compose.yml` |
| 8. Tecnologías y protocolos | Matriz: Mosquitto vs HiveMQ, aiocoap vs libcoap, FastAPI vs Flask |
| 9. Implementación | Código de `servers/` + capturas de `docker compose up` |
| 10. Pruebas experimentales | Ejecuciones de `bench.py` con distintas etiquetas |
| 11. Análisis de resultados | `tabla_resumen.csv` + las 3 figuras + la interpretación |
| 14. Manual técnico | Las secciones 4 y 5 de este README |
| 16. Código fuente | Este repositorio |

---

## 8. Estructura de archivos

```
trabajo7-mvp/
├── docker-compose.yml
├── mosquitto/
│   └── mosquitto.conf
├── servers/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── http_server.py       # FastAPI, POST /data
│   ├── coap_server.py       # aiocoap, recurso /data
│   └── mqtt_echo.py         # bench/req -> bench/resp
├── bench/
│   ├── requirements.txt
│   ├── bench.py             # ← el corazón: mide RTT
│   ├── analizar.py          # ← tablas y gráficos
│   ├── medir_recursos.py    # CPU/RAM
│   ├── capturar_trafico.sh  # bytes en la red
│   └── escenario_red.sh     # simular redes malas
└── resultados/              # CSVs y PNGs generados
```
