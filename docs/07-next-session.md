# TODO — session 3

Ordered by value to the port. Item 1 is the session's main goal; the rest are
there so that a blocked morning has somewhere useful to go.

## 1. The project format (`sample/game/sample1..3`) — main goal

This is the engine's central data structure: maps, events, database,
cutscenes — everything the user creates. Nothing else can be reimplemented
until it is understood.

**What we already know.** Three sample projects, all exactly 1,994,768 bytes.
A first diff shows **56 % of the bytes differ** between them and the varying
regions cover the whole arena, so there is no large constant scaffolding to
skip past. The 32-byte header decodes promisingly:

    +0x00  u32   1,006,148 / 427,496 / 231,940   -- differs per sample
    +0x04  u32   varies wildly                   -- checksum
    +0x08  u32   0x001E7000 = 1,994,752          -- constant: arena capacity
    +0x0C  u32   0x00A02A00 / 0x00A7B900 / 0x00A70480
    +0x10  u32   0x00010000                      -- constant
    +0x14  u32   20                              -- constant
    +0x18  u32   579 / 285 / 503                 -- a count of something
    +0x1C  u32   0

`+0x00` is almost certainly **bytes used**: it is always below the constant
capacity at `+0x08`, and it tracks how elaborate each sample game is. That
would make it the number behind the editor's "Memory" gauge.

`+0x0C` is too large to be a file offset but falls inside the PS2's 32 MB
address space, so it may be a saved pointer.

**Plan.**

1. Map the section table that starts around `+0x10`: the `u16` pairs there
   look like (count, stride). Cross-check every stride against the `.smp`
   record sizes, which are the `sizeof` of the `CEdPro*` classes:
   208 (`ed_human`, `ed_i_w`), 216, 220, 240, 272, 988, 3736, 3784.
   A stride that matches one of those identifies its section outright.
2. Use the text as anchors. Character names, item names and descriptions are
   plain ASCII inside the project; locating them pins the record boundaries,
   and the `.smp` presets give us the expected content to match against.
3. Work out how the three samples' `+0x18` counts (579 / 285 / 503) relate to
   what is visible in-game.

**What would help most: differential captures from PCSX2.** The fastest way
to map fields is to change one thing at a time and diff. Concretely, in the
emulator: create a minimal project, save to the memory card, then repeatedly
change a single value (rename a character, bump one stat, add one event
command) and save to a fresh slot. A handful of such pairs will identify more
fields in an hour than static analysis will in a day. Memory-card saves
should share the layout with `sample/game/*`; confirming that is itself the
first useful result.

## 2. Close the `.iab` frame header

The codec is solved, but the short per-frame header before the macroblock
stream is not: 17 bits in `logo.iab`, 13 in `rpg_640_448.iab`, and the
`eb_ci` videos decode cleanly at no offset yet.

Implement the MPEG-2 **B-15** coefficient table so the first macroblock's
exact bit length can be measured rather than guessed. Validate it by encoding
test images with `ffmpeg -intra_vlc 1` and checking the parser lands exactly
on each slice's start code. The port needs this decoder anyway, so the work
is not throwaway.

## 3. `.bin` geometry — start the VIF/GIF disassembler

The `.bin` files are pre-built DMA/VIF1 chains, not meshes; `UNPACK V4_32`
codes are already recognisable. Two halves:

* a VIF/GIF packet disassembler, to see what data is being uploaded;
* a first pass over `.vutext` and the 16 `.DVP.overlay.*` microprograms, to
  learn the vertex layout they expect and how skinning is done.

Aim for reading one simple object end to end (`evobj/a/a00.bin`, 22 KB, with
its 128x128 texture) rather than general coverage.

## 4. Smaller, self-contained wins

* **`.fnt`** — the header is understood; write the glyph decoder and dump
  `ascii16` and `jis16` to PNG sheets. Small and immediately verifiable.
* **`.hd`/`.bd`** — standard SCE sound banks; a VAG extractor would give us
  the sound effects and confirm the MIDI + sample pipeline.
* **Checksums** — identify the algorithm behind the project header's `+0x04`
  and the texture block's `+0x18`. Needed before we can write files the
  original engine will accept, which is how we validate the port against an
  emulator.

## 5. Loose ends worth a few minutes

* `opening8m.iab` declares 171,354,304 bytes in its header but `CDIMAGE.TBL`
  records 87,469,616. `logo.iab` has no such mismatch. Truncated file,
  pre-encode master, or a misread field?
* `bgm_000.iab` is byte-identical in `stream/` and `stream22/` while every
  other track differs. Deliberate, or a build slip?
* The `net/` configs and the networking modules suggest online features. Is
  any of it reachable in the shipped USA build, or is it all dormant like the
  Japanese logo movie?
