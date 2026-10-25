#!/usr/bin/env python3
"""Play MIDI using a small built-in synth and the operating system's WAV player.

Usage:
    python3 midi_player.py fractal-example.mid
    python3 midi_player.py fractal-example.mid --wav preview.wav

No third-party Python packages or soundfont required. Supports SMF format 0/1,
PPQ timing, tempo changes, programs, velocity, sustain and running status.
This is a listening aid, not a General MIDI renderer: piano, celesta and strings
use approximate harmonic waveforms. Pitch bend, drums and other controllers
are ignored. Rendering happens before playback; --wav exports without playing.
"""
import argparse
from array import array
from bisect import bisect_right
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import wave


def read_midi(path):
    """Return sorted (absolute_tick, sequence, kind, channel, data) events."""
    data = Path(path).read_bytes()
    if len(data) < 14 or data[:4] != b'MThd':
        raise ValueError('Not a Standard MIDI File')
    header_size, fmt, track_count, ppq = struct.unpack_from('>IHHH', data, 4)
    if header_size < 6 or fmt not in (0, 1) or not ppq or ppq & 0x8000:
        raise ValueError('Requires MIDI format 0/1 with PPQ timing')
    position = 8 + header_size
    events = []
    sequence = 0
    end_tick = 0
    for _ in range(track_count):
        if data[position:position + 4] != b'MTrk':
            raise ValueError('Missing MIDI track')
        size = struct.unpack_from('>I', data, position + 4)[0]
        position += 8
        track = data[position:position + size]
        if len(track) != size:
            raise ValueError('Truncated MIDI track')
        position += size
        offset = tick = 0
        running_status = None

        def take(count):
            nonlocal offset
            result = track[offset:offset + count]
            if len(result) != count:
                raise ValueError('Truncated MIDI event')
            offset += count
            return result

        def vlq():
            value = 0
            for _ in range(4):
                byte = take(1)[0]
                value = (value << 7) | (byte & 127)
                if byte < 128:
                    return value
            raise ValueError('Invalid MIDI variable-length integer')

        while offset < len(track):
            tick += vlq()
            status = take(1)[0]
            if status < 128:
                if running_status is None:
                    raise ValueError('Running status without a prior status')
                offset -= 1
                status = running_status
            if status == 255:
                kind = take(1)[0]
                payload = take(vlq())
                if kind == 81:
                    if len(payload) != 3 or not int.from_bytes(payload, 'big'):
                        raise ValueError('Invalid tempo event')
                    events.append((tick, sequence, 'tempo', 0, int.from_bytes(payload, 'big')))
                if kind == 47:
                    break
            elif status in (240, 247):
                running_status = None
                take(vlq())
            elif 128 <= status < 240:
                running_status = status
                kind, channel = status >> 4, status & 15
                payload = take(1 if kind in (12, 13) else 2)
                if any(byte >= 128 for byte in payload):
                    raise ValueError('Invalid MIDI data byte')
                events.append((tick, sequence, kind, channel, payload))
            else:
                raise ValueError('Unsupported MIDI status')
            sequence += 1
        end_tick = max(end_tick, tick)
    return sorted(events), ppq, end_tick


def collect_notes(events, ppq, end_tick):
    """Apply tempo, program and sustain state to produce notes in seconds."""
    tempo_ticks, tempo_seconds, tempos = [0], [0.0], [500000]
    for tick, _, kind, _, value in events:
        if kind == 'tempo':
            seconds = tempo_seconds[-1] + (tick - tempo_ticks[-1]) * tempos[-1] / (ppq * 1e6)
            tempo_ticks.append(tick)
            tempo_seconds.append(seconds)
            tempos.append(value)

    def seconds(tick):
        index = bisect_right(tempo_ticks, tick) - 1
        return tempo_seconds[index] + (tick - tempo_ticks[index]) * tempos[index] / (ppq * 1e6)

    programs = [0] * 16
    sustain = [False] * 16
    active = {}
    held = [[] for _ in range(16)]
    notes = []

    def finish(note, tick):
        start, pitch, velocity, program = note
        notes.append((seconds(start), seconds(tick), pitch, velocity, program))

    for tick, _, kind, channel, payload in events:
        if kind == 'tempo':
            continue
        if kind == 12:
            programs[channel] = payload[0]
        elif kind == 11 and payload[0] == 64:
            sustain[channel] = payload[1] >= 64
            if not sustain[channel]:
                for note in held[channel]:
                    finish(note, tick)
                held[channel].clear()
        elif kind in (8, 9):
            pitch, velocity = payload
            key = (channel, pitch)
            if kind == 9 and velocity:
                # Multiple voices on the same pitch are paired FIFO.
                active.setdefault(key, []).append((tick, pitch, velocity, programs[channel]))
            elif active.get(key):
                note = active[key].pop(0)
                if sustain[channel]:
                    held[channel].append(note)
                else:
                    finish(note, tick)
    for voices in active.values():
        for note in voices:
            finish(note, end_tick)
    for voices in held:
        for note in voices:
            finish(note, end_tick)
    return notes, seconds(end_tick)


