#include "log.h"

#include <Arduino.h>
#include <freertos/semphr.h>
#include <stdarg.h>

static SemaphoreHandle_t logMutex = nullptr;

void logBegin() { logMutex = xSemaphoreCreateMutex(); }

void logLine(const char* format, ...) {
  char line[256];
  va_list args;
  va_start(args, format);
  vsnprintf(line, sizeof line, format, args);
  va_end(args);
  if (logMutex) xSemaphoreTake(logMutex, portMAX_DELAY);
  Serial.println(line);
  if (logMutex) xSemaphoreGive(logMutex);
}
