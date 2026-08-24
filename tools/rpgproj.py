#!/usr/bin/env python3
"""Read an RPG Maker 3 project (sample/game/*, or BASLUS-21178a from a save).

    python tools/rpgproj.py project --header
    python tools/rpgproj.py project --walk
    python tools/rpgproj.py project --walk --type 4      # one record type only
    python tools/rpgproj.py project --maps --png out/
    python tools/rpgproj.py project --skills --elf SLUS_211.78
    python tools/rpgproj.py project --strings
    python tools/rpgproj.py a b --diff
    python tools/rpgproj.py project --fix-checksum out   # rewrite with a valid CRC

File layout: a 16-byte wrapper (bytes_used, CRC-32, capacity, saved base) then
the object arena.  Only the first `bytes_used` bytes of the arena are
meaningful; what follows is uninitialised PS2 memory written out with the
buffer, so it differs between two saves made seconds apart.
"""
import argparse
import re
import struct
import sys
import zlib

WRAPPER = 16      # bytes before the arena; also where the CRC starts
TYPES = 20
TBL_SIZE = 0x24   # sizeof of each type's fixed part
TBL_VAR = 0x64    # size of each type's variable part, plus 4
TBL_NEXTID = 0x7EA
TITLE = 0x1AC
FIRST = 0xB30     # first record payload

NAME_OFF = 0x4C   # name inside a record, Shift-JIS, NUL padded

SKILL_BASE = 0x154   # first special-skill entry inside a Class record
SKILL_STRIDE = 240
SKILLS = 16

# The two pick-lists a skill chooses from live in the executable, not in the
# project.  ELF_VFX is 64 records of {char name[22]; i16 id, id2, se}; rows
# whose id is -3 are disabled and the editor does not show them, so a stored
# value counts only the rest, with "None" at 0.  ELF_ANIM is eight 16-byte
# names.  Offsets are into SLUS_211.78 as a file.
ELF_VFX = 0x3A80D8
ELF_VFX_N = 64
ELF_VA = 0xFF000     # vaddr = file offset + this

# Everything else the editor offers is a table of pointers with its own label
# in the slot before the first entry.  Reading the strings inline instead of
# through the pointers very nearly works and is wrong in exactly one place:
# animation 7 points away to "Throw", leaving a dead "Attack 5" behind.
ELF_ANIM = 0x370414                     # 8 entries, label "Animation" at -1
ELF_CATEGORY = 0x32ADAC                 # 5 entries, label "Effects" at -1
# The editor gives a skill two effect selectors and picks both tables from the
# category at +0x0C0.  ELF_EFFECT is the first, what the skill does; the
# second, the "additional effect", is one of the "Add Effects: ..." lists and
# we do not yet know which field carries it -- see 08-project-format.md.
ELF_EFFECT = {0: 0x32F7E4, 1: 0x331B0C, 2: 0x333E34, 3: 0x33615C, 4: 0x338484}
ELF_ADDEFFECT = 0x357F78                # "Add Effects: Attacks", None at -1
EXTRA_OFF = -4    # bytes of variable data beyond the type's own variable part

# Names as the executable registers them, at 0x00100F48.  Two pairs share a
# string: 6/7 are monsters and their encounter groups, 14/15 are both "Event".
TYPE_NAMES = [
    "Field Data", "Dungeon Data", "Town Data", "Story Data", "Class Data",
    "Human Data", "Monster Data", "Monster Group", "Item Data", "Equip Data",
    "Important Data", "Room Data", "Castle Data", "System Data", "Event",
    "Event (2)", "Save Event", "Warp Event", "Chest Event", "Entrance",
]


