// Un intento de envío de una alerta por HTTP, MQTT o CoAP.
//
// Cada función hace UN intento completo con la fiabilidad propia del protocolo
// y respeta el tiempo máximo que recibe. Los reintentos entre intentos los
// decide main.cpp con la misma política para los tres.
#pragma once

#include <stddef.h>
#include <stdint.h>

enum class Protocol : uint8_t { HTTP = 0, MQTT = 1, COAP = 2 };

enum class SendStatus : uint8_t {
  OK,        // el servidor confirmó (HTTP 200 true, PUBACK, CoAP 2.04)
  RETRY,     // falla transitoria: red, tiempo agotado, error 5xx
  REJECTED,  // el servidor dice que el mensaje es inválido: reintentar no sirve
};

struct SendResult {
  SendStatus status;
  char error[32];               // código corto para el registro ("" si OK)
  uint8_t coapRetransmissions;  // retransmisiones CON hechas dentro del intento
};

const char* protocolName(Protocol protocol);
const char* statusName(SendStatus status);

// Orden de respaldo del modo operativo.
extern const Protocol FAILOVER_ORDER[];
extern const size_t FAILOVER_COUNT;

void protocolsBegin();
void protocolsIdle();  // mantiene viva la sesión MQTT si es persistente

SendResult protocolSend(Protocol protocol, const char* json, size_t length, uint32_t timeoutMs);
