#include "FractalThing.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>

std::vector<FractalThing::FractalPoint>
FractalThing::sample(const Settings &s) const {
  if (!std::isfinite(s.reMin) || !std::isfinite(s.reMax) ||
      !std::isfinite(s.imMin) || !std::isfinite(s.imMax) ||
      s.reMin >= s.reMax || s.imMin >= s.imMax || s.iterations == 0) {
    throw std::invalid_argument("Invalid fractal bounds or iteration limit.");
  }
  constexpr double pi = 3.14159265358979323846;
  std::vector<FractalPoint> points;
  points.reserve(513);
  for (unsigned int j = 0; j <= 512; ++j) {
    const double t = j / 512.0;
    const double u = 0.5 + 0.45 * std::sin(4.0 * pi * t);
    FractalPoint p;
    // Weighted interpolation avoids overflowing the width of large intervals.
    p.real = (1.0 - t) * s.reMin + t * s.reMax;
    p.imaginary = (1.0 - u) * s.imMin + u * s.imMax;
    double a = 0.0, b = 0.0, orbitSum = 0.0;
    for (unsigned int n = 0; n < s.iterations; ++n) {
      const double nextA = a * a - b * b + p.real;
      b = 2.0 * a * b + p.imaginary;
      a = nextA;
      const double magnitude = std::hypot(a, b);
      p.iterations = n + 1;
      orbitSum += std::min(magnitude, 2.0) / 2.0;
      if (magnitude > 2.0) {
        p.escaped = true;
        const double smooth =
            p.iterations + 1.0 - std::log2(std::log(magnitude));
        p.escapeValue = std::clamp(smooth / s.iterations, 0.0, 1.0);
        break;
      }
    }
    p.orbitValue = orbitSum / p.iterations;
    points.push_back(p);
  }
  return points;
}

std::vector<FractalThing::MidiNote>
FractalThing::generateNotes(const Settings &s) const {
  return generateNotes(sample(s));
}

std::vector<FractalThing::MidiNote>
FractalThing::generateNotes(const std::vector<FractalPoint> &points) const {
  if (points.size() != 513) {
    throw std::invalid_argument(
        "The phrase requires exactly 513 ordered samples.");
  }
  for (const auto &p : points) {
    if (!std::isfinite(p.escapeValue) || !std::isfinite(p.orbitValue) ||
        p.escapeValue < 0 || p.escapeValue > 1 || p.orbitValue < 0 ||
        p.orbitValue > 1) {
      throw std::invalid_argument(
          "Sample features must be finite values in [0, 1].");
    }
  }
  // D3 through D5, D Dorian. Index 7 is D4; indices 4..10 are A3..G4.
  constexpr std::array<int, 15> scale{50, 52, 53, 55, 57, 59, 60, 62,
                                      64, 65, 67, 69, 71, 72, 74};
  constexpr unsigned int barTicks = 4 * ticksPerQuarter;
  std::vector<MidiNote> notes;
  int previous = 7;
  for (unsigned int bar = 0; bar < 8; ++bar) {
    const unsigned int begin = bar * 64;
    double activity = 0.0;
    for (unsigned int j = begin; j < begin + 64; ++j) {
      activity +=
          std::abs(points[j + 1].escapeValue - points[j].escapeValue) +
          0.5 * std::abs(points[j + 1].orbitValue - points[j].orbitValue);
    }
    activity = std::clamp(8.0 * activity / 64.0, 0.0, 1.0);
    unsigned int count = activity < 0.08 ? 2 : (activity < 0.22 ? 4 : 8);
    if (bar >= 6)
      count = std::min(count, 4u);
    const unsigned int slot = barTicks / count;
    const int maxStep =
        bar >= 6 || activity < 0.08 ? 1 : (activity < 0.22 ? 2 : 3);
    const auto velocity =
        static_cast<std::uint8_t>(std::lround(72 + 24 * activity));
    for (unsigned int k = 0; k < count; ++k) {
      const unsigned int position = k * slot;
      if (bar == 7 && position >= barTicks / 2)
        break;
      double q = 0.0, g = 0.0;
      const unsigned int samples = 64 / count;
      for (unsigned int j = begin + k * samples; j < begin + (k + 1) * samples;
           ++j) {
        q += points[j].escapeValue;
        g += points[j].orbitValue;
      }
      int target =
          static_cast<int>(std::lround(14 * (0.75 * q + 0.25 * g) / samples));
      if (bar == 2 || bar == 3)
        target += 2;
      target = std::clamp(target, 0, 14);
      if (bar == 7)
        target = std::clamp(target, 4, 10);
      int pitch = previous + std::clamp(target - previous, -maxStep, maxStep);
      // Enter the cadence register before the final tonic.
      if (bar == 7)
        pitch = std::clamp(pitch, 4, 10);
      if (notes.empty())
        pitch = 7;
      notes.push_back({bar * barTicks + position, slot * 9 / 10,
                       static_cast<std::uint8_t>(scale[pitch]), velocity, 0});
      previous = pitch;
    }
    if (bar == 7) {
      notes.push_back(
          {bar * barTicks + barTicks / 2, barTicks / 2, 62, velocity, 0});
    }
  }
  return notes;
}

