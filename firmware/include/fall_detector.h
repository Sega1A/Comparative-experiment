// Detección de caída por umbrales sobre la magnitud de la aceleración
// (Bourke et al., 2007) y de inmovilidad prolongada después de la caída.
//
//   reposo --(|a| < FREEFALL_G)--> caída libre --(|a| > IMPACT_G)--> impacto
//     impacto --(POST_IMPACT_SETTLE_MS)--> evento FALL, vigila inmovilidad
//     vigilancia --(quieto IMMOBILITY_MS)--> evento IMMOBILITY
//     vigilancia --(nueva caída libre)--> caída libre (detecta otra caída)
#pragma once

#include <stdint.h>

class FallDetector {
 public:
  enum class Event { NONE, FALL, IMMOBILITY };

  // Llamar a cada muestra con |a| en g y millis().
  Event update(float g, uint32_t nowMs);

  // La persona confirmó que está bien (botón BOOT): deja de vigilar.
  void cancelWatch();

  // Nota de calibración pendiente (golpe que no llegó a ser caída, etc.).
  // Devuelve false si no hay. Cada nota se entrega una sola vez.
  bool takeNote(const char*& text, float& peakG, float& minG);

  float peakG() const { return peak_; }
  const char* stateName() const;

 private:
  enum class State { IDLE, FREEFALL, SETTLING, WATCHING };
  void startFreefall(float g, uint32_t now);
  void note(const char* text, float peakG, float minG);

  State state_ = State::IDLE;
  uint32_t since_ = 0;       // inicio del estado actual
  uint32_t stillSince_ = 0;  // inicio del último tramo sin movimiento
  float peak_ = 0.0f;        // pico del impacto
  float ffMin_ = 1.0f;       // |a| mínimo durante la caída libre
  float ffMax_ = 0.0f;       // |a| máximo después de la caída libre

  const char* noteText_ = nullptr;
  float notePeak_ = 0.0f, noteMin_ = 0.0f;
  uint32_t lastBumpNote_ = 0;
};
