#include "alert.h"

#include <inttypes.h>
#include <stdio.h>

#include "config.h"

const char* eventName(EventType event) {
  switch (event) {
    case EventType::FALL:
      return "fall";
    case EventType::IMMOBILITY:
      return "immobility";
    case EventType::TEST:
      return "test";
  }
  return "unknown";
}

size_t alertToJson(const Alert& alert, char* buf, size_t capacity) {
  int n;
  if (alert.event == EventType::FALL) {
    n = snprintf(buf, capacity,
                 "{\"device_id\":\"%s\",\"sequence\":%" PRIu32 ",\"timestamp\":%" PRId64
                 ",\"event_type\":\"%s\",\"acceleration\":%.2f}",
                 DEVICE_ID, alert.sequence, alert.timestampMs, eventName(alert.event),
                 (double)alert.acceleration);
  } else {
    n = snprintf(buf, capacity,
                 "{\"device_id\":\"%s\",\"sequence\":%" PRIu32 ",\"timestamp\":%" PRId64
                 ",\"event_type\":\"%s\"}",
                 DEVICE_ID, alert.sequence, alert.timestampMs, eventName(alert.event));
  }
  if (n < 0 || (size_t)n >= capacity) return 0;
  return (size_t)n;
}