class Project:
    def __init__(self, data):
        (self.used, self.checksum, self.capacity,
         self.base) = struct.unpack_from("<4I", data, 0)
        self.ntypes, = struct.unpack_from("<I", data, 0x14)
        self.objects, = struct.unpack_from("<I", data, 0x18)
        self.size = struct.unpack_from("<%dH" % TYPES, data, TBL_SIZE)
        self.var = struct.unpack_from("<%dH" % TYPES, data, TBL_VAR)
        self.next_id = struct.unpack_from("<%dH" % TYPES, data, TBL_NEXTID)
        self.data = data

    def crc(self):
        return zlib.crc32(self.data[WRAPPER:WRAPPER + self.used])

    def title(self):
        return decode(self.data[TITLE:TITLE + 64].split(b"\0")[0])

    def stride(self, kind, extra):
        """Bytes from one record's payload to the next.

        A record occupies a 20-byte allocator header, its fixed part, and a
        variable part of `var[kind] - 4 + extra` bytes.  Types that never grow
        have var == 4, which is why fixed records simply step by sizeof + 20.
        """
        return self.size[kind] + self.var[kind] + WRAPPER + extra

    def walk(self):
        """Yield (payload_offset, id, type, extra) for every record."""
        p = FIRST
        while p < self.used:
            if p + 8 > self.used:
                raise ValueError("record header runs past bytes_used at 0x%X" % p)
            ident, kind = struct.unpack_from("<II", self.data, p)
            if kind >= TYPES or self.size[kind] == 0:
                raise ValueError("bad type %d at 0x%X" % (kind, p))
            extra, = struct.unpack_from("<I", self.data, p + EXTRA_OFF)
            yield p, ident, kind, extra
            p += self.stride(kind, extra)
        # The walk stops one allocator header past the last record; that
        # header is the free pointer, which is what bytes_used records.
        if p != self.used + 20:
            raise ValueError("walk ended at 0x%X, expected 0x%X" % (p, self.used + 20))

    def name_at(self, off):
        return decode(self.data[off + NAME_OFF:off + NAME_OFF + 32].split(b"\0")[0])

    def maps(self):
        """Yield (name, width, height, tiles, heights) for every map record.

        A map's grid lives in the record's variable part, after the fixed
        record and the `var - 4` bytes that precede it.  The blob opens with a
        24-byte header stating the two dimensions, then one byte per cell of
        terrain, then the same grid again holding Z.  Both are addressed
        row-major, `index = y * width + x`, confirmed by painting a single
        tile in the editor at X=100 Y=76 and finding it at index 10,740.

        The Z grid is sixteen bytes short of the full width*height; the last
        sixteen cells of the bottom row are simply not stored.
        """
        for off, ident, kind, extra in self.walk():
            if not extra or kind not in (0, 1, 2):
                continue
            blob = off + self.size[kind] + self.var[kind] - 4
            w, h = struct.unpack_from("<2I", self.data, blob + 0x10)
            if not (0 < w * h <= extra):
                continue
            tiles = self.data[blob + 0x18:blob + 0x18 + w * h]
            z = self.data[blob + 0x18 + w * h:blob + extra]
            yield self.name_at(off), w, h, tiles, z


def decode(b):
    for enc in ("ascii", "cp932"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return repr(b)


def strings(data, limit, minlen=4):
    pat = rb"(?:[\x20-\x7e]|[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]){%d,}" % minlen
    for m in re.finditer(pat, data[:limit]):
        s = decode(m.group())
        if not s.startswith("b'"):
            yield m.start(), s


def show_header(p):
    ok = "ok" if p.crc() == p.checksum else "BAD (computed 0x%08X)" % p.crc()
    print("bytes_used   0x%08X  (%d)" % (p.used, p.used))
    print("checksum     0x%08X  CRC-32 of arena[0:bytes_used]  %s" % (p.checksum, ok))
    print("capacity     0x%08X  (%d = file size - %d)" % (p.capacity, p.capacity, WRAPPER))
    print("saved base   0x%08X  (arena address when written; 0 on memory-card saves)"
          % p.base)
    print("type count   %d" % p.ntypes)
    print("objects      %d  (records + 1)" % p.objects)
    print("title        %s" % p.title())
    print()
    print("type  name             sizeof  var  next_id")
    for t in range(TYPES):
        print("  %2d  %-16s %6d %4d  %7d"
              % (t, TYPE_NAMES[t], p.size[t], p.var[t], p.next_id[t]))


def show_walk(p, only=None):
    n = 0
    for off, ident, kind, extra in p.walk():
        n += 1
        if only is not None and kind != only:
            continue
        print("  0x%06X  id %-5d %-16s size %5d%s  %s"
              % (off, ident, TYPE_NAMES[kind], p.size[kind],
                 "  +%-7d" % extra if extra else " " * 10, p.name_at(off)))
    print("  %d records, objects field says %d" % (n, p.objects - 1))


def elf_lists(path):
    """Return the visual-effect, animation and add-effect lists as the editor
    shows them, read out of the executable rather than the project."""
    d = open(path, "rb").read()

    def at(va):
        off = va - ELF_VA
        return decode(d[off:off + 40].split(b"\0")[0])

    vfx = []
    for i in range(ELF_VFX_N):
        rec = d[ELF_VFX + i * 28:ELF_VFX + i * 28 + 28]
        ident, = struct.unpack_from("<h", rec, 22)
        if ident != -3:                     # -3 is a row the editor hides
            vfx.append(decode(rec[:22].split(b"\0")[0]))
    def table(base):
        out = []
        for i in range(64):
            ptr, = struct.unpack_from("<I", d, base + i * 4)
            if not ptr:
                break
            out.append(at(ptr))
        return out

    anim = table(ELF_ANIM)
    cats = table(ELF_CATEGORY)
    eff = dict(enumerate(table(ELF_ADDEFFECT)))
    eff[-1] = at(struct.unpack_from("<I", d, ELF_ADDEFFECT - 4)[0])
    return vfx, anim, cats, eff


def show_skills(p, elf=None):
    """List every class's special skills, with the fields sessions 4-5 pinned.

    The effect column is `+0x0E0` resolved through "Add Effects: Attacks",
    which the editor confirmed only for category 0; for the others it is left
    as the raw category, because writing that field did not move what the
    editor displays and we do not yet know what does.
    """
    vfx, anim, cats, eff = elf_lists(elf) if elf else (None,) * 4
    # A recovery skill picks from the Heal block alone, so its stored index is
    # relative to that sub-list rather than to the whole pick-list.
    heal = ["None"] + vfx[26:36] if vfx else None
    for off, ident, kind, extra in p.walk():
        if kind != 4:
            continue
        rows = []
        for i in range(SKILLS):
            e = off + SKILL_BASE + SKILL_STRIDE * i
            if struct.unpack_from("<i", p.data, e)[0] != 1:
                continue
            name = decode(p.data[e + 4:e + 4 + 22].split(b"\0")[0])
            if not name:
                continue
            ty, cat, _, ve, _, an, _, tgt, pts, fx, cost = struct.unpack_from(
                "<11i", p.data, e + 0xBC)
            if vfx:
                lst = heal if cat == 3 else vfx
                ve = lst[ve] if ve < len(lst) else "?%d" % ve
                an = anim[an] if an < len(anim) else "?%d" % an
                fx = eff.get(fx, "?%d" % fx) if cat == 0 else "(cat %d)" % cat
                cat = cats[cat] if cat < len(cats) else "?%d" % cat
            rows.append((name, "magic" if ty else "skill", cat,
                         "all" if tgt else "one", pts, fx, cost, ve, an))
        if not rows:
            continue
        print("  %s" % p.name_at(off))
        for r in rows:
            print("    %-18s %-5s %-14s %-3s %4d pts  cost %-3d  %-21s"
                  "  %-17s %s"
                  % (r[0], r[1], r[2], r[3], r[4], r[6], r[5], r[7], r[8]))


def write_png(path, w, h, rgb):
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    open(path, "wb").write(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b""))


