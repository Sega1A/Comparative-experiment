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

## Gestión del proyecto

Scrum con sprints de una semana. El backlog y los sprints están en GitHub Projects.
