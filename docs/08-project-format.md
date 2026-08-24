# The project format (`sample/game/*`, memory-card saves)

This is the engine's central data structure: everything the user creates in
the editor — maps, events, database, cutscenes — lives in a single
1,994,768-byte file.

**Status: solved.** The checksum is CRC-32, the record walk is exact, and
`tools/rpgproj.py` reads every record of all eight projects we have, ending on
the last byte of each and agreeing with the file's own object count.

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
`sample/game/sample1`. Anything learned from one applies to the other.

Note when capturing cards from PCSX2: the directory's modification timestamp
does **not** advance when the editor saves. Compare file contents, not dates.

## File layout

    +0x00  u32   bytes_used        length of the meaningful part of the arena
    +0x04  u32   checksum          CRC-32 of arena[0 : bytes_used]
    +0x08  u32   capacity          always file size - 16
    +0x0C  u32   arena address at save time (0 on memory-card saves)
    +0x10  …     arena

Because `capacity` is exactly the file size minus 16, the first 16 bytes are a
wrapper and everything after is one flat arena. The same wrapper appears on
`info.dat` (capacity 0x3F0 = 1024 - 16), on `player1..3`
(0x31FF0 = 204800 - 16) and on the system save (0x83F0 = 33792 - 16), so it is
the engine's generic "saved buffer" header rather than something specific to
projects.

`+0x0C` is *not* a relocation base: the file contains no pointers at all.
Interpreting it as the arena's address and searching for the resulting
pointer values finds none — only 84 words in the whole of `sample1` even fall
in the right range, and none of them point at a record. The field is written
by the disc build and left at zero by the console's own save path.

**Only the first `bytes_used` bytes mean anything.** Past that point the file
is uninitialised PS2 memory that was written out with the rest of the buffer:
a freshly created project reports 2,844 bytes used yet has non-zero data
almost all the way to the end of the file. This is why an earlier diff of the
three samples appeared to show 56 % of the bytes changing — most of that was
leftover heap. Two saves from the same session carry *identical* garbage,
which is exactly what makes the differential method work.

## The checksum

    checksum = crc32(data[0x10 : 0x10 + bytes_used])

Plain CRC-32 as zlib computes it: reflected, polynomial 0xEDB88320, initial
value 0xFFFFFFFF, final complement. It verifies on all eight projects we
have — the five memory-card captures and the three disc samples — and
`tools/rpgproj.py --fix-checksum` reproduces the game's own value byte for
byte.

It belongs to the wrapper, not to projects: the identical formula also
verifies on `info.dat` (1,008 bytes covered of 1,024) and on the editor's
system save `BASLUS-21178system` (33,776 of 33,792). Every checksum the save
path writes is now accounted for.

Session 3 had ruled CRC-32 out, and was wrong to: the search had covered the
right polynomial but never the right range. The range is not "to
`bytes_used`" measured from the file start, it is *the arena itself* —
`bytes_used` is the arena's length, so the CRC starts at 0x10 and runs
`bytes_used` bytes from there, ending 16 bytes further into the file than
every range tried before.

Two things made it findable. First, a capture that changes exactly one byte
(`onestat.ps2`, one class stat from 0 to 1). Second, the fact that a CRC is
linear over GF(2): for any CRC whatsoever,

    crc(A) xor crc(B) = crc_with_zero_init(A xor B)

so the *difference* of two checksums depends only on the differing bytes and
on how many bytes follow them — not on the initial value, and not on any of
the data before the change. Feeding a single 0x01 byte followed by zeros into
each candidate polynomial and checking after every added zero turns a
four-dimensional search into a one-dimensional one. It reported exactly one
hit, giving the polynomial and the end of the range together.

The routine is in the executable, and matches. `crc32_init_table` at
0x00357B98 builds a reflected 256-entry table from 0x04C11DB7 by bit-reversing
each entry, and `crc32_update(state, buf, end)` at 0x00357C70 is the ordinary
table-driven loop. The caller at 0x001C0F70 reads the buffer pointer, length
and capacity from a descriptor and writes all three of `bytes_used`,
`checksum` and `capacity` into the wrapper, which confirms the field meanings
from the other side.

## Global header (0x00 .. 0xB30)

    +0x10  u32   0x00010000     constant
    +0x14  u32   20             number of record types
    +0x18  u32   objects        record count + 1
    +0x1C  u32   0
    +0x20  u32   same value as +0x18
    +0x24  20×u16  sizeof of each type's fixed part      (table A)
    +0x64  20×u16  each type's variable part, plus 4     (table B)
    +0xA4  …       small fixed fields, identical in all files seen
    +0x1AC string  project title, Shift-JIS
    +0x200 u32     a count (140 / 75 / 25 in the samples, -1 in a new project)
    +0x208 float   -3.14159265 in two samples — a saved camera angle
    +0x7EA 20×u16  next free ID, per type               (table C)

