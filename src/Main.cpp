#include "FractalThing.h"
#include "MidiExport.h"
#include <iostream>
#include <cmath>
#include <iomanip>
#include <limits>
#include <stdexcept>
#include <string>

namespace {

double parseCoordinate(const char* argument) {
    std::size_t end;
    const std::string text(argument);
    const double value = std::stod(text, &end);
    if (end != text.size() || !std::isfinite(value)) {
        throw std::invalid_argument("Coordinates must be finite numbers.");
    }
    return value;
}

unsigned int parseIterations(const char* argument) {
    const std::string text(argument);
    if (text.empty() || text.find_first_not_of("0123456789") != std::string::npos) {
        throw std::invalid_argument("Iterations must be a positive integer.");
    }
    const auto value = std::stoull(text);
    if (value == 0 || value > std::numeric_limits<unsigned int>::max()) {
        throw std::invalid_argument("Iterations are outside the supported range.");
    }
    return static_cast<unsigned int>(value);
}

void printUsage(const char* program) {
    std::cout << "Usage: " << program
              << " --re MIN MAX --im MIN MAX --iterations COUNT [--phrases 1..16]\n";
}
}

int main(int argc, char* argv[]) {
    if (argc == 2 && std::string(argv[1]) == "--help") {
        printUsage(argv[0]);
        return 0;
    }

    FractalThing::Settings settings{};
    unsigned int phrases = 1;
    bool havePhrases = false;
    bool haveRe = false, haveIm = false, haveIterations = false;
    try {
        for (int i = 1; i < argc; ++i) {
            const std::string option(argv[i]);
            if (option == "--re" && !haveRe && i + 2 < argc) {
                settings.reMin = parseCoordinate(argv[++i]);
                settings.reMax = parseCoordinate(argv[++i]);
                haveRe = true;
            } else if (option == "--im" && !haveIm && i + 2 < argc) {
                settings.imMin = parseCoordinate(argv[++i]);
                settings.imMax = parseCoordinate(argv[++i]);
                haveIm = true;
            } else if (option == "--iterations" && !haveIterations && i + 1 < argc) {
                settings.iterations = parseIterations(argv[++i]);
                haveIterations = true;
            } else if (option == "--phrases" && !havePhrases && i + 1 < argc) {
                phrases = parseIterations(argv[++i]);
                if (phrases > 16) throw std::invalid_argument("Phrase count must be between 1 and 16.");
                havePhrases = true;
            } else {
                throw std::invalid_argument("Unknown, duplicate or incomplete option: " + option);
            }
        }
        if (!haveRe || !haveIm || !haveIterations) {
            throw std::invalid_argument("Supply --re, --im and --iterations.");
        }
        if (settings.reMin >= settings.reMax || settings.imMin >= settings.imMax) {
            throw std::invalid_argument("Each interval must have MIN < MAX.");
        }
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        printUsage(argv[0]);
        return 1;
    }

    std::cout << std::setprecision(15)
              << "Re: [" << settings.reMin << ", " << settings.reMax << "]\n"
              << "Im: [" << settings.imMin << ", " << settings.imMax << "]\n"
              << "Iterations: " << settings.iterations << '\n';

    try {
        FractalThing fractal;
        const auto arrangement = fractal.generateArrangement(settings, phrases);
        exportMidi(arrangement, "MyMidiFile.mid", phrases * FractalThing::phraseTicks);
        std::cout << "Exported " << arrangement[0].notes.size()
                  << " melody notes, 4 tracks: " << phrases * 8
                  << " bars, D Dorian, 108 BPM -> MyMidiFile.mid\n";
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
