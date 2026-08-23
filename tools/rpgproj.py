"""Dump an RPG Maker 3 project file (sample/game/*, or BASLUS-21178a from a
memory card save).

    python tools/rpgproj.py project --header
    python tools/rpgproj.py project --walk
    python tools/rpgproj.py project --strings
    python tools/rpgproj.py a b --diff        # two projects, byte level

Only the first `bytes_used` bytes of the arena are meaningful; everything
after it is uninitialised PS2 memory that got written out with the rest of
the buffer.
"""
import argparse
import re
import struct
import sys

HDR = 16          # file header, before the arena
TYPES = 20        # number of record types, also at header +0x14
TBL_SIZE = 0x24   # sizeof table, file offset
TBL_B = 0x64      # second per-type table, purpose unknown
TBL_COUNT = 0x7EA  # per-type ID counter (next free ID, so objects = value - 1)
TITLE = 0x1AC     # project title, Shift-JIS
FIRST_RECORD = 0xB30

NAME_OFF = 0x4C   # offset of the name inside a record


class Project:
    def __init__(self, data):
        (self.used, self.checksum, self.capacity,
         self.field_c) = struct.unpack_from("<4I", data, 0)
        self.ntypes, = struct.unpack_from("<I", data, 0x14)
        self.objects, = struct.unpack_from("<I", data, 0x18)
        self.size = struct.unpack_from("<%dH" % TYPES, data, TBL_SIZE)
        self.tbl_b = struct.unpack_from("<%dH" % TYPES, data, TBL_B)
        self.count = struct.unpack_from("<%dH" % TYPES, data, TBL_COUNT)
        self.data = data

    def title(self):
        return decode(self.data[TITLE:TITLE + 64].split(b"\0")[0])

    def walk(self):
        """Yield (offset, id, type) for as far as the record chain parses."""
        p = FIRST_RECORD
        # bytes_used is measured from the start of the file and marks the end
        # of the last record; the header itself ends 20 bytes before 0xB30.
        while p < self.used and p + 8 <= len(self.data):
            ident, kind = struct.unpack_from("<II", self.data, p)
            if kind >= TYPES or self.size[kind] == 0:
                yield p, ident, None
                return
            yield p, ident, kind
            p += self.size[kind]

    def name_at(self, off):
        return decode(self.data[off + NAME_OFF:off + NAME_OFF + 32].split(b"\0")[0])


def decode(b):
    for enc in ("ascii", "cp932"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return repr(b)


def strings(data, limit, minlen=4):
    """ASCII and Shift-JIS runs inside the used part of the arena."""
    pat = rb"(?:[\x20-\x7e]|[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]){%d,}" % minlen
    for m in re.finditer(pat, data[:limit]):
        s = decode(m.group())
        if not s.startswith("b'"):
            yield m.start(), s


def show_header(p):
    print("bytes_used   0x%08X  (%d)" % (p.used, p.used))
    print("checksum     0x%08X  (algorithm unknown)" % p.checksum)
    print("capacity     0x%08X  (%d = file size - %d)" % (p.capacity, p.capacity, HDR))
    print("+0x0C        0x%08X" % p.field_c)
    print("type count   %d" % p.ntypes)
    print("objects      %d" % p.objects)
    print("title        %s" % p.title())
    print()
    print("type  size  tbl_b  next_id  objects")
    for t in range(TYPES):
        print("  %2d  %4d  %5d  %7d  %7d" % (
            t, p.size[t], p.tbl_b[t], p.count[t], p.count[t] - 1))


def show_walk(p):
    total = 0
    prev = None
    for off, ident, kind in p.walk():
        if kind is None:
            print("  0x%06X  chain stops here (bad type); %d records read" % (off, total))
            return
        print("  0x%06X  id %-5d type %2d  size %5d  %s" % (
            off, ident, kind, p.size[kind], p.name_at(off)))
        total += 1
        prev = off
    end = off + p.size[kind] if prev is not None else FIRST_RECORD
    print("  %d records, chain ends at 0x%06X, bytes_used = 0x%06X%s" % (
        total, end, p.used, "  MATCH" if end == p.used else "  MISMATCH"))


def show_diff(a, b):
    runs = []
    cur = None
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            if cur and i - cur[1] <= 16:
                cur[1] = i
            else:
                if cur:
                    runs.append(cur)
                cur = [i, i]
    if cur:
        runs.append(cur)
    print("%d differing runs (gaps of 16 bytes or less merged)" % len(runs))
    for s, e in runs:
        print("  0x%06X..0x%06X  %d bytes" % (s, e + 1, e - s + 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="+")
    ap.add_argument("--header", action="store_true")
    ap.add_argument("--walk", action="store_true")
    ap.add_argument("--strings", action="store_true")
    ap.add_argument("--diff", action="store_true")
    args = ap.parse_args()

    blobs = [open(f, "rb").read() for f in args.project]
    if args.diff:
        if len(blobs) != 2:
            sys.exit("--diff needs exactly two projects")
        return show_diff(*blobs)

    for f, blob in zip(args.project, blobs):
        p = Project(blob)
        if len(blobs) > 1:
            print("== %s" % f)
        if args.header or not (args.walk or args.strings):
            show_header(p)
        if args.walk:
            show_walk(p)
        if args.strings:
            for off, s in strings(blob, p.used):
                print("  0x%06X  %s" % (off, s))


if __name__ == "__main__":
    main()
