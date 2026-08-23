# The project format (`sample/game/*`, memory-card saves)

This is the engine's central data structure: everything the user creates in
the editor — maps, events, database, cutscenes — lives in a single
1,994,768-byte file.

## Where to find one

The disc carries three of them in `sample/game/`. The far more useful source
is a memory card, because you control what is in it:

    python tools/ps2mc.py card.ps2 --list
    python tools/ps2mc.py card.ps2 --extract out/

A saved project occupies one directory per slot:

    BASLUS-21178a/BASLUS-21178a    1994768   the project itself
    BASLUS-21178a/info.dat            1024   title, timestamps, checksum
    BASLUS-21178a/player1..3        204800   in-game save slots (empty here)
    BASLUS-21178a/icon.sys             964   "RPG MAKER 3 DATA 1"
    BASLUS-21178a/rpgsp.ico          55000   the 3D save icon
    BASLUS-21178system/…             33792   editor-wide settings

`BASLUS-21178a/BASLUS-21178a` is byte-for-byte the same format as
`sample/game/sample1`, down to the header tables. Anything learned from one
applies to the other.

## File layout

    +0x00  u32   bytes_used        end of the last record, from the file start
    +0x04  u32   checksum          algorithm not identified
    +0x08  u32   capacity          always file size - 16
    +0x0C  u32   0 on memory-card saves, 0x00A0_2A00-ish in the disc samples
    +0x10  …     arena

Because `capacity` is exactly the file size minus 16, the first 16 bytes are a
wrapper and everything after is one flat arena. The same wrapper appears on
`info.dat` (capacity 0x3F0 = 1024 - 16), on `player1..3`
(0x31FF0 = 204800 - 16) and on the system save (0x83F0 = 33792 - 16), so it is
the engine's generic "saved buffer" header rather than something specific to
projects.

**Only the first `bytes_used` bytes mean anything.** Past that point the file
is uninitialised PS2 memory that was written out with the rest of the buffer:
a freshly created project reports 2,844 bytes used yet has non-zero data
almost all the way to the end of the file. This is why an earlier diff of the
three samples appeared to show 56 % of the bytes changing — most of that was
leftover heap, not project data. Two saves made minutes apart on the same
console carry *identical* garbage, which is what makes differential analysis
work at all.

## Global header (0x00 .. 0xB30)

    +0x10  u32   0x00010000     constant
    +0x14  u32   20             number of record types
    +0x18  u32   object counter (1 in a new project, 2 after adding one object)
    +0x1C  u32   0
    +0x20  u32   same value as +0x18
    +0x24  20×u16  size of a record, per type   (table A, constant in every file)
    +0x64  20×u16  second per-type table        (table B, constant in every file)
    +0xA4  …       small fixed fields, identical in all five files seen
    +0x1AC string  project title, Shift-JIS
    +0x200 u32     a count (140 / 75 / 25 in the samples, -1 in a new project)
    +0x208 float   -3.14159265 in two samples — a saved camera angle
    +0x7EA 20×u16  next free ID, per type (table C)

Table C is the one that moves: a new project has `1` in all twenty slots, and
adding a single Sword & Shield class turns slot 4 into `2`. So the value is
the *next* ID to hand out, and the number of objects of a type is `C[t] - 1`.

Tables A and B are byte-identical across all five projects examined, so they
are the engine's fixed schema rather than per-project data:

    type   0     1     2     3     4     5     6     7     8     9
    A    436  1752  1132   260  4172   532  4188   492   288   336
    B     88  1092   100     4     4   636     4     4     4     4

    type  10    11    12    13    14    15    16    17    18    19
    A    264   356   256   444   260   260   252   300   280   256
    B      4    72     4  2236    16    16     4     4     4     4

Type 4 is the character class: creating one incremented `C[4]` and appended a
record of exactly `A[4]` = 4,172 bytes. Several of the A values match the
`sizeof` of the `CEdPro*` classes recovered from RTTI and the `.smp` record
sizes noted in `03-engine-architecture.md`. What B holds is still unknown; it
is not a count, since it never varies.

## Records

Records start at file offset **0xB30** and are laid end to end, each `A[type]`
bytes long, with no separator:

    +0x00  u32   id
    +0x04  u32   type
    +0x08  u32   0
    +0x0C  u32   id again
    +0x10  u32   -1        \
    +0x14  u32   type       |  a second, link-shaped group of four
    +0x18  u32   0          |
    +0x1C  u32   -1        /
    +0x4C  char  name, Shift-JIS, NUL-padded

The name at `+0x4C` is confirmed twice over: `New Class 01` in the memory-card
save, and in `sample3` two consecutive records whose names sit exactly
`A[type]` bytes apart. Searching the samples for name-like strings separated
by each candidate stride finds chains for twelve of the twenty types, which is
independent confirmation that table A really is `sizeof`.

The `-1` pair at `+0x10`/`+0x1C` looks like the prev/next of an empty list —
consistent with the record being the only one of its type.

`tools/rpgproj.py --walk` follows this chain. On memory-card saves it lands
exactly on `bytes_used`; on the disc samples it parses the first handful of
records and then desynchronises, so at least one record kind is
variable-length or interleaved with something else. Finding that rule is the
next job.

## Anatomy of a class record (type 4, 4,172 bytes)

Out of 4,172 bytes, only 174 are non-zero in a default class, which makes the
skeleton easy to read. Thirty-nine words hold `-1`:

* two in the record header (the link pair above);
* six consecutive at `+0x13C`..`+0x150` — an empty six-slot array;
* the remaining thirty-one form a lattice with a stride of **240 bytes**
  starting at `+0x234`: fifteen pairs at `+0x00`/`+0x10` of each 240-byte
  block, then one last word at `+0x1044` where the record runs out.

So a class carries an array of fifteen 240-byte entries, all empty in a
default class — very likely the techniques the class learns, which is exactly
the kind of table the editor exposes on its class screen.

## What is not understood yet

* **The checksum at `+0x04`.** It is not additive (the delta between two
  nearly identical saves does not match the delta of any word sum), and it is
  not CRC-32 in any of the usual polynomial/init/reflect combinations, over
  any plausible range. Needed before the original engine will accept a file
  we write.
* **The 20-byte step between `bytes_used` of an empty project (0xB1C) and the
  first record (0xB30).** Records themselves are contiguous, so this gap
  belongs to the global header.
* **Table B**, and the fixed fields between `+0xA4` and `+0x200`.
* **Why the sample walk desynchronises** — the variable-length record kind.
