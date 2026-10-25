# FractalMidiGen

Generate music from a Mandelbrot Fractal

The idea is to treat the numerical behaviour of a fractal as composition
material. We choose a region of the Mandelbrot plane, follow a fixed path
through it, and let the resulting orbits influence melodic contour, rhythmic
density and dynamics. A shared musical framework turns those measurements into
a recognisable phrase and a three-part arrangement.

The fractal supplies variation; our composition rules supply the scale,
register, tempo, instrumentation and phrase structure. These are deliberate
musical choices, not properties that Mandelbrot mathematics uniquely dictates.

`src/FractalThing/FractalThing.h` defines the Mandelbrot sampler and deterministic
melody generator. `generateNotes(settings)` converts the selected region into
MIDI notes (start tick, duration, pitch, velocity and channel). The overload
accepting samples is virtual so subclasses can provide other musical mappings.

Build with `make` (requires a C++17 compiler), then run with `make run`.
The executable is written to `build/fractalmg`. Running it generates
`MyMidiFile.mid` in the current directory. Use `make clean` to remove build files.

`make run` uses the following fractal parameters:

```sh
./build/fractalmg --re -1.194874414 -0.9328628317 --im -0.3278728806 -0.1392245412 --iterations 352 --phrases 4
```

Override them with, for example, `make run ITERATIONS=512 RE_MIN=-1.2`.
`make run` defaults to four eight-bar phrases (32 bars, approximately 71 seconds).
Use `make run PHRASES=8` for 64 bars or `make run PHRASES=1` for the original
eight-bar version. The optional CLI argument `--phrases` accepts 1–16; when
omitted, the executable generates one phrase.

With multiple phrases, the real interval is split into equally wide adjacent
strips, traversed from left to right. Phrase k (zero-based) uses real bounds
`(1 − k/P) reMin + (k/P) reMax` and
`(1 − (k+1)/P) reMin + ((k+1)/P) reMax`, where P is the phrase count.
The imaginary interval and iteration limit stay the same. Each strip gets
513 samples and its own musical mapping, then its notes are offset by
`k × 15360` ticks. This produces new material rather than looping a MIDI phrase.
Changing the phrase count also changes the sampled strips and therefore the
melodies. Every phrase has its own D cadence; total duration is `P × 15360` ticks.

Both intervals must be increasing and finite; iterations must be a positive
integer. All three options are required when running the executable directly.
The arguments are parsed and validated before generating the fractal melody.

## Fractal parameters and mathematics

### Finding a region with Infinomatic

