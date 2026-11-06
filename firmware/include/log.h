// Una línea por llamada al monitor serie, sin mezclar las dos tareas.
#pragma once

void logBegin();
void logLine(const char* format, ...) __attribute__((format(printf, 1, 2)));
