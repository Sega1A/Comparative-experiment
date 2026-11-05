// Datos de SU red y SU servidor.
//
// Copie este archivo como include/config.h y complete los valores.
// config.h no se sube a Git (tiene la clave del WiFi).
#pragma once

// --- WiFi (el ESP32 solo usa redes de 2,4 GHz) ---
#define WIFI_SSID "nombre_de_su_red"
#define WIFI_PASSWORD "clave_de_su_red"

// --- Laptop que corre `docker compose up` (vea su IP con: hostname -I) ---
#define SERVER_HOST "192.168.1.35"
#define HTTP_PORT 8000
#define MQTT_PORT 1883
#define COAP_PORT 5683
#define MQTT_TOPIC "alert"

// --- Identidad del dispositivo (columna device_id en la base) ---
#define DEVICE_ID "esp32-01"

// --- Servidor de hora. Necesita internet; si la red no tiene, ponga la IP de
// una máquina de la red local que sirva NTP. ---
#define NTP_SERVER "pool.ntp.org"
