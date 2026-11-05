// Alerta que sale del dispositivo. El JSON cumple el contrato AlertDTO de
// common/schemas/alert.py (device_id, sequence, timestamp + opcionales).
#pragma once

#include <stddef.h>
#include <stdint.h>

enum class EventType : uint8_t { FALL = 0, IMMOBILITY = 1, TEST = 2 };

const char* eventName(EventType event);

struct Alert {
  uint32_t sequence;     // único por dispositivo; se repite igual en cada reintento
  int64_t timestampMs;   // momento de la detección, ms desde epoch (UTC); 0 sin hora NTP
  float acceleration;    // pico de impacto en g (solo caídas)
  EventType event;
  uint8_t attempts;      // intentos de envío ya hechos
  uint32_t createdMs;    // millis() al crearla; 0 si se recuperó tras un reinicio
};

// Escribe el JSON en buf. Devuelve su largo (0 si no cupo).
size_t alertToJson(const Alert& alert, char* buf, size_t capacity);
