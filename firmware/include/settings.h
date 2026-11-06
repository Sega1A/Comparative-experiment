// Parámetros del experimento. Se suben a Git: son parte del método y deben
// declararse en el informe. Cambiarlos cambia los resultados.
#pragma once

#include <stdint.h>
#include <stddef.h>

// ---------------------------------------------------------------- Pines
constexpr uint8_t PIN_SDA = 21;
constexpr uint8_t PIN_SCL = 22;
constexpr uint8_t PIN_LED = 2;      // LED azul integrado en la placa
constexpr uint8_t PIN_BUZZER = 19;  // buzzer + (la otra pata a GND)
// Se maneja con PWM a esta frecuencia: así suena tanto un buzzer pasivo
// (necesita una señal alterna) como uno activo.
constexpr uint32_t BUZZER_FREQ_HZ = 2700;
constexpr uint8_t PIN_BOOT = 0;     // botón BOOT de la placa

// ---------------------------------------------------------------- Detección
// Bourke et al. (2007): caída libre seguida de un pico de impacto.
constexpr uint32_t SAMPLE_PERIOD_MS = 20;        // 50 Hz
constexpr float FREEFALL_G = 0.5f;               // |a| por debajo: caída libre
constexpr float IMPACT_G = 2.5f;                 // |a| por encima: impacto
constexpr uint32_t FREEFALL_TO_IMPACT_MS = 1000; // ventana entre ambas fases
constexpr bool REQUIRE_FREEFALL = true;          // false: basta el impacto
constexpr uint32_t POST_IMPACT_SETTLE_MS = 2000; // espera antes de alertar
// Calibración: informa por el monitor golpes de más de esto aunque no cumplan
// el patrón de caída (línea SENSOR).
constexpr float BUMP_NOTE_G = 1.8f;

// Inmovilidad prolongada después de una caída.
constexpr float STILL_TOLERANCE_G = 0.15f;       // quieto si ||a| - 1 g| < esto
constexpr uint32_t IMMOBILITY_MS = 15000;        // quieto este tiempo -> alerta
constexpr uint32_t IMMOBILITY_WATCH_MAX_MS = 120000;  // deja de vigilar

// ---------------------------------------------------------------- Envío
// Misma política para los tres protocolos. Un "intento" es un envío completo
// con la fiabilidad propia del protocolo (retransmisiones TCP, QoS 1 o CON),
// limitado a ATTEMPT_TIMEOUT_MS. Entre intentos: espera exponencial con jitter.
constexpr uint32_t ATTEMPT_TIMEOUT_MS = 10000;
constexpr uint8_t MAX_ATTEMPTS = 5;              // modo experimento: luego se da por perdida
constexpr uint32_t BACKOFF_BASE_MS = 1000;       // 1, 2, 4, 8... s
constexpr uint32_t BACKOFF_MAX_MS = 30000;
constexpr float BACKOFF_JITTER = 0.2f;           // +-20 %

// Modo operativo: tras este número de intentos fallidos seguidos con un
// protocolo, pasa al siguiente de FAILOVER_ORDER (ver protocols.cpp).
constexpr uint8_t FAILOVER_AFTER = 2;

// MQTT
constexpr int MQTT_QOS = 1;                      // al menos una vez (espera PUBACK)
constexpr bool MQTT_PERSISTENT = false;          // false: conecta y desconecta en cada intento

// CoAP (RFC 7252, sección 4.8). Ojo: el intento completo está limitado a
// ATTEMPT_TIMEOUT_MS (10 s), así que dentro de un intento caben 2
// retransmisiones (a los 2-3 s y a los 6-9 s). Las 4 de la RFC solo se
// alcanzan si se sube ATTEMPT_TIMEOUT_MS a ~93 s (MAX_TRANSMIT_WAIT).
constexpr uint32_t COAP_ACK_TIMEOUT_MS = 2000;
constexpr float COAP_ACK_RANDOM_FACTOR = 1.5f;
constexpr uint8_t COAP_MAX_RETRANSMIT = 4;
constexpr uint16_t COAP_LOCAL_PORT = 56830;

// ---------------------------------------------------------------- Cola
constexpr size_t QUEUE_CAPACITY = 16;            // alertas pendientes guardadas en flash

// ---------------------------------------------------------------- Prueba
// Ráfaga de alertas de prueba (BOOT largo o comando 'r'): la siguiente se
// genera TEST_BURST_GAP_MS después de que la anterior terminó.
constexpr uint16_t TEST_BURST_COUNT = 30;
constexpr uint32_t TEST_BURST_GAP_MS = 2000;

// ---------------------------------------------------------------- Alarma local
// El buzzer suena este tiempo después de una caída (o hasta presionar BOOT).
constexpr uint32_t ALARM_MAX_MS = 10000;
constexpr uint32_t LONG_PRESS_MS = 2000;
