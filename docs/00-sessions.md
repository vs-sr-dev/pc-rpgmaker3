# Session log

## Session 1 — disc and format analysis

Goal: understand how the disc is built and which formats we will be dealing
with.

Results:

* **`CDIMAGE.TBL` decoded** and verified byte-exact: a 3818-entry index of
  136-byte records into the monolithic `RPGSP.DAT` archive (2.5 GB).
* **`.p64` / `.mpic` decoded and validated**: container plus indexed 4/8 bpp
  texture block, palette stored at the end in CSM1 order, PS2 `0..128`
  alpha. `tools/p64_decode.py` produces correct PNGs.
* **`.iab` audio decoded**: SPU-ADPCM, with a header declaring rate,
  channels, duration and — when present — a 640x448 video track.
* **`.smp` identified**: database preset records, fixed size per category,
  matching the `CEdPro*` classes.
* **`.bin` identified** as pre-built DMA/VIF1 chains (not meshes).
* **Engine architecture mapped** from the executable's RTTI names: 224
  classes, including the whole `SG_*` scene graph, the ~100 `CEdEv*` event
  commands, the `CEdPro*` data model and the keyframe cutscene sequencer.
* Ten curiosities documented in `04-curiosities.md`.

Tools written: `rpgsp_index.py`, `p64_decode.py`, `pstrings.py`.

## Session 2 — cracking the .iab video codec

Goal: identify the video codec, which had no MPEG start codes anywhere and
so could not be played by anything.

Results:

* **The `.iab` body is a chunk chain**, not a fixed interleave: 16-byte
  headers carrying a magic, a float timestamp, size and stride. Walking it
  lands exactly on the end of the file, and gives exactly one chunk per
  frame. The two unknown header fields are the max and min frame size.
* **The codec is MPEG-2 intra** — established by finding the MPEG default
  quantiser matrices in the executable, then showing that the flat frame's
  bitstream is periodic with a period of exactly 42 bits, in 28 runs (one
  per macroblock row of 640x448), and that a macroblock reconstructed from
  the MPEG-2 spec with `intra_vlc_format = 1` matches those 42 bits exactly.
* **There is no slice layer.** The 6 extra bits per row come from the first
  macroblock of each row using `macroblock_type = '01'` (Intra, Quant) to
  re-send the quantiser. Full write-up in `06-iab-video.md`.
* **`tools/iab_video.py`** rebuilds a valid MPEG-2 elementary stream; ffmpeg
  decodes `logo.iab` (220 frames) and `rpg_640_448.iab` (3568 frames) with
  zero errors.
* **`tools/iab_audio.py`** decodes the SPU-ADPCM track to WAV, matching the
  declared duration to the sample.
* **Colour range settled**: the video is full-range YUV, as the PS2 IPU
  produces; decoding it as studio swing blows the highlights out.
* **`.mpic` decoder validated against hardware**: our Agetec logo decode
  matches a PCSX2 frame capture to a mean of 0.9 per colour channel.
* Four more curiosities (11-14), including a fully intact Japanese series
  ident that the USA release never plays.

Follow-up on the naming: `tukuru` is ツクール, the Japanese name of the
series, which makes `tukuru.mpic` holding the Agetec logo a straight
substitution into the Japanese ident's slot. Chasing that turned up a whole
seam of kunrei-style romaji in the asset names — curiosity 15.

Still open: the short per-frame header before the macroblock stream, whose
length varies per file. See `05-open-questions.md`.

Next step: the project format (`sample/game/*`), which is the core of the
engine.

## Session 3 — the project format, opened with a memory card

Goal: the project format (`sample/game/*`), the engine's central data
structure.

The lever was two PCSX2 memory cards captured a minute apart: one holding a
project created and saved with nothing in it, the other the same project
after adding a single Sword & Shield class with every field left at its
default. Diffing those two isolates one object exactly.

Results:

* **`tools/ps2mc.py`** reads PS2 memory card images (PCSX2's 528-byte pages
  included), walks the FAT and extracts the save directories.
* **Memory-card saves are the project format**: `BASLUS-21178a` is
  1,994,768 bytes, the same size and the same header tables as
  `sample/game/sample1`. Every experiment we can run in the emulator now
  applies directly to the disc samples.
* **The 16-byte wrapper is generic.** `capacity` is always the file size
  minus 16, on projects, on `info.dat`, on the in-game save slots and on the
  editor's system save alike.
* **Everything past `bytes_used` is uninitialised memory.** A new project
  uses 2,844 bytes of its 1.99 MB yet the file is non-zero nearly to the
  end. The 56 % byte difference between the three samples that session 2
  measured was mostly leftover heap. Two saves from the same session carry
  identical garbage, which is exactly what makes the differential method
  work.
* **The schema is three tables of twenty `u16`.** Table A at `+0x24` is the
  `sizeof` of each of the twenty record types; table C at `+0x7EA` is the
  next free ID per type. Adding one class incremented `C[4]` and appended
  `A[4]` = 4,172 bytes.
* **Records are laid end to end from 0xB30**, `id` and `type` in the first
  two words, name at `+0x4C` in Shift-JIS. Confirmed on the controlled save
  and cross-checked on the samples, where name strings chain at exactly the
  stride table A predicts for twelve of the twenty types.
* **A class record dissected**: fifteen empty 240-byte entries at `+0x230`,
  almost certainly its technique table.
* Full write-up in `08-project-format.md`.
* Two more curiosities (16, 17): two of the three sample games shipped in
  the USA release are still entirely in Japanese, and one of them is a
  developer's layout test.

