#include "protocols.h"

#include <Arduino.h>
#include <HTTPClient.h>
#include <MQTT.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <inttypes.h>
#include <string.h>

#include "config.h"
#include "settings.h"

// Ajustar con los resultados del experimento: primero el más fiable.
const Protocol FAILOVER_ORDER[] = {Protocol::MQTT, Protocol::COAP, Protocol::HTTP};
const size_t FAILOVER_COUNT = sizeof(FAILOVER_ORDER) / sizeof(FAILOVER_ORDER[0]);

namespace {

SendResult result(SendStatus status, const char* error, uint8_t retransmissions = 0) {
  SendResult r;
  r.status = status;
  strlcpy(r.error, error, sizeof r.error);
  r.coapRetransmissions = retransmissions;
  return r;
}

uint32_t remaining(uint32_t start, uint32_t timeoutMs) {
  const uint32_t elapsed = millis() - start;
  return elapsed < timeoutMs ? timeoutMs - elapsed : 1;
}

// ------------------------------------------------------------------ HTTP
// POST /alert con una conexión TCP nueva por intento. Éxito: 200 y "true".
SendResult sendHttp(const char* json, size_t length, uint32_t timeoutMs) {
  char url[96];
  snprintf(url, sizeof url, "http://%s:%d/alert", SERVER_HOST, HTTP_PORT);

  WiFiClient client;
  HTTPClient http;
  if (!http.begin(client, url)) return result(SendStatus::RETRY, "http_begin");
  http.setReuse(false);
  http.setConnectTimeout((int32_t)timeoutMs);
  http.setTimeout((uint16_t)(timeoutMs > 65535 ? 65535 : timeoutMs));
  http.addHeader("Content-Type", "application/json");

  const int code = http.POST((uint8_t*)json, length);
  const String body = code > 0 ? http.getString() : String();
  http.end();

  char error[32];
  if (code == 200 && body.indexOf("true") >= 0) return result(SendStatus::OK, "");
  if (code == 400) return result(SendStatus::REJECTED, "http_400");
  // Códigos negativos de HTTPClient: -1 conexión rechazada, -11 sin respuesta a tiempo...
  if (code > 0) {
    snprintf(error, sizeof error, "http_%d", code);
  } else {
    snprintf(error, sizeof error, "http_err_%d", code);
  }
  return result(SendStatus::RETRY, error);
}

// ------------------------------------------------------------------ MQTT
// Publica con QoS 1 y espera el PUBACK del broker. Ojo: el PUBACK confirma que
// llegó a Mosquitto, no que el suscriptor ya la guardó en la base.
WiFiClient mqttNet;
MQTTClient mqtt(256);

SendResult sendMqtt(const char* json, size_t length, uint32_t timeoutMs) {
  const uint32_t start = millis();
  char error[32];

  if (!mqtt.connected()) {
    mqttNet.setConnectionTimeout(timeoutMs);
    mqtt.setTimeout((int)timeoutMs);
    char clientId[48];
    snprintf(clientId, sizeof clientId, "%s-%08" PRIx32, DEVICE_ID, esp_random());
    if (!mqtt.connect(clientId)) {
      snprintf(error, sizeof error, "mqtt_connect_%d_%d", (int)mqtt.lastError(), (int)mqtt.returnCode());
      return result(SendStatus::RETRY, error);
    }
  }

  mqtt.setTimeout((int)remaining(start, timeoutMs));
  const bool ok = mqtt.publish(MQTT_TOPIC, json, (int)length, false, MQTT_QOS);
  const int lastError = (int)mqtt.lastError();

  if (!ok) {
    mqttNet.stop();     // cierra el socket sin esperar a la red
    mqtt.disconnect();  // ya no está conectado: solo limpia el estado
    snprintf(error, sizeof error, "mqtt_publish_%d", lastError);
    return result(SendStatus::RETRY, error);
  }
  if (!MQTT_PERSISTENT) {
    mqtt.setTimeout(500);
    mqtt.disconnect();
  }
  return result(SendStatus::OK, "");
}

// ------------------------------------------------------------------ CoAP
// POST confirmable (CON) a /alert según RFC 7252: si no llega el ACK, retransmite
// con espera exponencial (2-3 s, 4-6 s, ...) hasta COAP_MAX_RETRANSMIT veces.
// Acepta respuesta incluida en el ACK o respuesta separada (ACK vacío + CON).
WiFiUDP udp;
uint16_t coapMessageId = 0;

constexpr uint8_t kTypeCon = 0, kTypeNon = 1, kTypeAck = 2, kTypeRst = 3;
constexpr uint8_t kTokenLength = 4;

size_t buildCoapPost(uint8_t* buf, size_t capacity, uint16_t messageId, const uint8_t* token,
                     const char* json, size_t length) {
  static const char path[] = "alert";
  const size_t pathLength = sizeof(path) - 1;
  if (4 + kTokenLength + 1 + pathLength + 2 + 1 + length > capacity) return 0;

  size_t i = 0;
  buf[i++] = 0x40 | kTokenLength;  // versión 1, tipo CON
  buf[i++] = 0x02;                 // código 0.02 POST
  buf[i++] = messageId >> 8;
  buf[i++] = messageId & 0xFF;
  memcpy(buf + i, token, kTokenLength);
  i += kTokenLength;
  buf[i++] = (11 << 4) | pathLength;  // opción 11 Uri-Path
  memcpy(buf + i, path, pathLength);
  i += pathLength;
  buf[i++] = (1 << 4) | 1;  // opción 12 Content-Format (delta 1), 1 byte
  buf[i++] = 50;            // application/json
  buf[i++] = 0xFF;          // marcador de payload
  memcpy(buf + i, json, length);
  return i + length;
}

SendResult coapResponse(uint8_t code, uint8_t retransmissions) {
  char error[32];
  const uint8_t cls = code >> 5, detail = code & 0x1F;
  if (cls == 2) return result(SendStatus::OK, "", retransmissions);
  snprintf(error, sizeof error, "coap_%u.%02u", cls, detail);
  return result(cls == 4 ? SendStatus::REJECTED : SendStatus::RETRY, error, retransmissions);
}

SendResult sendCoap(const char* json, size_t length, uint32_t timeoutMs) {
  const uint32_t start = millis();

  IPAddress server;
  if (!server.fromString(SERVER_HOST)) return result(SendStatus::REJECTED, "coap_host_no_es_ip");

  uint8_t packet[256];
  uint8_t token[kTokenLength];
  const uint32_t tokenBits = esp_random();
  memcpy(token, &tokenBits, kTokenLength);
  const uint16_t messageId = ++coapMessageId;
  const size_t packetLength = buildCoapPost(packet, sizeof packet, messageId, token, json, length);
  if (packetLength == 0) return result(SendStatus::REJECTED, "coap_muy_grande");

  if (!udp.begin(COAP_LOCAL_PORT)) return result(SendStatus::RETRY, "coap_socket");

  auto transmit = [&]() {
    udp.beginPacket(server, COAP_PORT);
    udp.write(packet, packetLength);
    return udp.endPacket() == 1;
  };

  uint32_t wait = COAP_ACK_TIMEOUT_MS +
                  (uint32_t)((COAP_ACK_RANDOM_FACTOR - 1.0f) * COAP_ACK_TIMEOUT_MS *
                             (esp_random() / (float)UINT32_MAX));
  uint8_t retransmissions = 0;
  bool emptyAck = false;  // el servidor confirmó; la respuesta viene aparte

  if (!transmit()) {
    udp.stop();
    return result(SendStatus::RETRY, "coap_send");
  }
  uint32_t sentAt = millis();

  uint8_t in[256];
  while (millis() - start < timeoutMs) {
    if (udp.parsePacket() > 0) {
      const int got = udp.read(in, sizeof in);
      if (got < 4 || (in[0] >> 6) != 1) continue;
      const uint8_t type = (in[0] >> 4) & 0x03;
      const uint8_t tokenLength = in[0] & 0x0F;
      const uint8_t code = in[1];
      const uint16_t rxId = (in[2] << 8) | in[3];
      const bool sameToken = tokenLength == kTokenLength && got >= 4 + kTokenLength &&
                             memcmp(in + 4, token, kTokenLength) == 0;

      if (type == kTypeAck && rxId == messageId) {
        if (code == 0) {
          emptyAck = true;
        } else if (sameToken) {
          udp.stop();
          return coapResponse(code, retransmissions);
        }
      } else if ((type == kTypeCon || type == kTypeNon) && sameToken && code != 0) {
        if (type == kTypeCon) {  // respuesta separada: confirmarla con ACK vacío
          const uint8_t ack[4] = {0x60, 0x00, in[2], in[3]};
          udp.beginPacket(udp.remoteIP(), udp.remotePort());
          udp.write(ack, sizeof ack);
          udp.endPacket();
        }
        udp.stop();
        return coapResponse(code, retransmissions);
      } else if (type == kTypeRst && rxId == messageId) {
        udp.stop();
        return result(SendStatus::RETRY, "coap_rst", retransmissions);
      }
      continue;
    }

    if (!emptyAck && millis() - sentAt >= wait) {
      if (retransmissions >= COAP_MAX_RETRANSMIT) {
        udp.stop();
        return result(SendStatus::RETRY, "coap_sin_ack", retransmissions);
      }
      transmit();
      retransmissions++;
      sentAt = millis();
      wait *= 2;
    }
    vTaskDelay(pdMS_TO_TICKS(2));
  }
  udp.stop();
  return result(SendStatus::RETRY, emptyAck ? "coap_sin_respuesta" : "coap_tiempo", retransmissions);
}

}  // namespace

