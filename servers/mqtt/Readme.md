Comandos de Ejecución
Terminal 1 (Iniciar Servicios):


docker compose up --build

Terminal 2 (Publicar Alerta QoS 0):

docker exec -it mqtt-broker mosquitto_pub -q 0 -t "alertas/caidas" -m "{\"device_id\": \"ESP32_TEST_QOS0\", \"timestamp\": $(date +%s.%N)}"


Terminal 2 (Publicar Alerta QoS 1):

docker exec -it mqtt-broker mosquitto_pub -q 1 -t "alertas/caidas" -m "{\"device_id\": \"ESP32_TEST_QOS1\", \"timestamp\": $(date +%s.%N)}"


Ejemplo de Salida Esperada (Terminal 1)

mqtt-subscriber  | =======================================================
mqtt-subscriber  | [NUEVA ALERTA RECIBIDA]
mqtt-subscriber  |    ▸ Tema (Topic)   : alertas/caidas
mqtt-subscriber  |    ▸ QoS del Mensaje: 1
mqtt-subscriber  |    ▸ Dispositivo ID : ESP32_TEST_QOS1
mqtt-subscriber  |    ▸ Latencia Medida: 237.49 ms
mqtt-subscriber  |    ▸ Payload JSON   : {'device_id': 'ESP32_TEST_QOS1', 'timestamp': 1792247059.504377}