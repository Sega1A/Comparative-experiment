// Dispositivo de detección de caídas: ESP32 + MPU6050.
//
// Dos tareas:
//   - loop() (núcleo 1): lee el sensor a 50 Hz, detecta caída/inmovilidad,
//     maneja el botón, el buzzer, el LED y los comandos del monitor serie.
//   - senderTask (núcleo 0): saca alertas de la cola y las envía, con
//     reintentos. Así un envío lento no detiene la lectura del sensor.
//
// Qué hace cuando el envío falla (lo pedido en el proyecto):
//   1. La alerta ya está guardada en flash: no se pierde aunque se reinicie.
//   2. Cada intento tiene un límite de ATTEMPT_TIMEOUT_MS y usa la fiabilidad
//      propia del protocolo (TCP, QoS 1 o CON).
//   3. Si falla, espera 1, 2, 4, 8... s (+-20 %) y reintenta con el MISMO
//      número de secuencia, para que el servidor pueda descartar duplicados.
//   4. Sin WiFi, espera la reconexión dentro del mismo límite.
//   5. Modo experimento: tras MAX_ATTEMPTS la alerta cuenta como perdida
//      (así se mide la tasa de entrega). Modo operativo: nunca se rinde y,
//      tras FAILOVER_AFTER fallos seguidos, cambia al siguiente protocolo.
//   6. Mientras tanto avisa localmente: buzzer y LED parpadeando.

#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <inttypes.h>
#include <sys/time.h>
#include <time.h>

#include "alert.h"
#include "alert_queue.h"
#include "config.h"
#include "fall_detector.h"
#include "log.h"
#include "protocols.h"
#include "settings.h"

#if defined(MODE_EXPERIMENT) == defined(MODE_OPERATIONAL)
#error "Defina MODE_EXPERIMENT o MODE_OPERATIONAL (lo hace cada entorno de platformio.ini)"
#endif

#ifdef MODE_EXPERIMENT
static const char* const MODE_NAME = "experimento";
#else
static const char* const MODE_NAME = "operativo";
#endif

// ============================================================ MPU6050
namespace mpu {

constexpr uint8_t ADDR = 0x68;
constexpr float LSB_PER_G = 4096.0f;  // rango +-8 g

bool write(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool read(uint8_t reg, uint8_t* buf, size_t n) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint16_t)ADDR, n, true) != n) return false;
  for (size_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

bool begin() {
  return write(0x6B, 0x00)     // PWR_MGMT_1: despierta
         && write(0x1C, 0x10)  // ACCEL_CONFIG: +-8 g
         && write(0x1A, 0x03); // CONFIG: filtro pasa bajos ~44 Hz
}

bool readMagnitudeG(float& g) {
  uint8_t b[6];
  if (!read(0x3B, b, 6)) return false;
  const float ax = (int16_t)((b[0] << 8) | b[1]) / LSB_PER_G;
  const float ay = (int16_t)((b[2] << 8) | b[3]) / LSB_PER_G;
  const float az = (int16_t)((b[4] << 8) | b[5]) / LSB_PER_G;
  g = sqrtf(ax * ax + ay * ay + az * az);
  return true;
}

}  // namespace mpu

// ============================================================ Hora
static bool timeSynced() { return time(nullptr) > 1700000000; }  // posterior a nov 2023