def render(path, destination, sample_rate):
    events, ppq, end_tick = read_midi(path)
    notes, length = collect_notes(events, ppq, end_tick)
    if length > 600:
        raise ValueError('This small player supports files up to 10 minutes')
    # Float accumulation preserves polyphony; normalize only after mixing.
    mix = array('f', [0.0]) * (int((length + 0.6) * sample_rate) + 1)
    print(f'Rendering {len(notes)} notes, {length:.1f} seconds...', flush=True)
    for start, end, pitch, velocity, program in notes:
        frequency = 440.0 * 2 ** ((pitch - 69) / 12)
        release = 0.3 if 48 <= program <= 55 else 0.12
        attack = 0.07 if 48 <= program <= 55 else 0.005
        first = int(start * sample_rate)
        stop = min(len(mix), int((end + release) * sample_rate))
        step = 2 * math.pi * frequency / sample_rate
        for index in range(first, stop):
            age = (index - first) / sample_rate
            envelope = min(1.0, age / attack) * max(0.0, 1 - max(0.0, start + age - end) / release)
            if not 48 <= program <= 55:
                envelope *= math.exp(-age * (2.2 if program == 8 else 1.5))
            phase = (index - first) * step
            # Suppress harmonics above Nyquist instead of introducing aliasing.
            tone = math.sin(phase) if frequency < sample_rate / 2 else 0.0
            for harmonic, weight in ((2, 0.25), (3, 0.12)):
                if frequency * harmonic < sample_rate / 2:
                    tone += weight * math.sin(phase * harmonic)
            mix[index] += tone * envelope * velocity / 127
    peak = max((abs(value) for value in mix), default=0.0)
    gain = 0.85 * 32767 / max(peak, 1.0)
    pcm = array('h', (int(value * gain) for value in mix))
    if sys.byteorder != 'little':
        pcm.byteswap()
    with wave.open(str(destination), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())


def play(path):
    if sys.platform == 'darwin':
        command = ['afplay', str(path)]
    elif sys.platform == 'win32':
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return
    else:
        player = next((name for name in ('aplay', 'paplay', 'ffplay') if shutil.which(name)), None)
        if player is None:
            raise RuntimeError('No WAV player found; use --wav to export instead')
        command = [player, str(path)]
        if player == 'ffplay':
            command = [player, '-nodisp', '-autoexit', '-loglevel', 'error', str(path)]
    process = subprocess.Popen(command)
    try:
        if process.wait():
            raise RuntimeError('Audio playback failed')
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('midi', type=Path)
    parser.add_argument('--wav', type=Path, help='Export WAV without playing')
    parser.add_argument('--sample-rate', type=int, default=22050, choices=(22050, 44100))
    args = parser.parse_args()
    if args.wav:
        if args.midi.resolve() == args.wav.resolve():
            parser.error('MIDI input and WAV output must be different files')
        render(args.midi, args.wav, args.sample_rate)
        print(f'Saved {args.wav}')
    else:
        with tempfile.TemporaryDirectory(prefix='midi-player-') as directory:
            output = Path(directory) / 'playback.wav'
            render(args.midi, output, args.sample_rate)
            print('Playing. Press Ctrl+C to stop.', flush=True)
            play(output)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped.')
    except (OSError, ValueError, RuntimeError, struct.error) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
