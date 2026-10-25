"""Integration checks for the generated Standard MIDI File (stdlib only)."""
import pathlib
import struct
import subprocess
import tempfile
import unittest
import sys

EXE = pathlib.Path(__file__).resolve().parents[1] / 'build/fractalmg'
DEFAULT = ['--re', '-1.194874414', '-0.9328628317', '--im',
           '-0.3278728806', '-0.1392245412', '--iterations', '352']


def generate(args):
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run([str(EXE), *args], cwd=directory, check=True,
                       capture_output=True)
        return pathlib.Path(directory, 'MyMidiFile.mid').read_bytes()


def parse(data):
    assert data[:4] == b'MThd'
    assert struct.unpack('>IHHH', data[4:14]) == (6, 1, 4, 480)
    offset, tracks = 14, []
    while offset < len(data):
        assert data[offset:offset+4] == b'MTrk'
        size = int.from_bytes(data[offset+4:offset+8], 'big')
        body = data[offset+8:offset+8+size]
        assert len(body) == size
        pos, tick, events = 0, 0, []

        def variable():
            nonlocal pos
            value = 0
            for _ in range(4):
                byte = body[pos]
                pos += 1
                value = (value << 7) | (byte & 127)
                if byte < 128:
                    return value
            raise AssertionError('Invalid variable length quantity')

        while pos < len(body):
            tick += variable()
            status = body[pos]
            pos += 1
            if status == 255:
                kind = body[pos]
                pos += 1
                length = variable()
                payload = body[pos:pos+length]
                assert len(payload) == length
                pos += length
                events.append((tick, status, kind, payload))
            else:
                if status & 240 == 192:
                    events.append((tick, status, body[pos], None))
                    pos += 1
                    continue
                assert status & 240 in (128, 144)
                pitch, velocity = body[pos:pos+2]
                assert pitch < 128 and velocity < 128
                pos += 2
                events.append((tick, status, pitch, velocity))
        assert events[-1][1:] == (255, 47, b'')
        tracks.append(events)
        offset += 8 + size
    assert offset == len(data) and len(tracks) == 4
    return tracks


class MelodyTests(unittest.TestCase):
    def test_multiple_phrases(self):
        args = DEFAULT + ['--phrases', '4']
        data = generate(args)
        self.assertEqual(data, generate(args))
        tracks = parse(data)
        for track in tracks:
            self.assertEqual(track[-1][0], 4 * 15360)
        melody = [event for event in tracks[1] if event[1] == 144]
        self.assertGreater(len(melody), 64)
        phrases = [[(t % 15360, p, v) for t, s, p, v in melody
                    if i*15360 <= t < (i+1)*15360] for i in range(4)]
        self.assertTrue(any(phrase != phrases[0] for phrase in phrases[1:]))
        verifier = EXE.parent.parent / 'python/verify_midi.py'
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory, 'long.mid')
            path.write_bytes(data)
            result = subprocess.run([sys.executable, str(verifier), str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for count in ('0', '17', '-1', '1.5'):
                result = subprocess.run([str(EXE), *DEFAULT, '--phrases', count],
                                        cwd=directory, capture_output=True)
                self.assertNotEqual(result.returncode, 0)

    def test_independent_verifier(self):
        verifier = EXE.parent.parent / 'python/verify_midi.py'
        data = generate(DEFAULT)
        wrong_header = bytearray(data)
        wrong_header[11] = 2
        wrong_tempo = data.replace((60000000 // 108).to_bytes(3, 'big'),
                                  (750000).to_bytes(3, 'big'), 1)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory, 'test.mid')
            for payload, expected in [(data, 0), (wrong_header, 1),
                                      (wrong_tempo, 1), (data[:-1], 1), (b'', 1)]:
                path.write_bytes(payload)
                result = subprocess.run([sys.executable, str(verifier), str(path)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_reproducibility_and_musical_structure(self):
        data = generate(DEFAULT)
        self.assertEqual(data, generate(DEFAULT))
        tempo, melody, bass, harmony = parse(data)
        self.assertIn((0, 255, 81, (60000000 // 108).to_bytes(3, 'big')), tempo)
        self.assertIn((0, 255, 88, bytes([4, 2, 24, 8])), tempo)
        active, notes = {}, []
        for tick, status, pitch, velocity in melody:
            if status == 144:
                self.assertFalse(active, 'Phrase must be monophonic')
                self.assertTrue(50 <= pitch <= 74)
                self.assertIn((pitch - 50) % 12, [0, 2, 3, 5, 7, 9, 10])
                self.assertTrue(72 <= velocity <= 96)
                active[pitch] = tick
                notes.append((tick, pitch))
            elif status == 128:
                self.assertIn(pitch, active)
                self.assertGreater(tick, active.pop(pitch))
        self.assertFalse(active)
        self.assertEqual(notes[0], (0, 62))
        self.assertEqual(notes[-1], (14400, 62))
        self.assertEqual(melody[-1][0], 15360)
        for index, part in enumerate((melody, bass, harmony)):
            self.assertIn((0, 192 | index, [0, 32, 48][index], None), part)
            self.assertEqual(part[-1][0], 15360)
            active_part = set()
            for tick, status, pitch, velocity in part:
                if status >> 4 == 9:
                    self.assertNotIn(pitch, active_part)
                    active_part.add(pitch)
                elif status >> 4 == 8:
                    self.assertIn(pitch, active_part)
                    active_part.remove(pitch)
            self.assertFalse(active_part)
        self.assertEqual(sum(e[1] == 145 for e in bass), 16)
        self.assertEqual(sum(e[1] == 146 for e in harmony), 24)
        for bar in range(7):
            self.assertIn(sum(bar * 1920 <= t < (bar+1)*1920 for t, _ in notes), [2, 4, 8])

    def test_different_regions_and_iteration_limits(self):
        baseline = generate(DEFAULT)
        for args in [DEFAULT[:-1] + ['64'],
                     ['--re', '-1.184874414', '-0.9228628317', *DEFAULT[3:]],
                     ['--re', '-0.2', '0.2', '--im', '-0.2', '0.2', '--iterations', '352'],
                     ['--re', '0.5', '1', '--im', '0.5', '1', '--iterations', '352']]:
            candidate = generate(args)
            parse(candidate)
            self.assertNotEqual(baseline, candidate)

    def test_export_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, 'MyMidiFile.mid').mkdir()
            result = subprocess.run([str(EXE), *DEFAULT], cwd=directory, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Cannot open MIDI output', result.stderr)


if __name__ == '__main__':
    unittest.main()
