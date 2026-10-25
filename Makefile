CXX = c++
CPPFLAGS += -Isrc/MidiGen -Isrc/FractalThing
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2
PANDOC ?= pandoc
TYPST ?= typst
PDF := build/FractalMidiGen.pdf

TARGET := build/fractalmg
RE_MIN ?= -1.194874414
RE_MAX ?= -0.9328628317
IM_MIN ?= -0.3278728806
IM_MAX ?= -0.1392245412
ITERATIONS ?= 352
PHRASES ?= 4
# The course example src/MidiGen/Main.cpp is intentionally excluded.
SOURCES := $(wildcard src/*.cpp src/FractalThing/*.cpp) src/MidiGen/MidiGen.cpp
OBJECTS := $(patsubst src/%.cpp,build/%.o,$(SOURCES))
DEPS := $(OBJECTS:.o=.d)

.PHONY: all run test pdf clean
.DELETE_ON_ERROR:
.DEFAULT_GOAL := all

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CXX) $(LDFLAGS) -o $@ $^ $(LDLIBS)

build/%.o: src/%.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -MMD -MP -c $< -o $@

run: $(TARGET)
	./$(TARGET) --re $(RE_MIN) $(RE_MAX) --im $(IM_MIN) $(IM_MAX) --iterations $(ITERATIONS) --phrases $(PHRASES)

clean:
	rm -rf build

test: $(TARGET)
	python3 tests/test_melody.py

pdf: $(PDF)

$(PDF): README.md Makefile
	@mkdir -p $(dir $@)
	$(PANDOC) README.md --from=gfm --standalone --toc --number-sections \
		--pdf-engine=$(TYPST) --variable=papersize:a4 \
		--variable=fontsize:11pt --output=$@

-include $(DEPS)
