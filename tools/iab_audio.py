#!/usr/bin/env python3
"""
RPG Maker 3 (PS2) .iab audio track -> WAV.

The audio track is PS2 SPU-ADPCM (the format normally seen in .VAG files),
carried in the .iab chunk chain: each audio chunk holds `interleave` bytes
for the left channel followed by `interleave` bytes for the right.

ADPCM block = 16 bytes:
    byte 0 : low nibble = shift, high nibble = filter (0..4)
    byte 1 : loop flags (ignored here)
    2..15  : 28 samples, 4 bits each, low nibble first
"""
import argparse, struct, sys

VIDEO_MAGIC = 0x84218421
AUDIO_MAGIC = 0x12481248
F0 = (0, 60, 115, 98, 122)
F1 = (0, 0, -52, -55, -60)


def decode_adpcm(data, state):
    """Decode SPU-ADPCM bytes; `state` is a mutable [prev1, prev2] list."""
    out = bytearray()
    p1, p2 = state
    for b in range(0, len(data) - 15, 16):
        hdr = data[b]
        shift, flt = hdr & 0x0F, min((hdr >> 4) & 0x0F, 4)
        if shift > 12:
            shift, flt = 9, 0          # invalid shift: SPU treats as silence-ish
        f0, f1 = F0[flt], F1[flt]
        for i in range(28):
            byte = data[b + 2 + (i >> 1)]
            nib = (byte & 0x0F) if (i & 1) == 0 else (byte >> 4)
            if nib > 7:
                nib -= 16
            s = (nib << 12) >> shift
            s += (p1 * f0 + p2 * f1) >> 6
            s = max(-32768, min(32767, s))
            out += struct.pack('<h', s)
            p2, p1 = p1, s
    state[0], state[1] = p1, p2
    return out


def chunks(data):
    o = 0x40
    while o + 16 <= len(data):
        magic, ts, size, stride = struct.unpack_from('<IfII', data, o)
        if stride == 0 or o + stride > len(data) + 16:
            break
        yield magic, ts, data[o + 16:o + 16 + size]
        o += stride


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('iab')
    ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args()

    data = open(a.iab, 'rb').read()
    _, rate, nch, inter, ablk, asec, nsub, total = struct.unpack_from('<IIIIIfII', data, 0)
    print(f'{rate} Hz, {nch} ch, interleave {inter}, {ablk} blocks, {asec:.2f} s')

    state = [[0, 0] for _ in range(nch)]
    pcm = [bytearray() for _ in range(nch)]
    for magic, ts, payload in chunks(data):
        if magic != AUDIO_MAGIC:
            continue
        for c in range(nch):
            pcm[c] += decode_adpcm(payload[c * inter:(c + 1) * inter], state[c])

    n = min(len(p) for p in pcm) // 2
    frames = bytearray()
    for i in range(n):
        for c in range(nch):
            frames += pcm[c][i * 2:i * 2 + 2]

    with open(a.out, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', 36 + len(frames)) + b'WAVEfmt ')
        f.write(struct.pack('<IHHIIHH', 16, 1, nch, rate, rate * nch * 2, nch * 2, 16))
        f.write(b'data' + struct.pack('<I', len(frames)) + frames)
    print(f'wrote {a.out}: {n} frames = {n / rate:.2f} s')


if __name__ == '__main__':
    main()
