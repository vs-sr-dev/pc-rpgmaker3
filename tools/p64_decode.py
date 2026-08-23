#!/usr/bin/env python3
"""
RPG Maker 3 (PS2) .p64 / .mpic texture decoder -> PNG.

.p64 container:
    u16 count; u16 hdr_size(=64); u32 payload_size; u32 reserved;
    u32 tex_offset[count]   (relative to end of the 64-byte header)
    ... then `count` texture blocks.

Texture block (also the whole content of a .mpic file):
    u16 fmt        1 = 8bpp indexed, 0 = 4bpp indexed
    u16 unk        always 2
    u16 width
    u16 height
    u16 ncolors    256 or 16
    u16 pal_bytes  1024 or 64
    u32 data_bytes
    u32 -1 ; u32 0 ; u32 checksum ; char magic[4] = "V20"
    char source_path[96-...]   (remainder of a 128-byte header, often the
                                artist's Windows path -- see docs)
    u8  pixels[data_bytes]     row-major, NOT swizzled
    u8  palette[pal_bytes]     RGBA, alpha 0..128, CSM1 order for 256-colour
"""
import argparse, os, struct, sys, zlib

HDRSZ = 128


def write_png(path, w, h, rgba):
    raw = b''.join(b'\x00' + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c))
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw, 9))
           + chunk(b'IEND', b''))
    open(path, 'wb').write(png)


def unswizzle_clut(pal):
    """PS2 CSM1 CLUT order: within each group of 32 entries, the middle two
    runs of 8 are swapped."""
    out = bytearray(len(pal))
    n = len(pal) // 4
    for i in range(n):
        blk, rem = divmod(i, 32)
        if 8 <= rem < 16:
            j = blk * 32 + rem + 8
        elif 16 <= rem < 24:
            j = blk * 32 + rem - 8
        else:
            j = i
        out[j * 4:j * 4 + 4] = pal[i * 4:i * 4 + 4]
    return bytes(out)


def decode_block(buf, base, raw_clut=False):
    fmt, unk, w, h, ncol, palb = struct.unpack_from('<6H', buf, base)
    datab, = struct.unpack_from('<I', buf, base + 12)
    magic = buf[base + 28:base + 31]
    src = buf[base + 32:base + HDRSZ].split(b'\0', 1)[0]
    pix = buf[base + HDRSZ:base + HDRSZ + datab]
    pal = buf[base + HDRSZ + datab:base + HDRSZ + datab + palb]
    total = HDRSZ + palb + datab

    if ncol == 256 and not raw_clut:
        pal = unswizzle_clut(pal)
    # PS2 stores alpha as 0..128 -> scale to 0..255
    pal = bytes(pal[i] if i % 4 != 3 else min(255, pal[i] * 2)
                for i in range(len(pal)))

    rgba = bytearray(w * h * 4)
    if fmt == 1:                       # 8bpp
        for i, idx in enumerate(pix[:w * h]):
            rgba[i * 4:i * 4 + 4] = pal[idx * 4:idx * 4 + 4]
    else:                              # 4bpp, low nibble first
        for i in range(w * h):
            b = pix[i >> 1]
            idx = (b & 0x0F) if (i & 1) == 0 else (b >> 4)
            rgba[i * 4:i * 4 + 4] = pal[idx * 4:idx * 4 + 4]
    meta = dict(fmt=fmt, unk=unk, w=w, h=h, ncol=ncol, palb=palb,
                datab=datab, magic=magic, src=src.decode('cp932', 'replace'),
                total=total)
    return meta, bytes(rgba)


def blocks(path):
    buf = open(path, 'rb').read()
    if path.lower().endswith('.mpic'):
        yield 0, buf, 0
        return
    count, hdrsz, payload = struct.unpack_from('<HHI', buf, 0)
    offs = struct.unpack_from(f'<{count}I', buf, 12)
    for i, o in enumerate(offs):
        yield i, buf, hdrsz + o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('-o', '--outdir', default='.')
    ap.add_argument('--raw-clut', action='store_true')
    ap.add_argument('--info', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    for p in a.files:
        for i, buf, base in blocks(p):
            meta, rgba = decode_block(buf, base, a.raw_clut)
            stem = os.path.splitext(os.path.basename(p))[0]
            out = os.path.join(a.outdir, f'{stem}_{i}.png')
            print(f'{p}[{i}] {meta["w"]}x{meta["h"]} fmt={meta["fmt"]} '
                  f'{meta["ncol"]}c magic={meta["magic"]} src={meta["src"]!r}')
            if not a.info:
                write_png(out, meta['w'], meta['h'], rgba)


if __name__ == '__main__':
    main()
