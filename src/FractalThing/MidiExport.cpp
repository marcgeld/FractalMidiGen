#include "MidiExport.h"

#include <algorithm>
#include <fstream>
#include <stdexcept>

namespace {
using Bytes = std::vector<unsigned char>;
void bigEndian(Bytes &out, std::uint32_t value, unsigned int width) {
  for (unsigned int i = width; i > 0; --i)
    out.push_back((value >> ((i - 1) * 8)) & 255);
}
void variable(Bytes &out, std::uint32_t value) {
  unsigned char bytes[4];
  unsigned int count = 0;
  bytes[count++] = value & 127;
  while ((value >>= 7) != 0)
    bytes[count++] = (value & 127) | 128;
  while (count > 0)
    out.push_back(bytes[--count]);
}
void track(Bytes &out, const Bytes &data) {
  out.insert(out.end(), {'M', 'T', 'r', 'k'});
  bigEndian(out, static_cast<std::uint32_t>(data.size()), 4);
  out.insert(out.end(), data.begin(), data.end());
}
} // namespace

void exportMidi(const FractalThing::Arrangement &arrangement,
                const std::string &filename, std::uint32_t totalTicks) {
  if (totalTicks == 0 || totalTicks > 16 * FractalThing::phraseTicks ||
      totalTicks % FractalThing::phraseTicks != 0) {
    throw std::invalid_argument("Invalid arrangement duration.");
  }
  struct Event {
    std::uint32_t tick;
    unsigned char status, pitch, velocity;
  };
  Bytes file{'M', 'T', 'h', 'd'};
  bigEndian(file, 6, 4);
  bigEndian(file, 1, 2);
  bigEndian(file, 4, 2);
  bigEndian(file, FractalThing::ticksPerQuarter, 2);
  Bytes tempo{0, 0xff, 0x51, 3};
  bigEndian(tempo, 60000000 / FractalThing::tempoBpm, 3);
  tempo.insert(tempo.end(), {0, 0xff, 0x58, 4, 4, 2, 24, 8});
  variable(tempo, totalTicks);
  tempo.insert(tempo.end(), {0xff, 0x2f, 0});
  track(file, tempo);
  for (std::size_t index = 0; index < arrangement.size(); ++index) {
    const auto &part = arrangement[index];
    if (part.channel != index || part.program > 127) {
      throw std::invalid_argument("Invalid track channel or program.");
    }
    std::vector<Event> events;
    for (const auto &n : part.notes) {
      if (n.pitch > 127 || n.velocity == 0 || n.velocity > 127 ||
          n.channel != part.channel || n.durationTicks == 0 ||
          n.startTick >= totalTicks ||
          n.durationTicks > totalTicks - n.startTick) {
        throw std::invalid_argument("Invalid MIDI note.");
      }
      events.push_back({n.startTick,
                        static_cast<unsigned char>(0x90 | n.channel), n.pitch,
                        n.velocity});
      events.push_back({n.startTick + n.durationTicks,
                        static_cast<unsigned char>(0x80 | n.channel), n.pitch,
                        0});
    }
    std::stable_sort(
        events.begin(), events.end(), [](const Event &a, const Event &b) {
          if (a.tick != b.tick)
            return a.tick < b.tick;
          return a.status <
                 b.status; // Note-offs precede note-ons at the same tick.
        });
    Bytes melody{0, 0xff, 3};
    variable(melody, static_cast<std::uint32_t>(part.name.size()));
    melody.insert(melody.end(), part.name.begin(), part.name.end());
    melody.insert(
        melody.end(),
        {0, static_cast<unsigned char>(0xc0 | part.channel), part.program});
    std::uint32_t previous = 0;
    for (const auto &e : events) {
      variable(melody, e.tick - previous);
      melody.insert(melody.end(), {e.status, e.pitch, e.velocity});
      previous = e.tick;
    }
    variable(melody, totalTicks - previous);
    melody.insert(melody.end(), {0xff, 0x2f, 0});
    track(file, melody);
  }
  std::ofstream out(filename, std::ios::binary);
  if (!out)
    throw std::runtime_error("Cannot open MIDI output: " + filename);
  out.write(reinterpret_cast<const char *>(file.data()),
            static_cast<std::streamsize>(file.size()));
  out.close();
  if (!out)
    throw std::runtime_error("Cannot write MIDI output: " + filename);
}