[Infinomatic on the App Store](https://apps.apple.com/se/app/infinomatic/id6761056274)
is an example of a fractal exploration app that can be used to find a region
for `--re` and `--im`. Explore a Mandelbrot region that interests you, then use
its numerical complex-plane bounds as the input to this project. The app is
an optional way to choose coordinates; it is not a runtime dependency or a
source of pixels for the music generator.

Translate the region's coordinates into arguments as follows:

```text
Left/right bounds:     Re = [−1.194874414, −0.9328628317]
Bottom/top bounds:     Im = [−0.3278728806, −0.1392245412]
Iteration budget:      352

--re -1.194874414 -0.9328628317
--im -0.3278728806 -0.1392245412
--iterations 352
```

Use the smaller coordinate first, including for negative values. Screen
coordinates and complex-plane coordinates can have different vertical
directions: `--im` always means the numerical minimum followed by the maximum.
If a viewer gives a centre `(cx, cy)` and complex-plane width `w` and height `h`
instead of bounds, convert with:

```text
reMin = cx − w/2       reMax = cx + w/2
imMin = cy − h/2       imMax = cy + h/2
```

Width and height here are coordinate spans, not image dimensions in pixels.
A zoom factor alone is insufficient without the viewer's coordinate convention
and aspect ratio. Use the numerical bounds rather than estimating them from a
screenshot. If an iteration setting is available, it can be used as a starting
value for `--iterations`; palette and colouring settings do not affect our music.

### What the inputs mean

The Mandelbrot calculation starts with a complex parameter **c = x + iy**, where
**i² = −1**. The command-line intervals select a rectangular region of the
complex plane from which values of **c** will be sampled:

| Option | Mathematical meaning | Example |
| --- | --- | --- |
| `--re MIN MAX` | Bounds for the real component x = Re(c), the horizontal axis | −1.194874414 ≤ x ≤ −0.9328628317 |
| `--im MIN MAX` | Bounds for the imaginary component y = Im(c), the vertical axis | −0.3278728806 ≤ y ≤ −0.1392245412 |
| `--iterations N` | Maximum number of recurrence steps for each sampled c | N = 352 |

`Re` and `Im` describe the region to explore; they are not the initial value of
the iterated variable **z**. For each sampled **c**, start again at **z₀ = 0**
and apply the Mandelbrot recurrence:

```text
z₀ = 0
zₙ₊₁ = zₙ² + c,    n = 0, …, N − 1
```

Writing **zₙ = aₙ + ibₙ** makes the role of the input coordinates explicit:

```text
a₀ = 0, b₀ = 0
aₙ₊₁ = aₙ² − bₙ² + x    ← x comes from the --re interval
bₙ₊₁ = 2aₙbₙ + y         ← y comes from the --im interval
```

Both new components must be calculated from the previous **aₙ** and **bₙ**.
The parameter **c** stays constant throughout the iterations for that sample.
For example, the lower-left corner of the supplied region gives:

```text
c = −1.194874414 − 0.3278728806i
z₀ = 0
z₁ = c
z₂ = c² + c
… up to z₃₅₂, unless the orbit escapes earlier
```

After each step, check the escape condition:

```text
|zₙ| > 2    ⇔    aₙ² + bₙ² > 4
```

If this condition is met, the orbit escapes and the point is outside the
Mandelbrot set. Otherwise, stop after **N** steps and record that it did not
escape within the iteration budget. A finite budget does not prove that the
point belongs to the set. Increasing `--iterations` can reveal slower escapes;
it does not change the coordinate bounds or the number of sampled points.

## From numerical orbits to music

### Why follow a path rather than read an image?

A rendered fractal assigns colours to numerical results using a palette and
often additional smoothing or shading. Those display choices could change a
pixel-based melody without changing the underlying region. We instead work
directly with complex coordinates and iteration results, so the input remains
mathematical and independent of rendering resolution or colour scheme.

The path establishes an ordering: nearby samples become neighbouring moments
in musical time. Its horizontal component progresses steadily while its
vertical component sweeps twice through the region. This explores more than
a single straight line while preserving local continuity. It covers the inner
90% of the imaginary span, from 5% to 95%, and does not sample every point in
the rectangle. A different sampling path would be a different composition rule.

### Measuring the local behaviour

The following rules describe each eight-bar phrase. The generator uses the
orbits directly; no image or pixel colours are involved.
It samples 513 points using the same path for every region:

```text
t = j / 512, j = 0, …, 512
u = 0.5 + 0.45 sin(4πt)
x = (1 − t) reMin + t reMax
y = (1 − u) imMin + u imMax
c = x + iy
```

For each point, the sampler records two features in [0, 1]:

```text
q = clamp((n + 1 − log₂(log(|zₙ|))) / N, 0, 1) when it escapes
q = 1 when it does not escape within N iterations
g = mean(min(|zₙ|, 2) / 2), over performed steps n = 1, …, escape step or N
```

Features are not rescaled to each region's minimum and maximum, so small local
differences in quiet regions are not artificially amplified.

Here `log` means the natural logarithm, `log₂` means logarithm to base two,
and `clamp(v, 0, 1)` restricts a value to the interval [0, 1]. The escape step
`n` starts at 1. The smooth escape value q reduces the abrupt steps of an
integer escape count. It is an orbit-derived feature, not a geometric distance
to the Mandelbrot boundary. The orbit value g describes the average bounded
magnitude along the computed orbit. It can distinguish points whose q values
are all 1 because none escaped within the budget.

For a fixed N, slowly escaping points tend to have larger q values than quickly
escaping ones. Changing N can therefore change the melody in two ways: it may
reveal additional escapes, and it changes the denominator used to normalise q.
It is not simply a visual quality setting. The sample count stays fixed.

### Turning local changes into rhythm

The 512 steps between samples are split into eight bars of 64 steps. For each
bar, activity is `clamp(8 × mean(|Δq| + 0.5|Δg|), 0, 1)`.
Activity below 0.08 gives two half notes; below 0.22 gives four quarter notes;
otherwise it gives eight eighth notes. Each note averages q and g over its
corresponding sample window, including the first sample and excluding the next
window's first sample. The last point supplies the final activity difference.

The mean absolute differences measure how much the sampled behaviour changes
within a bar. Absolute values count both rises and falls, so alternating
features do not cancel each other. The factor 8 and the thresholds are fixed
musical sensitivity settings. They are design choices rather than mathematical
constants of the fractal.

| Local activity | Notes per bar before the ending rules | Maximum melodic movement |
| --- | --- | --- |
| Below 0.08 | 2 half notes | 1 scale step |
| From 0.08 to below 0.22 | 4 quarter notes | 2 scale steps |
| At least 0.22 | 8 eighth notes | 3 scale steps |

Quiet regions consequently tend towards longer notes and smaller movements.
More rapidly changing regions allow denser rhythms and wider movements.
These rules operate on bar averages: a very brief numerical spike does not
necessarily produce a separate musical gesture. Every bar still occupies
exactly 1920 ticks, regardless of its note count.

### Turning feature levels into melodic contour

Music uses D Dorian from D3 to D5, 108 BPM, 4/4, and 480 ticks per quarter note.
The scale has 15 notes, indexed 0–14. The target index is
`round(14 × (0.75 mean(q) + 0.25 mean(g)))`. The melody approaches this target by
at most one, two or three scale steps for low, medium or high activity.
Velocity is `round(72 + 24 × activity)`. Notes sound for 90% of their rhythmic
slot, except the final sustained note. Rounding uses C++ `std::lround`.

The scale is `D E F G A B C`, repeated across the register. In MIDI numbers the
available notes are `[50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74]`.
The target formula gives q three times the weight of g. Larger feature values
generally ask the melody to move upwards; smaller ones ask it to move downwards.
The movement limit prevents it from jumping directly between distant targets.
A scale step means moving to an adjacent note in this list, not necessarily
moving one semitone.

For example, if a note window has mean q = 0.60 and mean g = 0.40, its target
index is `round(14 × 0.55) = 8`, corresponding to E4. Starting from D4 at
index 7, even a quiet bar can reach it. A more distant target is approached
over several notes. This creates continuity while retaining the broad shape
of the fractal-derived signal. Repeated notes are allowed when the target is
already reached or quantisation produces the same index.

The 90% note duration leaves a small articulation gap. Velocity follows the
bar's activity rather than an independent random process, so changes in energy
are related to changes in rhythm and permitted interval size.

### Giving each phrase a beginning, development and ending

The phrase starts on D4. Bars 3–4 raise target indices by two scale steps;
bars 5–6 return to the original mapping. Bars 7–8 use at most four notes per bar
and at most one scale step per movement. In bar 8, target and resulting indices
are constrained to A3–G4; entering this range can override the one-step limit.
Its second half is replaced by a sustained D4 half note. Target indices always
stay within the scale. The phrase ends at tick 15360, exactly eight bars.

| Bars within a phrase | Musical purpose | Fixed shaping rule |
| --- | --- | --- |
| 1–2 | Establish a centre and introduce material | Begin on D4, then follow the feature targets |
| 3–4 | Develop the contour | Raise target indices by two scale steps, within the register |
| 5–6 | Return to the original mapping | Remove the target offset |
| 7 | Reduce activity before the ending | At most four notes per bar and one scale step per movement |
| 8 | Resolve the phrase | Restrict the cadence register and finish on a D4 half note |

The final D is a compositional anchor. We impose it rather than hoping an
arbitrary final sample happens to produce a convincing ending. With several
phrases, each strip has this same shape and cadence, producing a sequence of
related, self-contained phrases. The current version does not carry melodic
state across phrase boundaries or build a separate large-scale crescendo.

### Variation, determinism and limits

Different regions affect contour, rhythm and velocity, while the shared scale,
register and phrase form keep the results related. Quantisation can make some
regions produce identical melodies. Repeated runs with the same settings and
executable produce identical MIDI bytes; cross-platform floating-point and
math-library differences near thresholds are not guaranteed to be identical.

Two nearby regions can cross different escape transitions and produce different
q/g sequences. Those differences can change a target note, cross a rhythm
threshold, or change velocity. Differences that survive melodic quantisation
also influence the bass and harmony. The common rules keep the results within
the same musical world rather than changing scale or tempo for every region.

This is not a promise that every coordinate change will be audible. Broad,
uniform regions may produce simple or similar phrases, and two different
feature sequences can map to the same notes. Tiny changes below the sampling
resolution may be missed. Fixed scale quantisation and movement limits
deliberately trade some numerical detail for musical coherence. Increasing
the phrase count explores more samples across the full region, but also changes
the partitioning, so it does not merely append notes to an unchanged melody.

There are no random numbers, timestamps or external musical inputs in the
generator. Reproducibility depends on the coordinates, iteration limit, phrase
count and the implemented mapping constants. Tempo, scale and thresholds are
currently fixed in the source rather than command-line settings.

### Arranging the melody across four MIDI tracks

`src/FractalThing/MidiExport.cpp` writes the generated notes as a binary Standard
MIDI File (format 1), with four tracks in total:

| Track | Channel (1-based) | Instrument | Role |
| --- | --- | --- | --- |
| 0 | — | — | Tempo and time signature |
| 1 | 1 | Acoustic Grand Piano (program 0) | Fractal melody |
| 2 | 2 | Acoustic Bass (program 32) | Two half-note slots per bar |
| 3 | 3 | String Ensemble 1 (program 48) | Sustained diatonic triads |

Program numbers above are zero-based. `generateArrangement(settings)` builds
the three musical parts. Each bar's first melody note selects a D Dorian scale
degree as the harmonic root. Bass plays that root one octave below D3–C4,
then its diatonic fifth. Harmony stacks the root, third and fifth in the same
scale. Bass and harmony velocities are respectively 12 and 24 below the first
melody note's velocity. Bass gates are 90% of a half note and chord gates are
90% of a bar. In the last bar, bass stays on D2 and harmony uses D3–F3–A3;
the last bass note and chord sustain to the phrase end. All four tracks end at
the same tick, `phrase count × 15360`. Accompaniment is deterministic and
follows the fractal melody.

The accompaniment is derived from the melody rather than sampled independently.
For example, a first melody note of G selects the diatonic G–B–D triad;
the bass supplies G and its fifth D in a lower register. This ties harmonic
changes to the fractal contour while keeping the accompaniment slower than
the melody. A diatonic fifth means four scale steps above the root; it need
not always be a perfect fifth, as with the B–F interval in this mode.

Using notes from one scale does not guarantee that every passing melody note
is consonant with the sustained chord. The current arrangement permits such
tension; it does not yet optimise voice leading, avoid parallel movements or
analyse functional harmony. Lower accompaniment velocities help preserve the
melody's prominence. MIDI program changes request the named instruments, but
the actual timbres depend on the synthesizer used for playback.

The original course code is retained and built, but its fixed example exporter is not called
by the fractal generator.

Run `make test` (requires Python 3) to check repeatability, different regions and
iteration limits, MIDI structure, scale/register, monophony, phrase ending, and
output-file errors.

## Python tools with uv

The `python/` directory is a uv project defined by `pyproject.toml`. The tools
use only the Python standard library and require Python 3.10 or newer.
Create or synchronise the local environment and run the player:

```sh
cd python
uv sync
uv run midi_player.py ../MyMidiFile.mid
```

Export audio without playback with
`uv run midi_player.py ../MyMidiFile.mid --wav preview.wav`.
The environment is stored in `python/.venv/` and ignored by Git; `uv.lock`
records the project dependencies. Manual activation is optional:
`source .venv/bin/activate` (macOS/Linux).

`uv run verify_midi.py ../MyMidiFile.mid` checks the generated format-1 file:
four tracks, 480 PPQ, 108 BPM, 4/4, D Dorian, instrument programs, monophonic
melody and bass, polyphonic harmony,
eight-bar rhythm and the final D4. It also checks chunk sizes, note balance
and end-of-track events. Invalid files produce a `FAIL` message and exit code 1.

## Build the documentation as PDF

The README is the documentation source. Build a PDF directly with Pandoc and
Typst, without LaTeX or a separate documentation directory:

```sh
brew install pandoc typst
make pdf
open build/FractalMidiGen.pdf
```

The PDF includes a table of contents, numbered sections, tables, formulas and
clickable links. `make pdf` rebuilds it when README.md or the Makefile changes.
`make clean` removes the PDF along with the program's build files. Override
the executables with `PANDOC=...` or `TYPST=...` if needed.

## Code organisation and attribution

| File | Responsibility |
| --- | --- |
| `src/Main.cpp` | Parse arguments, generate the arrangement and request export |
| `src/FractalThing/FractalThing.cpp` | Sample orbits, calculate features, map notes and arrange phrases |
| `src/FractalThing/MidiExport.cpp` | Encode tracks, programs, timing and note events as a MIDI file |
| `python/verify_midi.py` | Independently check the expected generated MIDI structure and musical constraints |
| `python/midi_player.py` | Render MIDI with a small built-in synth for listening or WAV export |

The Python player is a listening aid with approximate synthesized timbres,
not a full General MIDI soundfont renderer. For a different sound, import the
same MIDI file into a DAW and select instruments there.

The course code in `src/MidiGen/MidiGen.cpp` is compiled into a separate object
and linked with the project's `src/Main.cpp`. The course example
`src/MidiGen/Main.cpp` is excluded from the build.

[Artificial Intelligence for Game Programming 1 (5SD809)](https://www.uu.se/en/study/course?query=5SD809) is a 7.5-credit Bachelor's level course offered by Uppsala University (Department of Game Design).

The code in `src/MidiGen/` comes from the course material for this course.
The MIDI generator is written by **Mikael Fridenfalk**, as credited in
`src/MidiGen/MidiGen.cpp`, whose source comments also carry his copyright notice.
The directory includes the supplied example `Main.cpp`; this example is kept
for reference and is excluded from the build. The project's own entry point is
`src/Main.cpp`.
