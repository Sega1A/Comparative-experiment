#include "fall_detector.h"

#include <math.h>

#include "settings.h"

void FallDetector::note(const char* text, float peakG, float minG) {
  noteText_ = text;
  notePeak_ = peakG;
  noteMin_ = minG;
}

bool FallDetector::takeNote(const char*& text, float& peakG, float& minG) {
  if (noteText_ == nullptr) return false;
  text = noteText_;
  peakG = notePeak_;
  minG = noteMin_;
  noteText_ = nullptr;
  return true;
}

void FallDetector::startFreefall(float g, uint32_t now) {
  state_ = State::FREEFALL;
  since_ = now;
  ffMin_ = g;
  ffMax_ = 0.0f;
}

FallDetector::Event FallDetector::update(float g, uint32_t now) {
  switch (state_) {
    case State::IDLE:
      if (REQUIRE_FREEFALL) {
        if (g < FREEFALL_G) {
          startFreefall(g, now);
        } else if (g > BUMP_NOTE_G && now - lastBumpNote_ > 500) {
          lastBumpNote_ = now;
          note("golpe_sin_caida_libre", g, 1.0f);  // no cuenta: falta la caída libre
        }
      } else if (g > IMPACT_G) {
        state_ = State::SETTLING;
        since_ = now;
        peak_ = g;
      }
      break;

    case State::FREEFALL:
      if (g < ffMin_) ffMin_ = g;
      if (g > ffMax_) ffMax_ = g;
      if (g > IMPACT_G) {
        state_ = State::SETTLING;
        since_ = now;
        peak_ = g;
      } else if (now - since_ > FREEFALL_TO_IMPACT_MS) {
        // Bajó sin un golpe suficiente: informa cuánto llegó a marcar.
        note("caida_libre_sin_impacto_suficiente", ffMax_, ffMin_);
        state_ = State::IDLE;
      }
      break;

    case State::SETTLING:
      if (g > peak_) peak_ = g;  // rebotes del mismo impacto
      if (now - since_ >= POST_IMPACT_SETTLE_MS) {
        note("caida_detectada", peak_, ffMin_);
        state_ = State::WATCHING;
        since_ = now;
        stillSince_ = now;
        return Event::FALL;
      }
      break;

    case State::WATCHING:
      if (REQUIRE_FREEFALL && g < FREEFALL_G) {
        startFreefall(g, now);  // otra caída mientras se vigilaba la anterior
        break;
      }
      if (fabsf(g - 1.0f) > STILL_TOLERANCE_G) {
        stillSince_ = now;  // se movió: vuelve a contar
      } else if (now - stillSince_ >= IMMOBILITY_MS) {
        state_ = State::IDLE;
        return Event::IMMOBILITY;
      }
      if (now - since_ >= IMMOBILITY_WATCH_MAX_MS) state_ = State::IDLE;  // se recuperó
      break;
  }
  return Event::NONE;
}

void FallDetector::cancelWatch() {
  if (state_ == State::WATCHING || state_ == State::SETTLING) state_ = State::IDLE;
}

const char* FallDetector::stateName() const {
  switch (state_) {
    case State::IDLE:
      return "reposo";
    case State::FREEFALL:
      return "caida_libre";
    case State::SETTLING:
      return "post_impacto";
    case State::WATCHING:
      return "vigilando_inmovilidad";
  }
  return "?";
}
