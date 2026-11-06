// Cola de alertas pendientes, guardada en la flash (NVS).
//
// Una alerta entra apenas se detecta el evento y sale solo cuando el servidor
// la confirma (o, en modo experimento, cuando se agotan los intentos). Si el
// ESP32 se reinicia o se queda sin batería, las pendientes se recuperan al
// arrancar. Es segura para usar desde las dos tareas (sensor y envío).
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "alert.h"

void queueBegin();

// Número de secuencia siguiente; persiste entre reinicios para que el par
// (device_id, sequence) identifique cada alerta y el servidor pueda detectar
// duplicados producidos por los reintentos.
uint32_t queueNextSequence();

// Agrega al final. Si la cola está llena descarta la más antigua y devuelve false.
bool queuePush(const Alert& alert);

bool queuePeek(Alert& out);               // primera, sin sacarla
void queueUpdateFront(const Alert& alert);  // guarda el contador de intentos
void queuePop();
size_t queueSize();