Still open: the checksum at `+0x04` resisted every additive scheme and every
usual CRC-32 variant, and the record walk desynchronises partway through the
disc samples, so at least one record kind is variable-length.

## Session 4 — the project format, finished

Goal: the two things session 3 left open — the checksum at `+0x04`, and the
record walk that desynchronised on the disc samples.

Three more memory-card captures, each one change past the last: a second
default class, then the first class renamed to `ZZZZTESTZZZZ`, then one
attack stat moved from 0 to 1.

Results:

* **The checksum is CRC-32** of `data[0x10 : 0x10 + bytes_used]` — the arena,
  from where it starts, for exactly its own declared length. It verifies on
  all eight projects we hold. Session 3 had tested the right polynomial but
  never that range, which ends 16 bytes further in than anything tried.
  Found by exploiting the linearity of CRCs: the *difference* of two
  checksums depends only on the differing bytes and the number of bytes
  after them, so the one-byte capture reduced a four-dimensional search to
  feeding zeros into a register until it matched. One hit, no ambiguity.
* **Confirmed in the executable**: `crc32_init_table` at 0x00357B98,
  `crc32_update` at 0x00357C70, and the caller at 0x001C0F70 that writes
  `bytes_used`, `checksum` and `capacity` into the wrapper.
* **The record walk is exact.** The step is
  `A[type] + B[type] + 16 + extra`, where `extra` is the u32 immediately
  before the record. Table B — the "second per-type table" that had been a
  mystery since session 3 — is the size of each type's *variable* part. It
  reads 4 for every fixed type, which is why those records just step by
  `sizeof + 20`. All eight projects now walk to their last byte, and the
  record count matches the file's own `objects` field every time: 578 for
  `sample1`, 284 for `sample2`, 502 for `sample3`.
* **The twenty record types have names**, recovered from the registration
  code at 0x00100F48: Field, Dungeon, Town, Story, Class, Human, Monster,
  monster groups, Item, Equip, Important, Room, Castle, System, two kinds of
  Event, Save Event, Warp Event, Chest Event, Entrance. Every one matches
  what the records actually hold, which independently confirms the walk.
  The whole database of a real game — 578 records of `sample1`, *Dear Brave
  Heart* — is now readable.
* **The allocator is settled**: a 20-byte header per allocation, records
  contiguous, `bytes_used` pointing at the header of the allocation that
  would come next.
* **The world map is a fixed 140 x 140 grid**, and fully addressed. Every
  Field record in every sample has the same 39,208-byte tail, opening with a
  24-byte header that states the two dimensions. A capture that paints a
  single tile settled the layout outright: the editor reported X=100, Y=76,
  Z=128 and the one changed cell sits at index 10,740 = 76 x 140 + 100, so
  the grid is row-major with X contiguous. The second grid is Z — 128
  everywhere in a new field, 0 for every one of *Elgiza Isle*'s 12,687 sea
  cells. `tools/rpgproj.py --maps --png` renders both, and the island comes
  out with coastline, rivers, a lake and islets.
* **Three class fields pinned outright** by the single-change captures: the
  name is inline at `+0x4C`, `+0x120` is an attack stat (one byte), and
  `+0x140` starts an array of **sixteen 240-byte special-skill slots** —
  session 3 had guessed fifteen at `+0x230`, and both guesses end at the same
  offset, which is why the wrong one looked right. Creating one skill named
  `HOLYSWORD`, then a second one with an effect, pinned the entry base at
  `+0x154` and its stride at 240, with `bytes_used` unchanged both times: the
  array is part of the fixed record. Inside an entry: a 22-byte name, a
  162-byte description, then a numeric block whose effect id is confirmed —
  the editor wrote 22 for *Strong vs. Demons*, and `sample1`'s *Megid Arc*,
  "damages demonic foes", carries the same 22. Read back, the demo's whole
  skill list comes out: Sonic Blade, Volcano Rave, Megid Arc, Thunder Slash
  for the Swordfighter, down to Meteo Most Fowl for the Chicken.
* **Curiosity 20**: the Japanese skill names are still in those fields, behind
  the NUL, because the English overwrote them in place and is shorter.
* The file contains **no pointers**; `+0x0C` is not a relocation base.
* `tools/mipsdis.py` added — disassemble the executable by virtual address.

What is left of the format is meaning rather than structure: the flag in the
type descriptor, the trailing half of a map's tile data, and the field-by-field
layout of each record type.

## Session 5 — the skill entry, finished

One capture closed the last of the special-skill layout. `skillcost.ps2`
reopened `HOLYSWORD` and set three things at once: cost 33, effect 77 points,
and the target from *1 target* to *all enemies*.

* **Three fields pinned in a single diff.** Outside the checksum the file
  differs in exactly one contiguous 13-byte run, at `+0x0D8` of entry 0 —
  target, effect points, and cost, with the already-known effect id sitting
  between two of them and holding still. There is no room left to misread the
  alignment.
* It confirms what Session 4 had only inferred: `+0x0DC` runs 128, 96, 256,
  200 across the Swordfighter's four skills and `+0x0E4` runs 10, 20, 30, 20.
  The 30 was not a cap — the editor took 33.
* **The target flag reads back true across the whole demo.** Every 0 is a
  melee strike, every 1 is a spell, a beam or a party heal.
* A wider read **corrected a Session 4 line**: `+0x0BC` is not healing-only,
  it is 1 on *Infernal Flames* as well. And three of the block's words —
  `+0x0C4`, `+0x0CC`, `+0x0D4` — are zero on all sixteen named skills in the
  demo, so what is still unexplained in a 240-byte entry is four fields, not
  seven.