const char* protocolName(Protocol protocol) {
  switch (protocol) {
    case Protocol::HTTP:
      return "http";
    case Protocol::MQTT:
      return "mqtt";
    case Protocol::COAP:
      return "coap";
  }
  return "?";
}

const char* statusName(SendStatus status) {
  switch (status) {
    case SendStatus::OK:
      return "ok";
    case SendStatus::RETRY:
      return "fallo";
    case SendStatus::REJECTED:
      return "rechazada";
  }
  return "?";
}

void protocolsBegin() {
  coapMessageId = (uint16_t)esp_random();
  mqtt.begin(SERVER_HOST, MQTT_PORT, mqttNet);
  mqtt.setCleanSession(true);
  mqtt.setKeepAlive(30);
}

void protocolsIdle() {
  if (MQTT_PERSISTENT && mqtt.connected()) mqtt.loop();
}

SendResult protocolSend(Protocol protocol, const char* json, size_t length, uint32_t timeoutMs) {
  switch (protocol) {
    case Protocol::HTTP:
      return sendHttp(json, length, timeoutMs);
    case Protocol::MQTT:
      return sendMqtt(json, length, timeoutMs);
    case Protocol::COAP:
      return sendCoap(json, length, timeoutMs);
  }
  return result(SendStatus::REJECTED, "protocolo_desconocido");
}