`objects` is a reliable check on any walk: it is the number of records plus
one, and it matches exactly on all eight files (579 for `sample1`'s 578
records, 285 for `sample2`, 503 for `sample3`).

Tables A and B are byte-identical across every project examined, because they
are not project data at all — they are the schema, and they come straight out
of the executable.

## The schema, from the executable

At 0x00100F48 the engine registers its twenty record types with twenty
consecutive calls to the same function (0x002CD948), each passing a size, a
second size, a flag and a name. `register_type` writes them into a 64-byte
descriptor:

    +0x00  u32   type index
    +0x04  u16   sizeof, the fixed part          -> table A in the file
    +0x06  u16   variable part + 4               -> table B in the file
    +0x08  u32   0, the counter                  -> table C in the file
    +0x0C  u32   the flag
    +0x10  16    the name

So the three tables in the file header are three columns of one descriptor
array. Recovering the names settles what the twenty types are:

    type  name              A: sizeof   B: var   flag
      0   Field Data              436       88    0
      1   Dungeon Data           1752     1092    1
      2   Town Data              1132      100    1
      3   Story Data              260        4    0
      4   Class Data             4172        4    0
      5   Human Data              532      636    1
      6   Monster Data           4188        4    0
      7   Monster Data (again)    492        4    0
      8   Item Data               288        4    0
      9   Equip Data              336        4    0
     10   Important Data          264        4    0
     11   Room Data               356       72    0
     12   Castle Data             256        4    0
     13   System Data             444     2236    0
     14   Event                   260       16    0
     15   Event (again)           260       16    0
     16   Save Event              252        4    0
     17   Warp Event              300        4    0
     18   Chest Event             280        4    0
     19   Entrance                256        4    0

Three registrations reuse a register still holding the previous string
instead of loading their own, which is why type 7 is labelled "Monster Data"
and types 14 and 15 are both "Event". The contents disambiguate them: type 6
holds monsters (*Killer Bee*, *Orc*), type 7 holds encounter groups named
after terrain (*Grasslands 1*, *Forest 2*), and 14/15 are two flavours of
event (*Sign*, *Opening Handling* against 229 *Decorative Event*).

Every name matches what the records actually contain, which is the strongest
confirmation that both the walk and the table indices are right.

The flag is 1 for exactly Dungeon, Town and Human, and 0 for everything else.
What it selects is not known.

Table C, `next_id`, is a per-type counter of IDs handed out. It is *not* a
record count: `sample1` has `C[4] = 22` but eleven classes, the difference
being classes created and deleted while the demo was built.

## Records

Every record is one allocation in a bump allocator. An allocation is a
20-byte header followed by the record's data, and `bytes_used` points at the
header of the allocation that would come next — which is why a brand-new
project reports 0xB1C while its first record's data would begin at 0xB30.

From one record's data to the next:

    next = payload + A[type] + B[type] + 16 + extra

where `extra` is the u32 at `payload - 4`, the last word of the 20-byte
header. Equivalently: 20 bytes of header, `A[type]` bytes of fixed record,
then `B[type] - 4 + extra` bytes of variable data. Types that never grow have
`B = 4`, so their records simply step by `sizeof + 20`, which is what the
memory-card captures showed.

This walks all eight projects end to end. The last step lands exactly 20 bytes
past `bytes_used` — on the free pointer's own header — and the record count
equals `objects - 1` every time.

The fixed part begins:

    +0x00  u32   object id, unique across the whole project
    +0x04  u32   type
    +0x08  u32   0
    +0x0C  u32   id again
    +0x10  u32   -1        \
    +0x14  u32   type       |  a second, link-shaped group of four
    +0x18  u32   0          |
    +0x1C  u32   -1        /
    +0x4C  char  name, Shift-JIS, NUL-padded

The id is global, not per type: `sample1`'s eleven classes carry 6, 12, 13,
15, 19, 478, 614, 619, 672, 674 and 675, interleaved with every other record
in creation order.

Which types actually grow, measured across the three samples:

    type  0  Field Data      extra = 39208, always
    type  1  Dungeon Data    2672 .. 9120
    type  3  Story Data      364 .. 1500-ish
    type  5  Human Data      932 .. 6976
    type 14  Event           128 .. 950-ish

Everything else has `extra = 0` in every sample. Story, Human and Event grow
because they carry dialogue and event scripts; Dungeon carries its floor
layout.

## The world map