static int64_t epochMs() {
  if (!timeSynced()) return 0;
  timeval tv;
  gettimeofday(&tv, nullptr);
  return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

// ============================================================ Estado
static FallDetector detector;
static bool alarmActive = false;
static uint32_t alarmStartMs = 0;

static uint16_t burstRemaining = 0;
static bool burstWaiting = false;
static uint32_t burstWaitStart = 0;

static uint32_t countOk = 0, countLost = 0, countRejected = 0;  // solo los escribe la tarea de envío

#ifdef MODE_EXPERIMENT
static Protocol currentProtocol() { return static_cast<Protocol>(EXPERIMENT_PROTOCOL); }
#else
static volatile size_t failoverIndex = 0;
static uint8_t failsOnCurrent = 0;
static Protocol currentProtocol() { return FAILOVER_ORDER[failoverIndex]; }
#endif

static void startAlarm() {
  alarmActive = true;
  alarmStartMs = millis();
}

// Prende o apaga el buzzer solo cuando cambia (reconfigurar el PWM en cada
// vuelta del loop lo haría sonar mal).
static void setBuzzer(bool on) {
  static bool buzzing = false;
  if (on == buzzing) return;
  buzzing = on;
  ledcWriteTone(PIN_BUZZER, on ? BUZZER_FREQ_HZ : 0);
}

static void beep(uint32_t ms) {
  setBuzzer(true);
  delay(ms);
  setBuzzer(false);
}

static void enqueue(EventType event, float acceleration) {
  Alert alert{};
  alert.sequence = queueNextSequence();
  alert.timestampMs = epochMs();
  alert.acceleration = acceleration;
  alert.event = event;
  alert.attempts = 0;
  alert.createdMs = millis() | 1;  // nunca 0 (0 = "recuperada tras reinicio")
  const bool kept = queuePush(alert);
  logLine("EVENT,%s,%" PRIu32 ",%.2f,ntp=%s%s", eventName(event), alert.sequence,
          (double)acceleration, timeSynced() ? "si" : "NO",
          kept ? "" : ",cola_llena_se_descarto_la_mas_antigua");
}

// ============================================================ Envío
static uint32_t backoffMs(uint8_t attempts) {
  uint64_t base = (uint64_t)BACKOFF_BASE_MS << (attempts > 16 ? 15 : attempts - 1);
  if (base > BACKOFF_MAX_MS) base = BACKOFF_MAX_MS;
  const float jitter = ((esp_random() / (float)UINT32_MAX) * 2.0f - 1.0f) * BACKOFF_JITTER;
  return (uint32_t)(base * (1.0f + jitter));
}

static bool waitForWifi(uint32_t timeoutMs) {
  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start >= timeoutMs) return false;
    vTaskDelay(pdMS_TO_TICKS(100));
  }
  return true;
}

static void senderTask(void*) {
  char json[192];
  for (;;) {
    Alert alert;
    if (!queuePeek(alert)) {
      protocolsIdle();
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }

    const Protocol protocol = currentProtocol();
    const size_t length = alertToJson(alert, json, sizeof json);
    const uint32_t start = millis();

    SendResult r;
    if (!waitForWifi(ATTEMPT_TIMEOUT_MS)) {
      r.status = SendStatus::RETRY;
      strlcpy(r.error, "sin_wifi", sizeof r.error);
      r.coapRetransmissions = 0;
    } else {
      const uint32_t used = millis() - start;
      r = protocolSend(protocol, json, length, used < ATTEMPT_TIMEOUT_MS ? ATTEMPT_TIMEOUT_MS - used : 1);
    }

    const uint32_t attemptMs = millis() - start;
    const int rssi = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
    alert.attempts++;

    logLine("ATTEMPT,%s,%" PRIu32 ",%u,%s,%" PRIu32 ",%d,%u,%s", protocolName(protocol),
            alert.sequence, alert.attempts, statusName(r.status), attemptMs, rssi,
            r.coapRetransmissions, r.error);

    const char* outcome = nullptr;
    if (r.status == SendStatus::OK) {
      outcome = "entregada";
      countOk++;
    } else if (r.status == SendStatus::REJECTED) {
      outcome = "rechazada";
      countRejected++;
#ifdef MODE_EXPERIMENT
    } else if (alert.attempts >= MAX_ATTEMPTS) {
      outcome = "perdida";
      countLost++;
#endif
    }

    if (outcome != nullptr) {
      const long totalMs = alert.createdMs ? (long)(millis() - alert.createdMs) : -1;
      logLine("RESULT,%s,%s,%" PRIu32 ",%s,%s,%u,%" PRIu32 ",%ld,%d,%u,%" PRIu32 ",%s", MODE_NAME,
              protocolName(protocol), alert.sequence, eventName(alert.event), outcome,
              alert.attempts, attemptMs, totalMs, rssi, (unsigned)length, ESP.getMinFreeHeap(),
              r.error);
      queuePop();
#ifdef MODE_OPERATIONAL
      failsOnCurrent = 0;
#endif
      continue;
    }

#ifdef MODE_OPERATIONAL
    if (++failsOnCurrent >= FAILOVER_AFTER) {
      failsOnCurrent = 0;
      failoverIndex = (failoverIndex + 1) % FAILOVER_COUNT;
      logLine("FAILOVER,%s", protocolName(currentProtocol()));
    }
#endif

    queueUpdateFront(alert);
    const uint32_t wait = backoffMs(alert.attempts);
    logLine("BACKOFF,%" PRIu32 ",%" PRIu32, alert.sequence, wait);
    vTaskDelay(pdMS_TO_TICKS(wait));
  }
}

