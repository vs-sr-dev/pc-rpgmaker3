#!/usr/bin/env python3
"""
RPG Maker 3 (PS2, SLUS-21178) -- CDIMAGE.TBL index parser.

Layout (little-endian):
    u32 count
    entry[count] {              # 136 bytes each
        char name[128];         # NUL-padded absolute path, '/'-separated
        u32  offset;            # byte offset inside RPGSP.DAT (2048-aligned)
        u32  size;              # exact byte size
    }
"""
import argparse, os, struct, sys

ENTRY = 136
SECTOR = 2048


def load(tbl_path):
    with open(tbl_path, 'rb') as f:
        data = f.read()
    (count,) = struct.unpack_from('<I', data, 0)
    expect = 4 + count * ENTRY
    if expect != len(data):
        print(f'warning: count={count} implies {expect} bytes, file is {len(data)}',
              file=sys.stderr)
    out = []
    for i in range(count):
        base = 4 + i * ENTRY
        raw = data[base:base + 128]
        name = raw.split(b'\0', 1)[0].decode('ascii', 'replace')
        off, size = struct.unpack_from('<II', data, base + 128)
        out.append((i, name, off, size))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tbl')
    ap.add_argument('--dat', help='RPGSP.DAT, for extraction / validation')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--stats', action='store_true')
    ap.add_argument('--extract', metavar='DESTDIR')
    ap.add_argument('--filter', default='', help='substring match on path')
    args = ap.parse_args()

    ents = load(args.tbl)
    sel = [e for e in ents if args.filter in e[1]]

    if args.list:
        for i, name, off, size in sel:
            print(f'{i:5d}  {off:#012x}  {size:10d}  {name}')

    if args.stats:
        from collections import Counter
        ext = Counter(os.path.splitext(n)[1].lower() or '<none>' for _, n, _, _ in ents)
        top = Counter(n.split('/')[1] if n.count('/') > 1 else '<root>'
                      for _, n, _, _ in ents)
        bytes_by_ext = Counter()
        bytes_by_dir = Counter()
        for _, n, _, s in ents:
            bytes_by_ext[os.path.splitext(n)[1].lower() or '<none>'] += s
            bytes_by_dir[n.split('/')[1] if n.count('/') > 1 else '<root>'] += s
        print(f'entries: {len(ents)}')
        print(f'total payload: {sum(e[3] for e in ents):,} bytes')
        print(f'max end offset: {max(e[2]+e[3] for e in ents):,}')
        print('\n-- by extension --')
        for k, v in ext.most_common():
            print(f'  {k:10s} {v:5d} files  {bytes_by_ext[k]:14,d} B')
        print('\n-- by top-level dir --')
        for k, v in top.most_common():
            print(f'  {k:16s} {v:5d} files  {bytes_by_dir[k]:14,d} B')

    if args.extract:
        if not args.dat:
            sys.exit('--extract requires --dat')
        with open(args.dat, 'rb') as f:
            for i, name, off, size in sel:
                dst = os.path.join(args.extract, name.lstrip('/'))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                f.seek(off)
                with open(dst, 'wb') as g:
                    g.write(f.read(size))
                print(f'{name} -> {size} B')


if __name__ == '__main__':
    main()