`Field Data` is the same size in every project, which makes it a fixed grid,
and its variable part says so outright. After the record's 436 fixed bytes
come 84 bytes (that is `B[0] - 4`), then the 39,208 bytes of `extra`:

    +0x00  u32    1
    +0x04  u32    0x00020000 in a new field, 0x00030000 in sample1
    +0x08  float  -10.0
    +0x0C  u32    0 in a new field, 13 in sample1  (a terrain set?)
    +0x10  u32    140          width
    +0x14  u32    140          height
    +0x18  19,600 bytes        terrain, one byte per cell
    +0x4C58 19,584 bytes       Z, one byte per cell, sixteen cells short

**Addressing is row-major: `index = y * width + x`, with X contiguous.**
Settled outright by a capture that paints a single tile: the editor reported
X=100, Y=76, Z=128, and the one non-default cell in the file sits at linear
index 10,740 — exactly 76 x 140 + 100. The alternative, 100 x 140 + 76, is
14,076, so there is nothing left to interpret.

The second grid holds Z, the editor's own third coordinate. A brand-new
field is 128 everywhere, which is what the editor showed for the untouched
tile, so 128 is ground level with room to carve down and build up. In
`sample1`'s *Elgiza Isle* it is 0 for **every one of the 12,687 sea cells**
and non-zero for 97.6 % of land cells, ranging 0..181. Rendered, it is the
island's silhouette.

The Z grid stops sixteen bytes short of a full 140 x 140: 19,584 rather than
19,600. Autocorrelation still peaks cleanly at a stride of 140, so it is the
same grid with the last sixteen cells of the bottom row simply not written.

`tools/rpgproj.py --maps --png out/` writes both grids as PNGs. *Elgiza
Isle* comes out as a coastline with rivers, a lake and a scatter of islets to
the south — the shape a world map should have, which is the last confirmation
the orientation needed.

Dungeon and Town records also carry a variable part, but not in this layout:
their blob does not open with a dimension pair, so their interiors are
described some other way.

## Anatomy of a class record (type 4, 4,172 bytes)

Out of 4,172 bytes, only 174 are non-zero in a default class, which makes the
skeleton easy to read. Three fields are pinned outright by captures that
changed one thing each:

    +0x4C   char   name; renaming to ZZZZTESTZZZZ changed those 12 bytes and
                   nothing else, and left bytes_used untouched, so the field
                   is fixed-size and inline
    +0x120  u8     the first attack stat; setting it from 0 to 1 in the editor
                   changed this single byte and the checksum, nothing more
    +0x140  ...    the special-skill array, below

### The special-skill array

A class carries **sixteen 240-byte entries starting at `+0x154`**. The record's
own size confirms the count: `0x154 + 16 * 240 - 8` is exactly 4,172, the
last entry running eight bytes short of a full one.

    +0x000  u32       1 if the entry exists, -1 if free
    +0x004  char[22]  name, Shift-JIS, NUL-terminated
    +0x01A  char      description, NUL-terminated, "\n" for line breaks
    +0x0BC  u32       0 or 1
    +0x0C0  u32       0..3
    +0x0C4  u32       always 0
    +0x0C8  u32       0..25
    +0x0CC  u32       always 0
    +0x0D0  u32       0..7
    +0x0D4  u32       always 0
    +0x0D8  u32       target: 0 one, 1 all
    +0x0DC  u32       effect points
    +0x0E0  i32       effect id, -1 for none
    +0x0E4  u32       cost in points

Session 3 had guessed fifteen entries at `+0x230`, from the lattice of `-1`
words alone. Both readings end at the same offset, which is why the wrong one
looked right for a session.

Two captures settled it. `onetech.ps2` created one Special Skill named
`HOLYSWORD` and changed exactly two things in the file besides the checksum:
nine bytes at `+0x158` and one word at `+0x244`. `twotech.ps2` then added a
second skill, `SunderArmor`, and gave the first the effect *Strong vs.
Demons* — three changes: `SunderArmor` at `+0x248`, a word at `+0x334`, and
`+0x234` going from -1 to 22.

The name offsets are 240 apart, which fixes the stride. The marker offsets are
240 apart too, and sit 236 bytes past their own entry's name — that is, four
bytes before the *next* entry's name, so the editor marks the following blank
row as it fills the current one. And the effect landed at `+0x234`, which is
`+0x154 + 224`: inside entry 0, the entry `HOLYSWORD` occupies. Only the base
at `+0x154` puts it there; the old reading placed it in the wrong entry, which
is what gave the mistake away.

`bytes_used` never moved for either capture, so the array is part of the fixed
record and is not allocated on demand.

