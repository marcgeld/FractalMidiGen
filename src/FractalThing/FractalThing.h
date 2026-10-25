#pragma once

#include <cstdint>
#include <vector>
#include <array>
#include <string>

// Deterministic Mandelbrot sampling and melodic mapping.
class FractalThing {
public:
    struct Settings {
        double reMin, reMax, imMin, imMax;
        unsigned int iterations;
    };

    struct FractalPoint {
        double real = 0.0;
        double imaginary = 0.0;
        unsigned int iterations = 0;
        bool escaped = false;
        double escapeValue = 1.0;
        double orbitValue = 0.0;
    };

    struct MidiNote {
        std::uint32_t startTick = 0;    // Absolute position in MIDI ticks.
        std::uint32_t durationTicks = 480;
        std::uint8_t pitch = 60;        // MIDI pitch: 0–127.
        std::uint8_t velocity = 100;    // Note-on velocity: 1–127.
        std::uint8_t channel = 0;       // MIDI channel: 0–15.
    };

    virtual ~FractalThing() = default;

    struct MidiTrack {
        std::string name;
        std::uint8_t channel;
        std::uint8_t program; // Zero-based General MIDI program.
        std::vector<MidiNote> notes;
    };
    using Arrangement = std::array<MidiTrack, 3>;
    Arrangement generateArrangement(const Settings& settings, unsigned int phrases = 1) const;

    static constexpr unsigned int ticksPerQuarter = 480;
    static constexpr unsigned int tempoBpm = 108;
    static constexpr unsigned int phraseTicks = 8 * 4 * ticksPerQuarter;

    std::vector<FractalPoint> sample(const Settings& settings) const;
    std::vector<MidiNote> generateNotes(const Settings& settings) const;

    // Returned notes describe note-on positions and durations, not file bytes.
    // Implementations must keep MIDI values within the ranges documented above.
    virtual std::vector<MidiNote> generateNotes(
        const std::vector<FractalPoint>& points) const;
};