# Enough distinct hues to tell terrain types apart; not the game's palette.
TERRAIN = [(60, 90, 60), (110, 150, 70), (150, 140, 90), (90, 130, 60),
           (170, 160, 120), (120, 110, 100), (200, 190, 150), (40, 70, 140),
           (150, 150, 150), (200, 200, 210)]


def show_maps(p, outdir=None):
    for name, w, h, tiles, z in p.maps():
        used = sorted(set(tiles))
        print("  %-20s %dx%d  %d terrain values %s"
              % (name or "(unnamed)", w, h, len(used), used[:12]))
        if outdir is None:
            continue
        safe = re.sub(r"[^\w.-]", "_", name) or "map"
        rgb = bytearray()
        for v in tiles:
            rgb += bytes(TERRAIN[v % len(TERRAIN)])
        write_png("%s/%s.terrain.png" % (outdir, safe), w, h, bytes(rgb))
        # The Z grid stops sixteen cells short; pad so the image stays square.
        zz = z + b"\0" * (w * h - len(z))
        write_png("%s/%s.height.png" % (outdir, safe), w, h,
                  bytes(b for v in zz for b in (v, v, v)))
        print("     -> %s/%s.terrain.png and .height.png" % (outdir, safe))


def show_diff(a, b):
    runs = []
    cur = None
    for i in range(min(len(a), len(b))):
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
    ap.add_argument("--type", type=int, help="with --walk, show only this type")
    ap.add_argument("--strings", action="store_true")
    ap.add_argument("--maps", action="store_true", help="list the map records")
    ap.add_argument("--png", metavar="DIR", help="with --maps, write PNGs there")
    ap.add_argument("--skills", action="store_true",
                    help="list every class's special skills")
    ap.add_argument("--elf", metavar="SLUS_211.78",
                    help="with --skills, name the effects and animations")
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--fix-checksum", metavar="OUT",
                    help="write a copy with the CRC-32 recomputed")
    args = ap.parse_args()

    blobs = [open(f, "rb").read() for f in args.project]
    if args.diff:
        if len(blobs) != 2:
            sys.exit("--diff needs exactly two projects")
        return show_diff(*blobs)

    if args.fix_checksum:
        if len(blobs) != 1:
            sys.exit("--fix-checksum takes one project")
        out = bytearray(blobs[0])
        struct.pack_into("<I", out, 4, Project(blobs[0]).crc())
        open(args.fix_checksum, "wb").write(bytes(out))
        return print("wrote %s with checksum 0x%08X"
                     % (args.fix_checksum, struct.unpack_from("<I", out, 4)[0]))

    for f, blob in zip(args.project, blobs):
        p = Project(blob)
        if len(blobs) > 1:
            print("== %s" % f)
        if args.header or not (args.walk or args.strings or args.maps
                               or args.png or args.skills):
            show_header(p)
        if args.walk:
            show_walk(p, args.type)
        if args.skills:
            show_skills(p, args.elf)
        if args.maps or args.png:
            show_maps(p, args.png)
        if args.strings:
            for off, s in strings(blob, p.used):
                print("  0x%06X  %s" % (off, s))


if __name__ == "__main__":
    main()