Reading `sample1` back confirms the layout and gives the demo's skill list:

    Swordfighter   Sonic Blade, Volcano Rave, Megid Arc, -, Thunder Slash, -
    Hunter         Arrow Flash, -, -
    Initiate       Healing Plus, -
    Noble Wing     Aerial Blade, Healing Wind, -
    Wise Man       Infernal Flames, -, -
    Superbutler    Butler Blitz, Butler Beam, -
    Chicken        Meteo Most Fowl, -

Swordfighter's fourth entry exists and is unnamed with a named skill after it,
so blanks are not only trailing — the marker really is per entry.

The effect id has independent confirmation. Of fifteen named skills in
`sample1`, only two carry one: *Thunder Slash* has 2, and **Megid Arc has 22**
— the same value the editor wrote for *Strong vs. Demons*, on a skill whose
own description reads "The white light from the sword damage demonic foes."
Nothing in the capture could have produced that agreement by accident.

A third capture settled the last three fields at once. `skillcost.ps2` opened
`HOLYSWORD` again and set its cost to 33, its effect to 77 points, and its
target from *1 target* to *all enemies*. `bytes_used` did not move, and
outside the checksum the file differs in exactly one contiguous 13-byte run,
at `+0x0D8` of entry 0:

    +0x0D8    0 -> 1     target
    +0x0DC    0 -> 77    effect points   (0x4D)
    +0x0E0   22 -> 22    effect id, untouched
    +0x0E4    0 -> 33    cost            (0x21)

Three named fields in one run, with the already-known effect id sitting
between two of them and holding still — the alignment is not open to
interpretation. It also confirms the correlation Session 4 had only guessed
at: `+0x0DC` runs 128, 96, 256, 200 across the Swordfighter's four skills and
`+0x0E4` runs 10, 20, 30, 20, exactly the two fields the editor just wrote.
The cost is not capped at the 30 seen in `sample1`; the editor accepted 33.

Read back across the demo, the target flag is only ever 0 or 1, and it means
what it says:

    one   Sonic Blade, Thunder Slash, Arrow Flash, Aerial Blade,
          Butler Blitz, ヒール
    all   Volcano Rave, Megid Arc, Healing Plus, Healing Wind,
          Infernal Flames, Butler Beam, and the four joke skills

Every single-target entry is a melee strike and every group entry is a spell,
a beam or a party heal. No capture was needed to believe it.

The rest of the numeric block stays unconfirmed, and it is smaller than it
looks: `+0x0C4`, `+0x0CC` and `+0x0D4` are zero on all sixteen named skills in
the demo, so only four fields carry anything. `+0x0C0` is 3 on the three
healing skills and 0 everywhere else, which reads as a recovery flag or an
element id. `+0x0BC` is 1 on those same three *and* on *Infernal Flames* —
Session 4 called it healing-only, which the wider read disproves; magic
against physical fits the four better. `+0x0C8` (0..25) and `+0x0D0` (0..7)
look like animation and sound ids, on nothing more than their ranges.

## How the captures were used

Nine memory-card projects, each one change apart:

    empty        2,844 bytes used, 0 records
    newclass     7,036            1 record   (+4,192)
    twoclasses  11,228            2 records  (+4,192)
    renamed     11,228            2 records  (name only)
    onestat     11,228            2 records  (one byte only)
    onemap      50,976            3 records  (+39,748: a field and its map)
    onetech     50,976            3 records  (one skill, inside the record)
    twotech     50,976            3 records  (a second skill and one effect)
    skillcost   50,976            3 records  (cost, points and target on one skill)

The identical 4,192-byte step from `empty` to `newclass` to `twoclasses`
settles the allocator: the overhead repeats on every allocation and records
stay contiguous. `renamed` and `onestat` keep `bytes_used` fixed, which is
what makes them usable as checksum probes — and `onestat`, differing in a
single byte, is what cracked it.

## What is not understood yet

* **The flag** in the type descriptor (1 for Dungeon, Town and Human).
* **Table B's meaning** beyond its arithmetic role — it is the minimum size
  of a record's variable part, but why Room Data needs 68 bytes of it and
  System Data 2,232 is unclear.
* **The 19,584 trailing bytes** of a Field's map data.
* **Four words of a skill entry** — `+0x0BC`, `+0x0C0`, `+0x0C8` and
  `+0x0D0` carry values we can only correlate; the block's other three words
  are zero everywhere we can read.
* **The fixed fields** between `+0xA4` and `+0x200` of the global header.
* **Writing a project back to a memory card**, which needs the ECC in the
  spare area of each 528-byte page recomputed. The project file itself we can
  now build and checksum correctly.