// ============================================================ Entrada y salida
static void toggleBurst() {
  if (burstRemaining > 0) {
    burstRemaining = 0;
    logLine("INFO,rafaga_detenida");
  } else {
    burstRemaining = TEST_BURST_COUNT;
    burstWaiting = false;
    logLine("INFO,rafaga_iniciada,%u alertas de prueba", TEST_BURST_COUNT);
  }
}

static void imOk() {
  if (alarmActive) logLine("INFO,alarma_silenciada");
  alarmActive = false;
  detector.cancelWatch();
}

static void printStatus() {
  logLine("STATUS,modo=%s,protocolo=%s,wifi=%s,ip=%s,rssi=%d,ntp=%s,cola=%u,entregadas=%" PRIu32
          ",perdidas=%" PRIu32 ",rechazadas=%" PRIu32 ",rafaga=%u,detector=%s,heap_libre=%" PRIu32,
          MODE_NAME, protocolName(currentProtocol()),
          WiFi.status() == WL_CONNECTED ? "si" : "NO", WiFi.localIP().toString().c_str(),
          WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0, timeSynced() ? "si" : "NO",
          (unsigned)queueSize(), countOk, countLost, countRejected, burstRemaining,
          detector.stateName(), ESP.getFreeHeap());
}

static void printHelp() {
  logLine("HELP,comandos: f=simular caida  t=una alerta de prueba  r=rafaga on/off  "
          "s=estado  b=probar buzzer  h=ayuda");
  logLine("HELP,boton BOOT: corto=estoy bien (silencia)  largo (2 s)=rafaga on/off");
}

static void handleSerial() {
  while (Serial.available()) {
    switch (Serial.read()) {
      case 'f':
        enqueue(EventType::FALL, 0.0f);
        startAlarm();
        break;
      case 't':
        enqueue(EventType::TEST, 0.0f);
        break;
      case 'r':
        toggleBurst();
        break;
      case 's':
        printStatus();
        break;
      case 'b':
        logLine("INFO,buzzer_1s");
        beep(1000);
        break;
      case 'h':
        printHelp();
        break;
      default:
        break;
    }
  }
}

static void handleButton(uint32_t now) {
  static bool wasDown = false;
  static uint32_t downAt = 0;
  static bool longDone = false;
  const bool down = digitalRead(PIN_BOOT) == LOW;
  if (down && !wasDown) {
    downAt = now;
    longDone = false;
  }
  if (down && !longDone && now - downAt >= LONG_PRESS_MS) {
    longDone = true;
    toggleBurst();
  }
  if (!down && wasDown && !longDone && now - downAt >= 30) imOk();
  wasDown = down;
}

// Ráfaga de prueba: la siguiente alerta sale TEST_BURST_GAP_MS después de que
// la cola quedó vacía, para que cada medición sea independiente.
static void handleBurst(uint32_t now) {
  if (burstRemaining == 0 || queueSize() > 0) {
    burstWaiting = false;
    return;
  }
  if (!burstWaiting) {
    burstWaiting = true;
    burstWaitStart = now;
  } else if (now - burstWaitStart >= TEST_BURST_GAP_MS) {
    burstWaiting = false;
    burstRemaining--;
    enqueue(EventType::TEST, 0.0f);
    if (burstRemaining == 0) logLine("INFO,rafaga_terminada");
  }
}

