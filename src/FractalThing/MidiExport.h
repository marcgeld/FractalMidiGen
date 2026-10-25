#pragma once

#include "FractalThing.h"
#include <string>

// Project-owned exporter; the original course implementation remains unchanged.
void exportMidi(const FractalThing::Arrangement& arrangement,
                const std::string& filename, std::uint32_t totalTicks = FractalThing::phraseTicks);