FractalThing::Arrangement
FractalThing::generateArrangement(const Settings &settings,
                                  unsigned int phrases) const {
  if (phrases == 0 || phrases > 16) {
    throw std::invalid_argument("Phrase count must be between 1 and 16.");
  }
  if (phrases > 1) {
    Arrangement result{
        {{"Melody", 0, 0, {}}, {"Bass", 1, 32, {}}, {"Harmony", 2, 48, {}}}};
    // Traverse adjacent vertical strips of the original region, left to right.
    for (unsigned int phrase = 0; phrase < phrases; ++phrase) {
      Settings region = settings;
      const double left = static_cast<double>(phrase) / phrases;
      const double right = static_cast<double>(phrase + 1) / phrases;
      region.reMin = (1.0 - left) * settings.reMin + left * settings.reMax;
      region.reMax = (1.0 - right) * settings.reMin + right * settings.reMax;
      const auto part = generateArrangement(region);
      for (std::size_t track = 0; track < result.size(); ++track) {
        for (auto note : part[track].notes) {
          note.startTick += phrase * phraseTicks;
          result[track].notes.push_back(note);
        }
      }
    }
    return result;
  }
  Arrangement arrangement{{{"Melody", 0, 0, generateNotes(settings)},
                           {"Bass", 1, 32, {}},
                           {"Harmony", 2, 48, {}}}};
  constexpr std::array<int, 7> degrees{0, 2, 3, 5, 7, 9, 10};
  const auto scalePitch = [&](int degree) {
    return 50 + 12 * (degree / 7) + degrees[degree % 7];
  };
  for (unsigned int bar = 0; bar < 8; ++bar) {
    const auto first = std::find_if(
        arrangement[0].notes.begin(), arrangement[0].notes.end(),
        [bar](const MidiNote &n) { return n.startTick == bar * 1920; });
    if (first == arrangement[0].notes.end()) {
      throw std::invalid_argument("Each bar must start with a melody note.");
    }
    const int pitchClass = (first->pitch - 50) % 12;
    const auto degree = std::find(degrees.begin(), degrees.end(), pitchClass);
    if (degree == degrees.end())
      throw std::invalid_argument("Melody must use D Dorian.");
    // Root follows the fractal melody; the final bar resolves to D minor.
    const int root = bar == 7 ? 0 : static_cast<int>(degree - degrees.begin());
    const auto bassVelocity = static_cast<std::uint8_t>(first->velocity - 12);
    const auto harmonyVelocity =
        static_cast<std::uint8_t>(first->velocity - 24);
    for (unsigned int beat = 0; beat < 2; ++beat) {
      const int pitch = scalePitch(root + (beat == 1 && bar != 7 ? 4 : 0)) - 12;
      arrangement[1].notes.push_back(
          {bar * 1920 + beat * 960, bar == 7 && beat == 1 ? 960u : 864u,
           static_cast<std::uint8_t>(pitch), bassVelocity, 1});
    }
    for (int interval : {0, 2, 4}) {
      arrangement[2].notes.push_back(
          {bar * 1920, bar == 7 ? 1920u : 1728u,
           static_cast<std::uint8_t>(scalePitch(root + interval)),
           harmonyVelocity, 2});
    }
  }
  return arrangement;
}