static void updateOutputs(uint32_t now) {
  if (alarmActive && now - alarmStartMs >= ALARM_MAX_MS) alarmActive = false;
  setBuzzer(alarmActive && (now - alarmStartMs) % 500 < 200);

  bool led;
  if (WiFi.status() != WL_CONNECTED) {
    led = now % 1000 < 500;  // lento: sin WiFi
  } else if (queueSize() > 0) {
    led = now % 200 < 100;   // rápido: hay alertas sin confirmar
  } else {
    led = false;
  }
  digitalWrite(PIN_LED, led ? HIGH : LOW);
}

// Motivos frecuentes: NO_AP_FOUND (no ve la red: nombre mal escrito, red de
// 5 GHz o muy lejos), AUTH_FAIL / 4WAY_HANDSHAKE_TIMEOUT (clave incorrecta),
// BEACON_TIMEOUT (señal perdida).
static void onWifiEvent(arduino_event_id_t event, arduino_event_info_t info) {
  if (event == ARDUINO_EVENT_WIFI_STA_GOT_IP) {
    logLine("WIFI,conectado,ip=%s,rssi=%d", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
    const auto reason = (wifi_err_reason_t)info.wifi_sta_disconnected.reason;
    logLine("WIFI,desconectado,motivo=%u %s,red=%s", (unsigned)reason,
            WiFi.disconnectReasonName(reason), WIFI_SSID);
  }
}

// ============================================================ Arduino
void setup() {
  Serial.begin(115200);
  delay(300);
  logBegin();

  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BOOT, INPUT_PULLUP);
  if (!ledcAttach(PIN_BUZZER, BUZZER_FREQ_HZ, 10)) logLine("ERROR,no se pudo configurar el buzzer");
  ledcWrite(PIN_BUZZER, 0);
  beep(150);  // pitido corto al arrancar: confirma que el buzzer funciona

  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  if (!mpu::begin()) logLine("ERROR,el MPU6050 no responde: revise SDA=21, SCL=22, VCC y GND");

  queueBegin();

  WiFi.onEvent(onWifiEvent);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // sin ahorro de energía: no agrega retardo a las mediciones
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, NTP_SERVER);

  protocolsBegin();

  logLine("BOOT,modo=%s,protocolo=%s,dispositivo=%s,servidor=%s,red=%s,pendientes=%u", MODE_NAME,
          protocolName(currentProtocol()), DEVICE_ID, SERVER_HOST, WIFI_SSID, (unsigned)queueSize());
  logLine("# ATTEMPT,protocolo,secuencia,intento,estado,ms,rssi,retransmisiones_coap,error");
  logLine("# RESULT,modo,protocolo,secuencia,evento,resultado,intentos,ms_ultimo_intento,"
          "ms_total,rssi,bytes_payload,heap_minimo,error");
  printHelp();

  xTaskCreatePinnedToCore(senderTask, "envio", 8192, nullptr, 1, nullptr, 0);
}

void loop() {
  static uint32_t lastSample = 0;
  static uint32_t readErrors = 0;
  const uint32_t now = millis();

  if (now - lastSample >= SAMPLE_PERIOD_MS) {
    lastSample = now;
    float g;
    if (mpu::readMagnitudeG(g)) {
      switch (detector.update(g, now)) {
        case FallDetector::Event::FALL:
          enqueue(EventType::FALL, detector.peakG());
          startAlarm();
          break;
        case FallDetector::Event::IMMOBILITY:
          enqueue(EventType::IMMOBILITY, 0.0f);
          startAlarm();
          break;
        case FallDetector::Event::NONE:
          break;
      }
      const char* text;
      float peakG, minG;
      if (detector.takeNote(text, peakG, minG)) {
        logLine("SENSOR,%s,pico=%.2f g,minimo=%.2f g (umbrales: caida libre <%.1f, impacto >%.1f)",
                text, (double)peakG, (double)minG, (double)FREEFALL_G, (double)IMPACT_G);
      }
    } else if (++readErrors % 250 == 1) {
      logLine("ERROR,lectura I2C fallida (%" PRIu32 " en total)", readErrors);
    }
  }

  handleButton(now);
  handleSerial();
  handleBurst(now);
  updateOutputs(millis());  // hora actual: startAlarm() puede haber corrido después de tomar `now`
  delay(1);
}
