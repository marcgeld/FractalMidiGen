"""Verify FractalMidiGen output: format 1, four tracks, D Dorian, 8–128 bars."""
import argparse
from pathlib import Path
import struct
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(path):
    data = Path(path).read_bytes()
    require(len(data) >= 14 and data[:4] == b'MThd', 'Missing or truncated MIDI header')
    header = struct.unpack_from('>IHHH', data, 4)
    require(header == (6, 1, 4, 480),
            f'Expected header (length=6, format=1, tracks=4, PPQ=480); got {header}')
    position = 14
    total_ticks = None
    for track in range(4):
        require(data[position:position+4] == b'MTrk' and position+8 <= len(data),
                f'Track {track}: missing or truncated chunk header')
        size = int.from_bytes(data[position+4:position+8], 'big')
        position += 8
        body = data[position:position+size]
        require(len(body) == size, f'Track {track}: truncated chunk')
        position += size
        offset = tick = 0
        active, notes, metas, programs = {}, [], [], []
        ended = False

        def take(count):
            nonlocal offset
            result = body[offset:offset+count]
            require(len(result) == count, f'Track {track}: truncated event')
            offset += count
            return result

        def vlq():
            value = 0
            for _ in range(4):
                byte = take(1)[0]
                value = (value << 7) | (byte & 127)
                if byte < 128:
                    return value
            raise ValueError(f'Track {track}: oversized variable-length integer')

        while offset < len(body):
            tick += vlq()
            status = take(1)[0]
            if status == 255:
                kind = take(1)[0]
                payload = take(vlq())
                metas.append((tick, kind, payload))
                if kind == 47:
                    require(not payload and offset == len(body) and not active,
                            f'Track {track}: invalid end event or unclosed notes')
                    ended = True
            else:
                channel = track - 1
                if track > 0 and status == (192 | channel):
                    program = take(1)[0]
                    programs.append((tick, program))
                    continue
                require(track > 0 and status in (128 | channel, 144 | channel),
                        f'Track {track}: unexpected status 0x{status:02x}')
                pitch, velocity = take(2)
                require(pitch < 128 and velocity < 128, 'Invalid MIDI data byte')
                if status >> 4 == 9 and velocity:
                    require(pitch not in active, 'Overlapping notes of the same pitch')
                    if track != 3:
                        require(not active, 'Melody and bass must be monophonic')
                    low, high = (38, 55) if track == 2 else (50, 74)
                    require(low <= pitch <= high and (pitch-50) % 12 in (0,2,3,5,7,9,10),
                            f'Track {track}: pitch {pitch} is outside its D Dorian register')
                    low_velocity, high_velocity = [(72,96),(60,84),(48,72)][track-1]
                    require(low_velocity <= velocity <= high_velocity,
                            'Velocity outside track range')
                    active[pitch] = tick
                    notes.append((tick, pitch))
                else:
                    require(pitch in active, f'Unmatched note-off for pitch {pitch}')
                    require(tick > active.pop(pitch), 'Note duration must be positive')
        require(ended, f'Track {track}: missing end-of-track event')
        if track == 0:
            total_ticks = tick
            require(15360 <= tick <= 16*15360 and tick % 15360 == 0,
                    'Duration must be 1–16 complete eight-bar phrases')
            require(metas == [(0,81,(60000000 // 108).to_bytes(3,'big')),
                              (0,88,bytes([4,2,24,8])), (total_ticks,47,b'')],
                    'Expected tempo 108 BPM, 4/4, and matching phrase end event')
        else:
            require([m for m in metas if m[1] != 3] == [(total_ticks,47,b'')], 'Tracks must have the same duration')
            require(programs == [(0, [0,32,48][track-1])], 'Unexpected instrument program')
            require((0,3,[b'Melody', b'Bass', b'Harmony'][track-1]) in metas,
                    'Missing track name')
            if track != 1:
                expected = ([bar*1920 + beat*960 for bar in range(total_ticks // 1920) for beat in range(2)]
                            if track == 2 else [bar*1920 for bar in range(total_ticks // 1920) for _ in range(3)])
                require([t for t, _ in notes] == expected, 'Unexpected accompaniment rhythm')
                require(notes[-1][1] == 38 if track == 2 else
                        sorted(p for t, p in notes if t == total_ticks - 1920) == [50,53,57],
                        'Accompaniment must resolve to D')
                print(f'Track {track}: {len(notes)} notes, end {tick}, balanced note events')
                continue
            require(notes and notes[0] == (0,62) and notes[-1] == (total_ticks-960,62),
                    'Phrase must start on D4 and finish with a D4 half note')
            for bar in range(total_ticks // 1920):
                starts = [t-bar*1920 for t, _ in notes if bar*1920 <= t < (bar+1)*1920]
                patterns = ([0,960], [0,480,960]) if bar % 8 == 7 else (
                    [0,960], [0,480,960,1440]) if bar % 8 == 6 else (
                    [0,960], [0,480,960,1440], list(range(0,1920,240)))
                require(starts in patterns, f'Bar {bar+1}: unexpected rhythm')
        print(f'Track {track}: {len(notes)} notes, end {tick}, balanced note events')
    require(position == len(data), 'Unexpected data after the declared tracks')
    print('PASS: format 1, four tracks, 108 BPM, 4/4, D Dorian, 8–128 bars and balanced notes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('midi', type=Path)
    args = parser.parse_args()
    try:
        verify(args.midi)
    except (OSError, ValueError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
