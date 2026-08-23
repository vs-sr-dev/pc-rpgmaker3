#!/usr/bin/env python3
"""
RPG Maker 3 (PS2) .iab video track -> MPEG-2 elementary stream.

The .iab video payload is an MPEG-2 *intra* bitstream with every start code
removed, so no off-the-shelf demuxer will touch it. Per frame it holds:

    17 bits of frame header   (bits 10..14 = quantiser_scale_code)
    then 40*28 macroblocks back to back, with NO slice layer at all --
    the first macroblock of each row carries macroblock_type '01'
    (Intra, Quant) instead of '1', which is what re-sends the quantiser.

Picture parameters recovered from the bitstream: I-picture, 4:2:0,
intra_vlc_format = 1 (coefficient table B-15, so EOB is '0110').

This tool re-synthesises the sequence/picture headers and wraps the whole
picture in a single slice, which ffmpeg decodes happily.

The decoded YUV is FULL range (0..255), matching the colour-space conversion
the PS2 IPU performs, so decode it as such or the picture washes out:

    ffmpeg -i out.m2v -vf scale=in_range=full:out_range=limited            -pix_fmt yuv420p out.mp4

The 17-bit frame header is not fully understood yet; bits 10..14 are the
quantiser_scale_code, but the number of bits before the first macroblock
varies per file (17 for logo.iab, 13 for rpg_640_448.iab). Use --offset.
"""
import argparse, os, struct, sys

AUDIO_MAGIC = 0x12481248
VIDEO_MAGIC = 0x84218421


class BW:
    def __init__(self): self.bits = []
    def u(self, val, n):
        for i in range(n - 1, -1, -1): self.bits.append((val >> i) & 1)
    def raw(self, s): self.bits.extend(1 if c == '1' else 0 for c in s)
    def align(self):
        while len(self.bits) % 8: self.bits.append(0)
    def start_code(self, code):
        self.align(); self.u(0x000001, 24); self.u(code, 8)
    def bytes(self):
        self.align()
        return bytes(int(''.join(map(str, self.bits[i:i + 8])), 2)
                     for i in range(0, len(self.bits), 8))


def chunks(data):
    o = 0x40
    while o + 16 <= len(data):
        magic, ts, size, stride = struct.unpack_from('<IfII', data, o)
        if stride == 0 or o + stride > len(data) + 16: break
        yield magic, ts, data[o + 16:o + 16 + size]
        o += stride


def build_m2v(frames, w=640, h=448, dcprec=0, qscale_type=0, alt_scan=0,
              offset=17):
    b = BW()
    b.start_code(0xB3)                       # sequence_header
    b.u(w, 12); b.u(h, 12)
    b.u(1, 4)                                # aspect_ratio_information
    b.u(4, 4)                                # frame_rate_code = 30000/1001
    b.u(0x3FFFF, 18); b.u(1, 1)              # bit_rate_value, marker
    b.u(112, 10); b.u(0, 1)                  # vbv, constrained
    b.u(0, 1); b.u(0, 1)                     # no custom quant matrices
    b.start_code(0xB5)                       # sequence_extension
    b.u(1, 4); b.u(0x48, 8)
    b.u(1, 1); b.u(1, 2)                     # progressive, 4:2:0
    b.u(0, 2); b.u(0, 2); b.u(0, 12); b.u(1, 1); b.u(0, 8)
    b.u(0, 1); b.u(0, 2); b.u(0, 5)

    for n, payload in enumerate(frames):
        bits = ''.join(f'{x:08b}' for x in payload)
        q = int(bits[10:15], 2)              # quantiser_scale_code
        b.start_code(0x00)                   # picture_header
        b.u(n % 1024, 10); b.u(1, 3); b.u(0xFFFF, 16); b.u(0, 1)
        b.start_code(0xB5)                   # picture_coding_extension
        b.u(8, 4)
        b.u(15, 4); b.u(15, 4); b.u(15, 4); b.u(15, 4)
        b.u(dcprec, 2); b.u(3, 2)            # intra_dc_precision, frame pict
        b.u(0, 1); b.u(1, 1); b.u(0, 1)      # tff, frame_pred_frame_dct, cmv
        b.u(qscale_type, 1); b.u(1, 1)       # q_scale_type, intra_vlc_format
        b.u(alt_scan, 1); b.u(0, 1)
        b.u(1, 1); b.u(1, 1); b.u(0, 1)      # chroma_420_type, progressive
        b.start_code(0x01)                   # one slice for the whole picture
        b.u(q, 5); b.u(0, 1)
        b.raw(bits[offset:])                 # macroblock data
    b.start_code(0xB7)
    return b.bytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('iab')
    ap.add_argument('-o', '--out', required=True, help='output .m2v')
    ap.add_argument('--first', type=int, default=0)
    ap.add_argument('--count', type=int, default=0, help='0 = all frames')
    ap.add_argument('--dcprec', type=int, default=0)
    ap.add_argument('--qscale-type', type=int, default=0)
    ap.add_argument('--alt-scan', type=int, default=0)
    ap.add_argument('--offset', type=int, default=17,
                    help='bit offset of the first macroblock (see docs: 17 for '
                         'logo.iab, 13 for rpg_640_448.iab)')
    a = ap.parse_args()

    data = open(a.iab, 'rb').read()
    rate, ch, il, ablk, asec, nsub, tot = struct.unpack_from('<IIIIfII', data, 4)
    vid = [p for m, ts, p in chunks(data) if m == VIDEO_MAGIC]
    if not vid: sys.exit('no video track in this .iab')
    sel = vid[a.first:a.first + a.count] if a.count else vid[a.first:]
    print(f'{len(vid)} frames, using {len(sel)} from #{a.first}')
    open(a.out, 'wb').write(build_m2v(sel, dcprec=a.dcprec,
                                      qscale_type=a.qscale_type,
                                      alt_scan=a.alt_scan, offset=a.offset))
    print(f'wrote {a.out} ({os.path.getsize(a.out)} bytes)')


if __name__ == '__main__':
    main()
