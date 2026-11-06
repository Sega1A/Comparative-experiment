#include "alert_queue.h"

#include <Arduino.h>
#include <Preferences.h>
#include <freertos/semphr.h>

#include "settings.h"

namespace {

constexpr const char* kNamespace = "alertas";
constexpr const char* kSeqKey = "seq";
constexpr const char* kQueueKey = "cola1";  // cambiar el nombre si cambia struct Alert

Alert items[QUEUE_CAPACITY];
size_t head = 0;   // índice de la primera
size_t count = 0;
Preferences prefs;
SemaphoreHandle_t mutex = nullptr;

struct Lock {
  Lock() { xSemaphoreTake(mutex, portMAX_DELAY); }
  ~Lock() { xSemaphoreGive(mutex); }
};

// Guarda la cola completa, en orden, como un solo bloque.
void persist() {
  Alert ordered[QUEUE_CAPACITY];
  for (size_t i = 0; i < count; i++) ordered[i] = items[(head + i) % QUEUE_CAPACITY];
  if (count == 0) {
    prefs.remove(kQueueKey);
  } else {
    prefs.putBytes(kQueueKey, ordered, count * sizeof(Alert));
  }
}

}  // namespace

void queueBegin() {
  mutex = xSemaphoreCreateMutex();
  prefs.begin(kNamespace, false);
  const size_t bytes = prefs.getBytesLength(kQueueKey);
  if (bytes > 0 && bytes % sizeof(Alert) == 0 && bytes / sizeof(Alert) <= QUEUE_CAPACITY) {
    count = prefs.getBytes(kQueueKey, items, bytes) / sizeof(Alert);
    for (size_t i = 0; i < count; i++) items[i].createdMs = 0;  // millis() del arranque anterior
  }
  head = 0;
}

uint32_t queueNextSequence() {
  Lock lock;
  const uint32_t next = prefs.getUInt(kSeqKey, 0) + 1;
  prefs.putUInt(kSeqKey, next);
  return next;
}

bool queuePush(const Alert& alert) {
  Lock lock;
  bool dropped = false;
  if (count == QUEUE_CAPACITY) {
    head = (head + 1) % QUEUE_CAPACITY;
    count--;
    dropped = true;
  }
  items[(head + count) % QUEUE_CAPACITY] = alert;
  count++;
  persist();
  return !dropped;
}

bool queuePeek(Alert& out) {
  Lock lock;
  if (count == 0) return false;
  out = items[head];
  return true;
}

void queueUpdateFront(const Alert& alert) {
  Lock lock;
  if (count == 0 || items[head].sequence != alert.sequence) return;
  items[head] = alert;
  persist();
}

void queuePop() {
  Lock lock;
  if (count == 0) return;
  head = (head + 1) % QUEUE_CAPACITY;
  count--;
  persist();
}

size_t queueSize() {
  Lock lock;
  return count;
}
